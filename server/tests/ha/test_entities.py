import json

import pytest

from filament_tracker.ha.entities import (
    AVAILABILITY_TOPIC,
    LOW_STOCK_TOPIC,
    TOTALS_TOPIC,
    birth_topic,
    changes,
    is_owned,
    messages,
    owned_topics,
)
from filament_tracker.ha.snapshot import ProductState, Snapshot

BLACK = ProductState(7, "Black PLA Basic", "PLA", "000000ff", 1, 2, True, 2)
WHITE = ProductState(8, "White PETG", "PETG", "FFFFFFFF", 4, 0, False, 1)
SNAPSHOT = Snapshot((BLACK, WHITE), total_sealed=5, total_open=2, in_review=3)


def config(out: dict[str, str], topic: str) -> dict[str, object]:
    return json.loads(out[topic])


def test_one_device_with_five_entities() -> None:
    out = messages(SNAPSHOT, "homeassistant")

    configs = sorted(t for t in out if t.endswith("/config"))
    assert configs == [
        "homeassistant/binary_sensor/filament_tracker/low_filament/config",
        "homeassistant/sensor/filament_tracker/in_review/config",
        "homeassistant/sensor/filament_tracker/total_open/config",
        "homeassistant/sensor/filament_tracker/total_sealed/config",
        "homeassistant/sensor/filament_tracker/total_spools/config",
    ]
    for topic in configs:
        entity = config(out, topic)
        assert entity["device"] == config(out, configs[0])["device"]
        assert entity["availability_topic"] == AVAILABILITY_TOPIC
        assert str(entity["unique_id"]).startswith("filament_tracker_")


def test_totals() -> None:
    out = messages(SNAPSHOT, "homeassistant")

    names = {
        key: config(out, f"homeassistant/sensor/filament_tracker/{key}/config")["name"]
        for key in ("total_spools", "total_open", "total_sealed", "in_review")
    }
    assert names == {
        "total_spools": "Total spools",
        "total_open": "Total open",
        "total_sealed": "Total sealed",
        "in_review": "Spools in review",
    }
    spools = config(out, "homeassistant/sensor/filament_tracker/total_spools/config")
    assert spools["state_topic"] == TOTALS_TOPIC
    assert spools["value_template"] == "{{ value_json.spools }}"
    assert json.loads(out[TOTALS_TOPIC]) == {"spools": 7, "open": 2, "sealed": 5, "in_review": 3}


def test_low_filament_is_on_and_lists_the_low_products() -> None:
    out = messages(SNAPSHOT, "homeassistant")

    low = config(out, "homeassistant/binary_sensor/filament_tracker/low_filament/config")
    assert low["name"] == "Low filament"
    assert low["state_topic"] == low["json_attributes_topic"] == LOW_STOCK_TOPIC
    assert low["device_class"] == "problem"
    assert json.loads(out[LOW_STOCK_TOPIC]) == {
        "low": True,
        "count": 1,
        "products": [
            {
                "name": "Black PLA Basic",
                "filament_type": "PLA",
                "color": "#000000",
                "sealed": 1,
                "threshold": 2,
            }
        ],
    }


def test_low_filament_is_off_when_nothing_is_low() -> None:
    out = messages(Snapshot((WHITE,), 4, 0, 0), "homeassistant")
    assert json.loads(out[LOW_STOCK_TOPIC]) == {"low": False, "count": 0, "products": []}


def test_messages_are_stable_for_the_same_snapshot() -> None:
    assert messages(SNAPSHOT, "ha") == messages(SNAPSHOT, "ha")
    assert all(t.startswith(("ha/", "filament_tracker/")) for t in messages(SNAPSHOT, "ha"))


def test_changes_send_configs_first_and_remove_configs_last() -> None:
    before = {"a/state": "1", "p/sensor/x/config": "c", "gone/state": "s", "p/gone/config": "g"}
    after = {"a/state": "2", "p/sensor/x/config": "c", "p/new/config": "n", "b/state": "b"}

    assert changes(before, after) == [
        ("p/new/config", "n"),
        ("a/state", "2"),
        ("b/state", "b"),
        ("gone/state", ""),
        ("p/gone/config", ""),
    ]
    assert changes(after, after) == []


@pytest.mark.parametrize(
    ("topic", "owned"),
    [
        ("homeassistant/sensor/filament_tracker/product_1_sealed/config", True),
        ("homeassistant/binary_sensor/filament_tracker/low_filament/config", True),
        ("filament_tracker/product/1", True),
        ("homeassistant/sensor/other_app/x/config", False),
        ("homeassistant/sensor/filament_tracker/x/state", False),
        ("homeassistant/status", False),
        ("ha/sensor/filament_tracker/x/config", False),
    ],
)
def test_knows_which_topics_are_its_own(topic: str, owned: bool) -> None:
    assert is_owned(topic, "homeassistant") is owned


def test_owned_topics_with_a_longer_prefix() -> None:
    assert owned_topics("my/ha") == ["my/ha/+/filament_tracker/+/config", "filament_tracker/#"]
    assert is_owned("my/ha/sensor/filament_tracker/x/config", "my/ha")
    assert not is_owned("my/sensor/filament_tracker/x/config", "my/ha")


def test_home_assistant_announces_itself_on_the_prefix_status_topic() -> None:
    assert birth_topic("homeassistant") == "homeassistant/status"
