import json

from filament_tracker.ha.entities import (
    AVAILABILITY_TOPIC,
    TOTALS_TOPIC,
    birth_topic,
    changes,
    messages,
    product_topic,
)
from filament_tracker.ha.snapshot import ProductState, Snapshot

BLACK = ProductState(7, "Black PLA Basic", "PLA", "000000ff", sealed=1, open=2, low_stock=True)
SNAPSHOT = Snapshot((BLACK,), total_sealed=1, in_review=3)


def test_each_product_has_a_sealed_sensor_and_a_low_stock_binary_sensor() -> None:
    out = messages(SNAPSHOT, "homeassistant")

    sealed = json.loads(out["homeassistant/sensor/filament_tracker/product_7_sealed/config"])
    assert sealed["name"] == "Black PLA Basic sealed"
    assert sealed["unique_id"] == "filament_tracker_product_7_sealed"
    assert sealed["state_topic"] == sealed["json_attributes_topic"] == product_topic(7)
    assert sealed["value_template"] == "{{ value_json.sealed }}"
    assert sealed["device"]["name"] == "Filament Tracker"
    assert sealed["availability_topic"] == AVAILABILITY_TOPIC

    low = json.loads(out["homeassistant/binary_sensor/filament_tracker/product_7_low_stock/config"])
    assert low["name"] == "Black PLA Basic low stock"
    assert low["device_class"] == "problem"
    assert "low_stock" in low["value_template"]

    assert json.loads(out[product_topic(7)]) == {
        "sealed": 1,
        "open": 2,
        "display_name": "Black PLA Basic",
        "filament_type": "PLA",
        "color": "#000000",
        "low_stock": True,
    }


def test_totals_for_sealed_spools_and_review() -> None:
    out = messages(SNAPSHOT, "ha")

    total = json.loads(out["ha/sensor/filament_tracker/total_sealed/config"])
    review = json.loads(out["ha/sensor/filament_tracker/in_review/config"])
    assert total["value_template"] == "{{ value_json.sealed }}"
    assert review["value_template"] == "{{ value_json.in_review }}"
    assert json.loads(out[TOTALS_TOPIC]) == {"sealed": 1, "in_review": 3}
    assert all(topic.startswith(("ha/", "filament_tracker/")) for topic in out)


def test_messages_are_stable_for_the_same_snapshot() -> None:
    assert messages(SNAPSHOT, "homeassistant") == messages(SNAPSHOT, "homeassistant")


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


def test_home_assistant_announces_itself_on_the_prefix_status_topic() -> None:
    assert birth_topic("homeassistant") == "homeassistant/status"
