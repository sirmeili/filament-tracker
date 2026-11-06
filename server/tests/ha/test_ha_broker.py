"""The Home Assistant publisher against a real Mosquitto broker (the plain listener of the
test broker in server/fakeprinter/).

Runs only when FT_HA_BROKER (host:port) is set, as it is in CI; see server/README.md to run
it locally. Everything else about the publisher is covered by test_publisher.py.
"""

import asyncio
import json
import os
from collections.abc import Callable

import aiomqtt
import pytest
from ha_helpers import add_product, add_spools
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.engine import create_session_factory
from filament_tracker.domain.enums import SpoolState
from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.entities import AVAILABILITY_TOPIC, LOW_STOCK_TOPIC, TOTALS_TOPIC
from filament_tracker.ha.publisher import HaPublisher

BROKER = os.environ.get("FT_HA_BROKER")
USER = "bblp"
PASSWORD = os.environ.get("FT_FAKE_BROKER_CODE", "fake-access-code")
PREFIX = "ft-test-ha"

EXPECTED = {
    AVAILABILITY_TOPIC,
    TOTALS_TOPIC,
    LOW_STOCK_TOPIC,
    f"{PREFIX}/sensor/filament_tracker/total_spools/config",
    f"{PREFIX}/binary_sensor/filament_tracker/low_filament/config",
}


def published(seen: dict[str, str]) -> bool:
    if not EXPECTED <= seen.keys() or seen[AVAILABILITY_TOPIC] != "online":
        return False
    low = json.loads(seen[LOW_STOCK_TOPIC] or "{}")
    return [p["name"] for p in low.get("products", [])] == ["Black PLA Basic"]


pytestmark = pytest.mark.skipif(not BROKER, reason="set FT_HA_BROKER to use the broker")


def broker() -> BrokerConfig:
    host, _, port = (BROKER or "").rpartition(":")
    return BrokerConfig(host, int(port), False, USER, SecretStr(PASSWORD))


async def retained(topics: list[str], done: Callable[[dict[str, str]], bool]) -> dict[str, str]:
    """Read messages from the broker, as Home Assistant would on connecting, until `done`.
    Retained messages from an earlier run may come first, so `done` checks values."""
    config = broker()
    seen: dict[str, str] = {}
    async with aiomqtt.Client(
        config.host, config.port, username=USER, password=PASSWORD, timeout=10
    ) as client:
        for topic in topics:
            await client.subscribe(topic)
        try:
            async with asyncio.timeout(10):
                async for message in client.messages:
                    seen[str(message.topic)] = bytes(message.payload).decode()  # type: ignore[arg-type]
                    if done(seen):
                        break
        except TimeoutError:
            pass
    return seen


def test_entities_reach_the_broker_and_go_unavailable_on_stop(engine: Engine) -> None:
    sessions: sessionmaker[Session] = create_session_factory(engine)
    with sessions() as session:
        black = add_product(session, low_stock_threshold=2)
        add_spools(session, black, SpoolState.SEALED, 2)
        session.commit()
    ha = HaPublisher(broker(), PREFIX, sessions, poll_seconds=0.1)

    async def main() -> dict[str, str]:
        stopping = asyncio.Event()
        task = asyncio.create_task(ha.run(stopping))
        try:
            seen = await retained([f"{PREFIX}/#", "filament_tracker/#"], done=published)
        finally:
            stopping.set()
            await asyncio.wait_for(task, 10)
        after = await retained(
            [AVAILABILITY_TOPIC], done=lambda seen: seen.get(AVAILABILITY_TOPIC) == "offline"
        )
        seen["after stop"] = after[AVAILABILITY_TOPIC]
        return seen

    loop = asyncio.SelectorEventLoop()
    try:
        seen = loop.run_until_complete(main())
    finally:
        loop.close()

    assert seen[AVAILABILITY_TOPIC] == "online"
    assert f"{PREFIX}/sensor/filament_tracker/total_spools/config" in seen
    assert f"{PREFIX}/binary_sensor/filament_tracker/low_filament/config" in seen
    low = json.loads(seen[LOW_STOCK_TOPIC])
    assert (low["low"], [p["name"] for p in low["products"]]) == (True, ["Black PLA Basic"])
    assert json.loads(seen[TOTALS_TOPIC])["sealed"] == 2
    assert seen["after stop"] == "offline"
