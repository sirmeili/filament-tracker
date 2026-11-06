"""MQTT discovery messages for Home Assistant (docs/SPEC.md, Home Assistant).

Everything is published retained, so Home Assistant finds the entities and their latest
state whenever it (re)connects. One device, "Filament Tracker", holds five entities:

- Total spools (sealed and open, not used up), Total open, Total sealed;
- Low filament, on while any product is low on stock, listing those products;
- Spools in review (the Review page's count).

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
LOW_STOCK_TOPIC = f"{BASE}/low_stock"

DEVICE = {
    "identifiers": [NODE],
    "name": "Filament Tracker",
    "manufacturer": "Filament Tracker",
    "model": "Spool tracker server",
}

# (object ID, name, key in the totals message, icon)
TOTALS = (
    ("total_spools", "Total spools", "spools", "mdi:printer-3d-nozzle"),
    ("total_open", "Total open", "open", "mdi:package-variant"),
    ("total_sealed", "Total sealed", "sealed", "mdi:package-variant-closed"),
    ("in_review", "Spools in review", "in_review", "mdi:clipboard-alert-outline"),
)


def birth_topic(prefix: str) -> str:
    """Where Home Assistant says it has (re)started."""
    return f"{prefix}/status"


def owned_topics(prefix: str) -> list[str]:
    """Subscriptions that cover every retained message this server could have published,
    including ones from older versions, so stale ones can be cleared."""
    return [f"{prefix}/+/{NODE}/+/config", f"{BASE}/#"]


def is_owned(topic: str, prefix: str) -> bool:
    parts = topic.split("/")
    if topic.startswith(f"{BASE}/"):
        return True
    head = prefix.split("/")
    return (
        len(parts) == len(head) + 4
        and parts[: len(head)] == head
        and parts[len(head) + 1] == NODE
        and parts[-1] == "config"
    )


def _dump(value: Any) -> str:
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


def _low_product(product: ProductState) -> dict[str, Any]:
    return {
        "name": product.name,
        "filament_type": product.filament_type,
        # The swatch color as #RRGGBB (the tag's alpha byte dropped).
        "color": f"#{product.color_rgba[:6].upper()}",
        "sealed": product.sealed,
        "threshold": product.low_stock_threshold,
    }


def messages(snapshot: Snapshot, prefix: str) -> dict[str, str]:
    """Every retained message for this snapshot, by topic."""
    out: dict[str, str] = {}
    for object_id, name, key, icon in TOTALS:
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
    topic, payload = _config(
        prefix,
        "binary_sensor",
        "low_filament",
        {
            "name": "Low filament",
            "state_topic": LOW_STOCK_TOPIC,
            "value_template": "{{ 'ON' if value_json.low else 'OFF' }}",
            "json_attributes_topic": LOW_STOCK_TOPIC,
            "json_attributes_template": (
                "{{ {'count': value_json.count, 'products': value_json.products} | tojson }}"
            ),
            "device_class": "problem",
            "icon": "mdi:cart-arrow-down",
        },
    )
    out[topic] = payload
    out[TOTALS_TOPIC] = _dump(
        {
            "spools": snapshot.total_spools,
            "open": snapshot.total_open,
            "sealed": snapshot.total_sealed,
            "in_review": snapshot.in_review,
        }
    )
    low = [_low_product(p) for p in snapshot.low_stock]
    out[LOW_STOCK_TOPIC] = _dump({"low": bool(low), "count": len(low), "products": low})
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
