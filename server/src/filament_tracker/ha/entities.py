"""MQTT discovery messages for Home Assistant (docs/SPEC.md, Home Assistant).

Everything is published retained, so Home Assistant finds the entities and their latest
state whenever it (re)connects. One device, "Filament Tracker", holds:

- per product, a sensor with the sealed count (open count, color, name and type as
  attributes) and a binary sensor that is on when the product is low on stock;
- a sensor with all sealed spools, and one with the spools waiting in Review.

The entities are unavailable while the server is not connected to the broker.
"""

import json
from typing import Any

from filament_tracker.ha.snapshot import ProductState, Snapshot

NODE = "filament_tracker"
BASE = "filament_tracker"
AVAILABILITY_TOPIC = f"{BASE}/status"
ONLINE, OFFLINE = "online", "offline"
TOTALS_TOPIC = f"{BASE}/totals"

DEVICE = {
    "identifiers": [NODE],
    "name": "Filament Tracker",
    "manufacturer": "Filament Tracker",
    "model": "Spool tracker server",
}


def product_topic(product_id: int) -> str:
    return f"{BASE}/product/{product_id}"


def birth_topic(prefix: str) -> str:
    """Where Home Assistant says it has (re)started."""
    return f"{prefix}/status"


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _config(prefix: str, component: str, object_id: str, fields: dict[str, Any]) -> tuple[str, str]:
    topic = f"{prefix}/{component}/{NODE}/{object_id}/config"
    payload = {
        "unique_id": f"{NODE}_{object_id}",
        "has_entity_name": True,
        "device": DEVICE,
        "availability_topic": AVAILABILITY_TOPIC,
        "payload_available": ONLINE,
        "payload_not_available": OFFLINE,
    } | fields
    return topic, _dump(payload)


def _product_messages(prefix: str, product: ProductState) -> dict[str, str]:
    state = product_topic(product.id)
    sealed = _config(
        prefix,
        "sensor",
        f"product_{product.id}_sealed",
        {
            "name": f"{product.name} sealed",
            "state_topic": state,
            "value_template": "{{ value_json.sealed }}",
            "json_attributes_topic": state,
            "unit_of_measurement": "spools",
            "state_class": "measurement",
            "icon": "mdi:printer-3d-nozzle",
        },
    )
    low = _config(
        prefix,
        "binary_sensor",
        f"product_{product.id}_low_stock",
        {
            "name": f"{product.name} low stock",
            "state_topic": state,
            "value_template": "{{ 'ON' if value_json.low_stock else 'OFF' }}",
            "device_class": "problem",
            "icon": "mdi:cart-arrow-down",
        },
    )
    payload = {
        "sealed": product.sealed,
        "open": product.open,
        "display_name": product.name,
        "filament_type": product.filament_type,
        # The swatch color as #RRGGBB (the tag's alpha byte dropped).
        "color": f"#{product.color_rgba[:6].upper()}",
        "low_stock": product.low_stock,
    }
    return dict([sealed, low, (state, _dump(payload))])


def messages(snapshot: Snapshot, prefix: str) -> dict[str, str]:
    """Every retained message for this snapshot, by topic."""
    out: dict[str, str] = {}
    for product in snapshot.products:
        out |= _product_messages(prefix, product)
    for object_id, name, key, icon in (
        ("total_sealed", "Sealed spools", "sealed", "mdi:package-variant-closed"),
        ("in_review", "Spools in review", "in_review", "mdi:clipboard-alert-outline"),
    ):
        topic, payload = _config(
            prefix,
            "sensor",
            object_id,
            {
                "name": name,
                "state_topic": TOTALS_TOPIC,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "unit_of_measurement": "spools",
                "state_class": "measurement",
                "icon": icon,
            },
        )
        out[topic] = payload
    out[TOTALS_TOPIC] = _dump({"sealed": snapshot.total_sealed, "in_review": snapshot.in_review})
    return out


def changes(published: dict[str, str], current: dict[str, str]) -> list[tuple[str, str]]:
    """What to publish to go from `published` to `current`: new or changed messages, and an
    empty retained message for each one that is gone (which removes the entity). Discovery
    configs go first, so Home Assistant knows an entity before its state arrives, and are
    removed last."""
    updates = [(t, p) for t, p in current.items() if published.get(t) != p]
    removals = [(t, "") for t in published if t not in current]
    configs_first = sorted(updates, key=lambda item: not item[0].endswith("/config"))
    configs_last = sorted(removals, key=lambda item: item[0].endswith("/config"))
    return configs_first + configs_last
