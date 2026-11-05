"""Decode Bambu Lab tag blocks into a TagRecord.

Field offsets follow the Bambu Research Group RFID Tag Guide (BambuLabRfid.md). All
numbers are little-endian. Decoding is pure: the same blocks always give the same record.
"""

import math
import struct
from collections.abc import Sequence
from datetime import datetime

from filament_tracker.decoder.blocks import BLOCK_SIZE, DATA_BLOCK_COUNT, data_index
from filament_tracker.decoder.record import TagRecord

DECODER_VERSION = 1

_SECOND_COLOR_FORMAT = 2


class DecodeError(ValueError):
    """The blocks are not a readable Bambu Lab tag."""


def parse_hex_blocks(blocks: Sequence[str]) -> list[bytes]:
    """Turn hex strings into 16-byte blocks, checking count and length."""
    if len(blocks) != DATA_BLOCK_COUNT:
        raise DecodeError(f"expected {DATA_BLOCK_COUNT} data blocks, got {len(blocks)}")
    parsed = []
    for n, text in enumerate(blocks):
        try:
            raw = bytes.fromhex(text)
        except ValueError as exc:
            raise DecodeError(f"data block {n} is not hex") from exc
        if len(raw) != BLOCK_SIZE:
            raise DecodeError(f"data block {n} must be {BLOCK_SIZE} bytes, got {len(raw)}")
        parsed.append(raw)
    return parsed


def decode(blocks: Sequence[str]) -> TagRecord:
    """Decode 48 hex data blocks (sector trailers removed) into a TagRecord."""
    return decode_bytes(parse_hex_blocks(blocks))


def decode_bytes(blocks: Sequence[bytes]) -> TagRecord:
    """Decode 48 data blocks of 16 bytes each into a TagRecord."""
    if len(blocks) != DATA_BLOCK_COUNT or any(len(b) != BLOCK_SIZE for b in blocks):
        raise DecodeError(f"expected {DATA_BLOCK_COUNT} blocks of {BLOCK_SIZE} bytes")

    def block(absolute: int) -> bytes:
        return blocks[data_index(absolute)]

    material_variant = block(1)
    variant_id = _text(material_variant[0:8])
    material_id = _text(material_variant[8:16])
    if not material_id:
        raise DecodeError("tag has no material ID")

    tray = block(9)
    if not any(tray):
        raise DecodeError("tag has no tray UID")

    b5, b6, b8, b10, b14, b16 = block(5), block(6), block(8), block(10), block(14), block(16)
    temps = struct.unpack_from("<6H", b6, 0)

    return TagRecord(
        decoder_version=DECODER_VERSION,
        tag_uid=block(0)[0:4].hex().upper(),
        tray_uid=tray.hex().upper(),
        material_id=material_id,
        variant_id=variant_id,
        filament_type=_text(block(2)),
        detailed_filament_type=_text(block(4)),
        color_rgba=b5[0:4].hex().upper(),
        second_color_rgba=_second_color(b16),
        spool_weight_g=_u16(b5, 4),
        filament_diameter_mm=_float(b5, 8),
        nozzle_diameter_mm=_float(b8, 12),
        spool_width_mm=_u16(b10, 4) / 100 or None,
        filament_length_m=_u16(b14, 4) or None,
        drying_temp_c=temps[0],
        drying_time_h=temps[1],
        bed_temp_type=temps[2],
        bed_temp_c=temps[3],
        max_hotend_temp_c=temps[4],
        min_hotend_temp_c=temps[5],
        production_date=_production_date(block(12)),
    )


def _text(raw: bytes) -> str:
    """Read a NUL-padded ASCII string."""
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def _u16(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def _float(raw: bytes, offset: int) -> float | None:
    value = struct.unpack_from("<f", raw, offset)[0]
    if not math.isfinite(value) or value <= 0:
        return None
    return round(value, 3)


def _second_color(raw: bytes) -> str | None:
    if _u16(raw, 0) != _SECOND_COLOR_FORMAT:
        return None
    # Stored as ABGR; reversing the bytes gives RGBA.
    return raw[4:8][::-1].hex().upper()


def _production_date(raw: bytes) -> datetime | None:
    try:
        return datetime.strptime(_text(raw), "%Y_%m_%d_%H_%M")
    except ValueError:
        return None
