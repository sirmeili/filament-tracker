"""Typed result of decoding a Bambu Lab tag."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, NamedTuple


class ProductKey(NamedTuple):
    """Fields shared by every roll of the same product."""

    material_id: str
    variant_id: str
    color_rgba: str


@dataclass(frozen=True)
class TagRecord:
    """Decoded contents of one Bambu Lab tag.

    Hex values are uppercase. Fields the public block map marks as uncertain are
    None when their bytes do not hold a usable value.
    """

    decoder_version: int
    tag_uid: str
    tray_uid: str
    material_id: str
    variant_id: str
    filament_type: str
    detailed_filament_type: str
    color_rgba: str
    second_color_rgba: str | None
    spool_weight_g: int
    filament_diameter_mm: float | None
    nozzle_diameter_mm: float | None
    spool_width_mm: float | None
    filament_length_m: int | None
    drying_temp_c: int
    drying_time_h: int
    bed_temp_type: int
    bed_temp_c: int
    max_hotend_temp_c: int
    min_hotend_temp_c: int
    production_date: datetime | None

    @property
    def product_key(self) -> ProductKey:
        return ProductKey(self.material_id, self.variant_id, self.color_rgba)

    def to_json_dict(self) -> dict[str, Any]:
        """Return the record as JSON-safe values, for storing next to the raw blocks."""
        data = asdict(self)
        if self.production_date is not None:
            data["production_date"] = self.production_date.isoformat()
        return data
