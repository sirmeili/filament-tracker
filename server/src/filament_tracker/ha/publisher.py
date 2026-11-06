"""Keep Home Assistant's entities in step with the database, over MQTT.

Every few seconds the publisher reads a snapshot and publishes only what changed, so every
way stock changes (scanners, the phone, the web app, the printer) reaches Home Assistant
without hooking each one. It runs on its own selector event loop in a background thread,
like the printer links, and reconnects with backoff when the broker goes away.

The broker is told to publish "offline" if the connection drops (the MQTT will), and the
publisher sends "offline" itself on a clean stop, so the entities show as unavailable while
the server is down. When Home Assistant restarts, everything is published again.
"""

import asyncio
import logging
import secrets
import threading
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, Protocol

import aiomqtt
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.entities import (
    AVAILABILITY_TOPIC,
    OFFLINE,
    ONLINE,
    birth_topic,
    changes,
    messages,
)
from filament_tracker.ha.snapshot import take_snapshot

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
BACKOFF_FIRST = 1.0
BACKOFF_MAX = 60.0
STOP_TIMEOUT = 5.0


class MqttStatus(StrEnum):
    OFF = "off"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class MqttClient(Protocol):
    """The parts of aiomqtt.Client the publisher uses, so tests can stand in for it."""

    messages: Any

    async def __aenter__(self) -> "MqttClient": ...
    async def __aexit__(self, *exc: object) -> None: ...
    async def subscribe(self, topic: str) -> Any: ...
    async def publish(
        self, topic: str, payload: str, qos: int = 0, retain: bool = False
    ) -> Any: ...


ClientFactory = Callable[..., MqttClient]


class HaPublisher:
    def __init__(
        self,
        broker: BrokerConfig | None,
        prefix: str,
        session_factory: sessionmaker[Session],
        *,
        client_factory: ClientFactory = aiomqtt.Client,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.broker = broker
        self.prefix = prefix
        self._sessions = session_factory
        self._client_factory = client_factory
        self._poll_seconds = poll_seconds
        self._sleep = sleep
        self.status = MqttStatus.OFF if broker is None else MqttStatus.CONNECTING
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stopping: asyncio.Event | None = None

    # --- the background thread -------------------------------------------------------

    def start(self) -> None:
        if self.broker is None:
            return
        self._loop = asyncio.SelectorEventLoop()
        self._stopping = asyncio.Event()
        self._thread = threading.Thread(
            target=self._run_thread, args=(self._loop, self._stopping), name="ha-mqtt", daemon=True
        )
        self._thread.start()
        logger.info(
            "publishing Home Assistant entities to %s:%d", self.broker.host, self.broker.port
        )

    def stop(self) -> None:
        if self._loop is None or self._thread is None or self._stopping is None:
            return
        self._loop.call_soon_threadsafe(self._stopping.set)
        self._thread.join(STOP_TIMEOUT)

    def _run_thread(self, loop: asyncio.AbstractEventLoop, stopping: asyncio.Event) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run(stopping))
        finally:
            loop.close()

    # --- the connection --------------------------------------------------------------

    async def run(self, stopping: asyncio.Event) -> None:
        """Stay connected and publishing until `stopping` is set."""
        backoff = BACKOFF_FIRST
        while not stopping.is_set():
            connected = False
            try:
                connected = await self._session(stopping)
            except (aiomqtt.MqttError, OSError) as error:
                # The error names the problem (refused, not authorised); never the password.
                logger.warning("Home Assistant MQTT: connection failed: %s", error)
            if stopping.is_set():
                break
            self.status = MqttStatus.DISCONNECTED
            if connected:
                backoff = BACKOFF_FIRST
            await _wait(stopping, self._sleep(backoff))
            backoff = min(backoff * 2, BACKOFF_MAX)
        self.status = MqttStatus.OFF

    async def _session(self, stopping: asyncio.Event) -> bool:
        broker = self.broker
        if broker is None:
            return False
        password = broker.password.get_secret_value() if broker.password else None
        client = self._client_factory(
            hostname=broker.host,
            port=broker.port,
            username=broker.username,
            password=password,
            identifier=f"filament-tracker-{secrets.token_hex(4)}",
            tls_context=broker.tls_context(),
            will=aiomqtt.Will(AVAILABILITY_TOPIC, OFFLINE, qos=1, retain=True),
            keepalive=60,
            timeout=10,
        )
        async with client:
            self.status = MqttStatus.CONNECTED
            logger.info("Home Assistant MQTT: connected")
            await client.subscribe(birth_topic(self.prefix))
            resend = asyncio.Event()
            listener = asyncio.create_task(self._listen(client, resend))
            try:
                await self._publish_loop(client, stopping, resend, listener)
            finally:
                listener.cancel()
                await asyncio.gather(listener, return_exceptions=True)
            if stopping.is_set():
                await client.publish(AVAILABILITY_TOPIC, OFFLINE, qos=1, retain=True)
        return True

    async def _listen(self, client: MqttClient, resend: asyncio.Event) -> None:
        """Republish everything when Home Assistant says it has started."""
        async for message in client.messages:
            payload = message.payload
            if isinstance(payload, bytes | bytearray):
                payload = bytes(payload[:16]).decode("utf-8", errors="replace")
            if str(payload).strip() == ONLINE:
                resend.set()

    async def _publish_loop(
        self,
        client: MqttClient,
        stopping: asyncio.Event,
        resend: asyncio.Event,
        listener: asyncio.Task[None],
    ) -> None:
        published: dict[str, str] = {}
        await client.publish(AVAILABILITY_TOPIC, ONLINE, qos=1, retain=True)
        while not stopping.is_set():
            if resend.is_set():
                resend.clear()
                published = {}
                await client.publish(AVAILABILITY_TOPIC, ONLINE, qos=1, retain=True)
            current = self._read()
            for topic, payload in changes(published, current):
                await client.publish(topic, payload, qos=1, retain=True)
            published = current
            # Wake for the next poll, a Home Assistant restart, a stop, or a lost connection.
            waits = [
                asyncio.ensure_future(self._sleep(self._poll_seconds)),
                asyncio.ensure_future(resend.wait()),
                asyncio.ensure_future(stopping.wait()),
                listener,
            ]
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
            for waiter in waits[:3]:
                waiter.cancel()
            if listener.done():
                # The message stream ended: the connection is gone.
                listener.result()
                raise aiomqtt.MqttError("connection lost")

    def _read(self) -> dict[str, str]:
        with self._sessions() as session:
            return messages(take_snapshot(session), self.prefix)


async def _wait(stopping: asyncio.Event, delay: Awaitable[None]) -> None:
    """Sleep, but wake early on a stop."""
    sleeper = asyncio.ensure_future(delay)
    stopper = asyncio.ensure_future(stopping.wait())
    await asyncio.wait([sleeper, stopper], return_when=asyncio.FIRST_COMPLETED)
    sleeper.cancel()
    stopper.cancel()
