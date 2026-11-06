"""One printer's MQTT connection: pin its certificate, read its reports, keep the AMS
slots and spools up to date, and reconnect with backoff.

The only thing ever published is `pushall`, on connect and every 30 minutes, because P1
printers otherwise report only what changed. The access code is never logged.
"""

import asyncio
import json
import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

import aiomqtt
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer
from filament_tracker.db.types import utcnow
from filament_tracker.printer.report import AmsView, TrayReport
from filament_tracker.printer.tls import (
    CertificateMismatchError,
    fetch_fingerprint,
    pinned_context,
)
from filament_tracker.services.ams import ingest

logger = logging.getLogger(__name__)

USERNAME = "bblp"
PUSHALL = {"pushing": {"sequence_id": "0", "command": "pushall", "version": 1, "push_target": 1}}
PUSHALL_EVERY = timedelta(minutes=30)
# A printer reports about once a second while printing; record that it was seen at most
# this often. A printer is online when it reported in the last 5 minutes.
SEEN_WRITE_EVERY = timedelta(minutes=1)
MAX_PAYLOAD = 1_000_000
BACKOFF_FIRST = 1.0
BACKOFF_MAX = 60.0


class LinkState(StrEnum):
    STARTING = "starting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PIN_MISMATCH = "pin_mismatch"


@dataclass(frozen=True)
class LinkStatus:
    state: LinkState
    since: datetime
    # For a pin mismatch, the fingerprint the printer presented instead.
    presented_sha256: str | None = None


class MqttClient(Protocol):
    """The parts of aiomqtt.Client the link uses, so tests can stand in for it."""

    messages: Any

    async def __aenter__(self) -> "MqttClient": ...
    async def __aexit__(self, *exc: object) -> None: ...
    async def subscribe(self, topic: str) -> Any: ...
    async def publish(self, topic: str, payload: str) -> None: ...


ClientFactory = Callable[..., MqttClient]


def _mismatch(error: BaseException) -> CertificateMismatchError | None:
    """The pin mismatch behind an MQTT error, if that is what it was."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, CertificateMismatchError):
            return current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None


class PrinterLink:
    def __init__(
        self,
        config: PrinterConfig,
        printer_id: int,
        session_factory: sessionmaker[Session],
        *,
        client_factory: ClientFactory = aiomqtt.Client,
        fetch: Callable[[str, int], str] = fetch_fingerprint,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.config = config
        self.printer_id = printer_id
        self._sessions = session_factory
        self._client_factory = client_factory
        self._fetch = fetch
        self._sleep = sleep
        self._clock = clock
        self._view = AmsView()
        self._ingested: list[TrayReport] | None = None
        self._last_seen_write: datetime | None = None
        self._connected = False
        self.status = LinkStatus(LinkState.STARTING, clock())

    @property
    def report_topic(self) -> str:
        return f"device/{self.config.serial}/report"

    @property
    def request_topic(self) -> str:
        return f"device/{self.config.serial}/request"

    async def run(self) -> None:
        """Stay connected until cancelled."""
        backoff = BACKOFF_FIRST
        while True:
            self._connected = False
            try:
                await self._connect_once()
                self._set(LinkState.DISCONNECTED)
            except (aiomqtt.MqttError, OSError) as error:
                mismatch = _mismatch(error)
                if mismatch is not None:
                    self._set(LinkState.PIN_MISMATCH, mismatch.actual)
                    logger.warning(
                        "%s: certificate does not match the pin; not connecting",
                        self.config.name,
                    )
                else:
                    self._set(LinkState.DISCONNECTED)
                    logger.warning("%s: connection failed: %s", self.config.name, error)
            if self._connected:
                # A session ends with an error when the connection drops; start over quickly.
                backoff = BACKOFF_FIRST
            await self._sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)

    async def _connect_once(self) -> None:
        pin = await self._pin()
        client = self._client_factory(
            hostname=self.config.host,
            port=self.config.port,
            username=USERNAME,
            password=self.config.access_code.get_secret_value(),
            identifier=f"filament-tracker-{secrets.token_hex(4)}",
            tls_context=pinned_context(pin),
            # The pin replaces hostname checks, which a printer's certificate cannot pass.
            tls_insecure=True,
            keepalive=60,
            timeout=10,
        )
        async with client:
            self._connected = True
            self._set(LinkState.CONNECTED)
            logger.info("%s: connected", self.config.name)
            await client.subscribe(self.report_topic)
            pusher = asyncio.create_task(self._push_all(client))
            try:
                async for message in client.messages:
                    self._handle_safely(message.payload)
            finally:
                pusher.cancel()

    async def _pin(self) -> str:
        with self._sessions() as session:
            printer = session.get_one(Printer, self.printer_id)
            if printer.cert_sha256:
                return printer.cert_sha256
        sha256 = await asyncio.to_thread(self._fetch, self.config.host, self.config.port)
        with self._sessions() as session:
            printer = session.get_one(Printer, self.printer_id)
            printer.cert_sha256 = sha256
            session.commit()
        logger.info("%s: pinned certificate %s", self.config.name, sha256)
        return sha256

    async def _push_all(self, client: MqttClient) -> None:
        while True:
            await client.publish(self.request_topic, json.dumps(PUSHALL))
            await self._sleep(PUSHALL_EVERY.total_seconds())

    def _handle_safely(self, payload: object) -> None:
        try:
            self.handle(payload)
        except Exception:
            # One bad report must not end the connection; the next pushall resyncs.
            logger.exception("%s: could not apply a report", self.config.name)
            self._ingested = None

    def handle(self, payload: object) -> None:
        """Merge one report and write what changed."""
        if isinstance(payload, bytes | bytearray):
            payload = bytes(payload[: MAX_PAYLOAD + 1]).decode("utf-8", errors="replace")
        if not isinstance(payload, str) or len(payload) > MAX_PAYLOAD:
            return
        try:
            message = json.loads(payload)
        except ValueError:
            logger.debug("%s: report is not JSON", self.config.name)
            return
        changed = self._view.apply(message)
        now = self._clock()
        trays = self._view.trays() if changed else None
        new_trays = trays is not None and trays != self._ingested
        seen_due = self._last_seen_write is None or now - self._last_seen_write >= SEEN_WRITE_EVERY
        if not (new_trays or seen_due):
            return
        with self._sessions() as session:
            printer = session.get_one(Printer, self.printer_id)
            if seen_due:
                printer.last_report_at = now
                self._last_seen_write = now
            if new_trays and trays is not None:
                ingest(session, printer, trays, now)
                self._ingested = trays
            session.commit()

    def _set(self, state: LinkState, presented: str | None = None) -> None:
        if self.status.state != state or self.status.presented_sha256 != presented:
            self.status = LinkStatus(state, self._clock(), presented)
