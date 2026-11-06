"""Read the AMS trays out of a Bambu printer's MQTT report messages.

P1 printers send a full report only after a `pushall`; otherwise each message carries just
what changed. `AmsView` merges every message into a full view of the AMS, one entry per
slot. Messages come from the network, so anything malformed is skipped, never raised.

The fields follow the report's `print.ams` section:

    {"print": {"ams": {"ams": [{"id": "0", "tray": [{"id": "0", "tray_uuid": "...",
      "tray_info_idx": "GFA00", "tray_type": "PLA", "tray_sub_brands": "PLA Basic",
      "tray_color": "000000FF", "remain": 85}, {"id": "1"}]}], "tray_exist_bits": "1"}}}

A tray with only an `id` is an empty slot.

Units 0 to 3 are four-slot AMS units; an AMS HT has one slot and an id from 128. In
`tray_exist_bits`, AMS unit n has bits 4n to 4n+3 and AMS HT 128+n has bit 16+n.
"""

import re
from dataclasses import dataclass
from typing import Any

HEX_UUID = re.compile(r"^[0-9A-Fa-f]{32}$")
HEX_COLOR = re.compile(r"^[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
TRAY_FIELDS = (
    "tray_uuid",
    "tray_info_idx",
    "tray_type",
    "tray_sub_brands",
    "tray_color",
    "remain",
)
AMS_UNITS = 4
TRAYS_PER_UNIT = 4
HT_FIRST = 128
HT_UNITS = 8
HT_FIRST_BIT = AMS_UNITS * TRAYS_PER_UNIT


def is_ht(ams_index: int) -> bool:
    return ams_index >= HT_FIRST


def unit_name(ams_index: int) -> str:
    """ "AMS 1" for the first AMS, "AMS HT 1" for the first AMS HT."""
    return f"AMS HT {ams_index - HT_FIRST + 1}" if is_ht(ams_index) else f"AMS {ams_index + 1}"


def slot_name(ams_index: int, tray_index: int) -> str:
    """ "AMS 1, slot 2", or just "AMS HT 1" for its only slot."""
    name = unit_name(ams_index)
    return name if is_ht(ams_index) else f"{name}, slot {tray_index + 1}"


def _exist_bit(ams_index: int, tray_index: int) -> int:
    if is_ht(ams_index):
        return HT_FIRST_BIT + ams_index - HT_FIRST
    return ams_index * TRAYS_PER_UNIT + tray_index


def _unit_index(value: object) -> int | None:
    number = _int(value)
    if number is None:
        return None
    if 0 <= number < AMS_UNITS or HT_FIRST <= number < HT_FIRST + HT_UNITS:
        return number
    return None


@dataclass(frozen=True)
class TrayReport:
    """One AMS slot as last reported. Everything but the position may be unknown."""

    ams_index: int
    tray_index: int
    tray_uuid: str | None = None
    material_id: str | None = None
    filament_type: str | None = None
    sub_brand: str | None = None
    color_rgba: str | None = None
    remaining_pct: int | None = None

    @property
    def loaded(self) -> bool:
        return self.tray_uuid is not None or self.filament_type is not None


class AmsView:
    """The merged state of one printer's AMS units."""

    def __init__(self) -> None:
        self._trays: dict[tuple[int, int], dict[str, Any]] = {}

    def apply(self, message: object) -> bool:
        """Merge one report message. Returns whether it had an AMS section to merge."""
        ams = _get(_get(message, "print"), "ams")
        if not isinstance(ams, dict):
            return False
        units = ams.get("ams")
        if isinstance(units, list):
            self._apply_units(units)
        bits = _exist_bits(ams.get("tray_exist_bits"))
        if bits is not None:
            for key in list(self._trays):
                ams_index, tray_index = key
                if not bits >> _exist_bit(ams_index, tray_index) & 1:
                    self._trays[key] = {}
        return True

    def trays(self) -> list[TrayReport]:
        return [_report(key, fields) for key, fields in sorted(self._trays.items())]

    def _apply_units(self, units: list[Any]) -> None:
        present: set[int] = set()
        for unit in units[: AMS_UNITS + HT_UNITS]:
            ams_index = _unit_index(_get(unit, "id"))
            trays = _get(unit, "tray")
            if ams_index is None or not isinstance(trays, list):
                continue
            present.add(ams_index)
            slots = 1 if is_ht(ams_index) else TRAYS_PER_UNIT
            for tray in trays[:slots]:
                tray_index = _index(_get(tray, "id"), slots)
                if tray_index is None:
                    continue
                key = (ams_index, tray_index)
                fields = {k: v for k, v in tray.items() if k in TRAY_FIELDS}
                if not fields:
                    # Only an id: nothing is loaded in this slot.
                    self._trays[key] = {}
                else:
                    self._trays.setdefault(key, {}).update(fields)
        # The unit list is complete when present, so units missing from it were removed.
        for key in [k for k in self._trays if k[0] not in present]:
            del self._trays[key]


def _get(value: object, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else None


def _index(value: object, limit: int) -> int | None:
    number = _int(value)
    return number if number is not None and 0 <= number < limit else None


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d{1,6}", value.strip()):
        return int(value)
    return None


def _exist_bits(value: object) -> int | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9A-Fa-f]{1,16}", value):
        return int(value, 16)
    return None


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= limit else None


def _uuid(value: object) -> str | None:
    if not isinstance(value, str) or not HEX_UUID.match(value) or not value.strip("0"):
        return None
    return value.upper()


def _color(value: object) -> str | None:
    if not isinstance(value, str) or not HEX_COLOR.match(value):
        return None
    return value.upper() if len(value) == 8 else value.upper() + "FF"


def _remaining(value: object) -> int | None:
    number = _int(value)
    # -1 means the AMS does not know (for example, a spool without a Bambu tag).
    return number if number is not None and 0 <= number <= 100 else None


def _report(key: tuple[int, int], fields: dict[str, Any]) -> TrayReport:
    return TrayReport(
        ams_index=key[0],
        tray_index=key[1],
        tray_uuid=_uuid(fields.get("tray_uuid")),
        material_id=_text(fields.get("tray_info_idx"), 16),
        filament_type=_text(fields.get("tray_type"), 32),
        sub_brand=_text(fields.get("tray_sub_brands"), 64),
        color_rgba=_color(fields.get("tray_color")),
        remaining_pct=_remaining(fields.get("remain")),
    )
