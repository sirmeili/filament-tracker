import json
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.diagnose import (
    ENTITIES,
    broker_report,
    config_topic,
    entities_report,
    expected_state,
    find_entity,
    read_retained,
    topics,
)
from filament_tracker.ha.entities import AVAILABILITY_TOPIC, LOW_STOCK_TOPIC, TOTALS_TOPIC

PREFIX = "homeassistant"
BROKER = BrokerConfig("broker.local", 1883, False, "user", SecretStr("broker-pass"))


def retained(**changes: Any) -> dict[str, str]:
    """Everything the server publishes: 12 spools, 7 open, 5 sealed, one product low."""
    out = {config_topic(PREFIX, e): "{}" for e in ENTITIES}
    out[AVAILABILITY_TOPIC] = "online"
    out[TOTALS_TOPIC] = json.dumps({"spools": 12, "open": 7, "sealed": 5, "in_review": 0})
    out[LOW_STOCK_TOPIC] = json.dumps({"low": True, "count": 1, "products": [{"name": "x"}]})
    for topic, value in changes.items():
        topic = {"availability": AVAILABILITY_TOPIC, "totals": TOTALS_TOPIC}.get(topic, topic)
        topic = LOW_STOCK_TOPIC if topic == "low" else topic
        if value is None:
            out.pop(topic, None)
        else:
            out[topic] = value
    return out


def ha_states(**overrides: str) -> list[dict[str, Any]]:
    states = {
        "Total spools": "12",
        "Total open": "7.0",
        "Total sealed": "5",
        "Spools in review": "0",
        "Low filament": "on",
    } | overrides
    return [
        {
            "entity_id": f"sensor.other_{i}",
            "state": state,
            "attributes": {"friendly_name": f"Filament Tracker {name}"},
        }
        for i, (name, state) in enumerate(states.items())
    ] + [{"entity_id": "light.kitchen", "state": "on", "attributes": {"friendly_name": "Kitchen"}}]


# --- reading the broker --------------------------------------------------------------


@dataclass
class Message:
    topic: str
    payload: Any
    retain: bool


class FakeClient:
    made: list[dict[str, Any]] = []

    def __init__(self, messages: list[Message], **kwargs: Any) -> None:
        FakeClient.made.append(kwargs)
        self._messages = messages
        self.subscribed: list[str] = []
        self.closed = False
        FakeClient.last = self

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True

    async def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    @property
    def messages(self) -> Any:
        async def gen() -> Any:
            for message in self._messages:
                yield message
            import asyncio

            await asyncio.sleep(3600)  # a real broker goes quiet; the timeout ends the read

        return gen()


def test_reads_only_retained_messages_until_quiet() -> None:
    FakeClient.made = []
    messages = [
        Message(TOTALS_TOPIC, b'{"spools": 1}', True),
        Message(AVAILABILITY_TOPIC, "online", True),
        Message(LOW_STOCK_TOPIC, b"live, not retained", False),
    ]
    seen = read_retained(BROKER, PREFIX, 0.05, lambda **kw: FakeClient(messages, **kw))
    assert seen == {TOTALS_TOPIC: '{"spools": 1}', AVAILABILITY_TOPIC: "online"}
    assert FakeClient.last.subscribed == topics(PREFIX)
    assert FakeClient.last.closed
    made = FakeClient.made[0]
    assert (made["hostname"], made["username"], made["password"]) == (
        "broker.local",
        "user",
        "broker-pass",
    )
    assert made["identifier"].startswith("filament-tracker-check-")


def test_subscribes_to_the_discovery_messages_under_the_prefix() -> None:
    assert topics("ha2")[0] == "ha2/+/filament_tracker/+/config"
    assert config_topic("ha2", ENTITIES[-1]) == (
        "ha2/binary_sensor/filament_tracker/low_filament/config"
    )


# --- the broker report ---------------------------------------------------------------


def test_everything_published() -> None:
    report = broker_report(retained(), PREFIX)
    assert report.ok
    assert report.lines == [
        "  Discovery: 5 of 5 entities",
        "  Availability: online",
        "  Totals: 12 spools, 7 open, 5 sealed, 0 in review",
        "  Low filament: on (1 product low)",
    ]


def test_missing_and_old_entities_are_problems() -> None:
    topic = config_topic(PREFIX, ENTITIES[0])
    old = f"{PREFIX}/sensor/filament_tracker/black_pla_sealed/config"
    report = broker_report(retained(**{topic: None, old: "{}"}), PREFIX)
    assert not report.ok
    assert "  Discovery: 4 of 5 entities  <-- problem" in report.lines
    assert "    missing: Total spools  <-- problem" in report.lines
    assert "  Old discovery messages still retained: 1  <-- problem" in report.lines


def test_server_offline_or_nothing_published() -> None:
    report = broker_report({}, PREFIX)
    assert not report.ok
    assert "  Availability: not published  <-- problem" in report.lines
    assert "  Totals: not published  <-- problem" in report.lines
    assert "  Low filament: not published  <-- problem" in report.lines
    offline = broker_report(retained(availability="offline", totals="not json"), PREFIX)
    assert "  Availability: offline  <-- problem" in offline.lines
    assert "  Totals: not published  <-- problem" in offline.lines


def test_low_filament_off_counts_products() -> None:
    report = broker_report(retained(low=json.dumps({"low": False, "count": 0})), PREFIX)
    assert "  Low filament: off (0 products low)" in report.lines
    assert broker_report(retained(low="[1, 2]"), PREFIX).ok is False


# --- comparing with Home Assistant ---------------------------------------------------


def test_expected_states() -> None:
    total, low = ENTITIES[0], ENTITIES[-1]
    assert expected_state(total, retained()) == "12"
    assert expected_state(low, retained()) == "on"
    assert expected_state(low, retained(low=json.dumps({"low": False}))) == "off"
    assert expected_state(total, retained(availability="offline")) == "unavailable"
    assert expected_state(total, retained(totals=None)) is None
    assert expected_state(low, retained(low=None)) is None


def test_finds_entities_by_name_or_id() -> None:
    by_id = [{"entity_id": "sensor.filament_tracker_spools_in_review", "state": "0"}]
    assert find_entity(by_id, ENTITIES[3]) == by_id[0]
    assert find_entity([{"entity_id": "x", "attributes": "odd"}], ENTITIES[0]) is None


def test_every_entity_matches_the_broker() -> None:
    report = entities_report(ha_states(), retained())
    assert report.ok
    assert "  Total open: 7.0 (matches the broker)" in report.lines
    assert "  Low filament: on (matches the broker)" in report.lines


def test_differences_and_missing_entities_are_problems() -> None:
    states = [s for s in ha_states(**{"Total sealed": "4"}) if "review" not in str(s)]
    report = entities_report(states, retained())
    assert not report.ok
    assert "  Total sealed: 4, the broker has 5  <-- problem" in report.lines
    assert "  Spools in review: not found in Home Assistant  <-- problem" in report.lines
    assert entities_report(ha_states(**{"Total spools": "abc"}), retained()).ok is False


def test_without_the_broker_states_are_listed_only() -> None:
    report = entities_report(ha_states(), None)
    assert report.ok
    assert "  Total spools: 12" in report.lines
