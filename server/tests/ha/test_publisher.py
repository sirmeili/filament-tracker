import asyncio
import json
import threading
from collections.abc import Awaitable, Callable

import pytest
from ha_helpers import FakeBroker, add_product, add_spools
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.engine import create_session_factory
from filament_tracker.domain.enums import SpoolState
from filament_tracker.ha import publisher as publisher_module
from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.entities import AVAILABILITY_TOPIC, TOTALS_TOPIC, product_topic
from filament_tracker.ha.publisher import HaPublisher, MqttStatus

BROKER = BrokerConfig("ha.lan", 1883, False, "filament", SecretStr("broker-secret"))
TICK = 0.01


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def publisher(sessions: sessionmaker[Session], broker: FakeBroker, **kwargs: object) -> HaPublisher:
    return HaPublisher(
        BROKER,
        "homeassistant",
        sessions,
        client_factory=broker.factory,
        poll_seconds=TICK,
        sleep=lambda _seconds: asyncio.sleep(TICK),
        **kwargs,  # type: ignore[arg-type]
    )


async def until(check: Callable[[], bool], what: str = "condition") -> None:
    for _ in range(500):
        if check():
            return
        await asyncio.sleep(TICK)
    raise AssertionError(f"timed out waiting for {what}")


def run(scenario: Callable[[HaPublisher, asyncio.Event], Awaitable[None]], ha: HaPublisher) -> None:
    async def main() -> None:
        stopping = asyncio.Event()
        task = asyncio.create_task(ha.run(stopping))
        try:
            await scenario(ha, stopping)
        finally:
            stopping.set()
            await asyncio.wait_for(task, 5)

    loop = asyncio.SelectorEventLoop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()


def test_publishes_entities_once_and_then_only_changes(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        black = add_product(session, low_stock_threshold=1)
        add_spools(session, black, SpoolState.SEALED, 2)
        session.commit()
        black_id = black.id
    broker = FakeBroker()
    ha = publisher(sessions, broker)

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        await until(lambda: broker.last(TOTALS_TOPIC) is not None, "first publish")
        assert ha.status is MqttStatus.CONNECTED
        topics = broker.topics()
        assert topics[0] == AVAILABILITY_TOPIC
        assert topics.index(
            f"homeassistant/sensor/filament_tracker/product_{black_id}_sealed/config"
        ) < topics.index(product_topic(black_id))
        first = len(broker.published)
        await asyncio.sleep(TICK * 5)
        assert len(broker.published) == first  # nothing changed, nothing sent

        with sessions() as session:
            add_spools(session, session.get_one(type(black), black_id), SpoolState.OPEN)
            session.commit()
        await until(lambda: len(broker.published) > first, "the change")
        await asyncio.sleep(TICK * 3)
        changed = broker.topics()[first:]
        assert changed == [product_topic(black_id)]
        assert json.loads(broker.last(product_topic(black_id)) or "{}")["open"] == 1

    run(scenario, ha)

    assert all(retain and qos == 1 for _t, _p, qos, retain in broker.published)
    assert broker.last(AVAILABILITY_TOPIC) == "offline"  # a clean stop says so
    assert ha.status is MqttStatus.OFF
    connect = broker.kwargs[0]
    assert (connect["hostname"], connect["port"], connect["username"]) == (
        "ha.lan",
        1883,
        "filament",
    )
    assert BROKER.password is not None
    assert connect["password"] == BROKER.password.get_secret_value()
    assert connect["tls_context"] is None
    assert (connect["will"].topic, connect["will"].payload, connect["will"].retain) == (
        AVAILABILITY_TOPIC,
        "offline",
        True,
    )
    assert broker.clients[0].subscribed == ["homeassistant/status"]


def test_republishes_everything_when_home_assistant_restarts(
    sessions: sessionmaker[Session],
) -> None:
    broker = FakeBroker()
    ha = publisher(sessions, broker)

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        await until(lambda: broker.last(TOTALS_TOPIC) is not None)
        first = len(broker.published)
        broker.clients[0].send("homeassistant/status", "offline")  # ignored
        broker.clients[0].send("homeassistant/status", b"online")
        await until(lambda: broker.topics()[first:].count(TOTALS_TOPIC) == 1, "resend")
        assert AVAILABILITY_TOPIC in broker.topics()[first:]

    run(scenario, ha)


def test_reconnects_after_a_refusal_or_a_lost_connection(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    broker = FakeBroker(refuse=2)
    ha = publisher(sessions, broker)

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        await until(lambda: ha.status is MqttStatus.CONNECTED, "connected")
        assert len(broker.clients) == 3
        broker.clients[-1].drop()
        await until(lambda: len(broker.clients) == 4 and ha.status is MqttStatus.CONNECTED, "back")

    run(scenario, ha)

    assert "connection failed" in caplog.text
    assert "broker-secret" not in caplog.text


def test_reports_disconnected_while_the_broker_is_away(sessions: sessionmaker[Session]) -> None:
    broker = FakeBroker(refuse=1000)
    ha = publisher(sessions, broker)

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        assert ha.status is MqttStatus.CONNECTING
        await until(lambda: ha.status is MqttStatus.DISCONNECTED, "disconnected")

    run(scenario, ha)


def test_backoff_doubles_up_to_a_minute(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    broker = FakeBroker(refuse=1000)

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        await asyncio.sleep(0)

    ha = HaPublisher(BROKER, "homeassistant", sessions, client_factory=broker.factory, sleep=sleep)

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        await until(lambda: len(waits) >= 9)

    run(scenario, ha)
    assert waits[:9] == [1, 2, 4, 8, 16, 32, 60, 60, 60]


def test_mqtts_brokers_get_a_tls_context(sessions: sessionmaker[Session]) -> None:
    broker = FakeBroker()
    ha = HaPublisher(
        BrokerConfig("broker.example.com", 8883, True),
        "homeassistant",
        sessions,
        client_factory=broker.factory,
        poll_seconds=TICK,
    )

    async def scenario(ha: HaPublisher, _: asyncio.Event) -> None:
        await until(lambda: ha.status is MqttStatus.CONNECTED)

    run(scenario, ha)
    assert broker.kwargs[0]["tls_context"] is not None
    assert broker.kwargs[0]["username"] is None and broker.kwargs[0]["password"] is None


def test_runs_on_its_own_thread_until_stopped(sessions: sessionmaker[Session]) -> None:
    broker = FakeBroker()
    ha = publisher(sessions, broker)

    ha.start()
    try:
        for _ in range(500):
            if broker.last(TOTALS_TOPIC) is not None:
                break
            threading.Event().wait(TICK)
        assert any(t.name == "ha-mqtt" for t in threading.enumerate())
    finally:
        ha.stop()
    assert not any(t.name == "ha-mqtt" for t in threading.enumerate())
    assert broker.last(AVAILABILITY_TOPIC) == "offline"


def test_without_a_broker_nothing_starts(sessions: sessionmaker[Session]) -> None:
    ha = HaPublisher(None, "homeassistant", sessions)

    ha.start()
    ha.stop()

    assert ha.status is MqttStatus.OFF
    assert not any(t.name == "ha-mqtt" for t in threading.enumerate())


def test_a_session_without_a_broker_does_nothing(sessions: sessionmaker[Session]) -> None:
    ha = HaPublisher(None, "homeassistant", sessions)
    assert asyncio.run(ha._session(asyncio.Event())) is False  # noqa: SLF001


def test_default_timings() -> None:
    assert publisher_module.POLL_SECONDS == 5.0
    assert publisher_module.BACKOFF_MAX == 60.0
