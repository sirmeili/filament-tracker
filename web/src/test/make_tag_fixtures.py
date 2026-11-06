"""Write src/test/tags.json: synthetic tags and what the server's decoder reads from them,
so the phone's offline decoder can be checked against it. No real tag data.

Run from web/: uv run --project ../server python src/test/make_tag_fixtures.py
"""

import json
from pathlib import Path

from filament_tracker.decoder.decode import DecodeError, decode
from filament_tracker.decoder.synthetic import SyntheticTag

CASES = [
    {"name": "black PLA Basic"},
    {
        "name": "PETG HF gray",
        "material_id": "GFG02",
        "variant_id": "G02-D00",
        "filament_type": "PETG",
        "detailed_filament_type": "PETG HF",
        "color_rgba": "515151FF",
    },
    {"name": "no detailed type", "detailed_filament_type": "", "color_rgba": "FF6A13FF"},
    {"name": "no material ID", "material_id": ""},
    {"name": "no tray UID", "tray_uid": bytes(16)},
]


def main() -> None:
    out = []
    for number, case in enumerate(CASES, start=1):
        fields = {k: v for k, v in case.items() if k != "name"}
        tag = SyntheticTag(
            tag_uid=bytes([number, 2, 3, 4]),
            tray_uid=fields.pop("tray_uid", bytes([number]) * 16),
            filler=bytes([number * 7 % 256]) * 395,
            **fields,
        )
        blocks = tag.data_blocks()
        try:
            record = decode(blocks)
            expected = {
                "materialId": record.material_id,
                "variantId": record.variant_id,
                "filamentType": record.filament_type,
                "detailedType": record.detailed_filament_type,
                "colorRgba": record.color_rgba,
                "trayUid": record.tray_uid,
            }
        except DecodeError:
            expected = None
        out.append({"name": case["name"], "blocks": blocks, "expected": expected})
    path = Path(__file__).parent / "tags.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
