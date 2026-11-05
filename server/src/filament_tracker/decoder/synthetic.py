"""Generate synthetic Bambu-style tags.

CI and the scan simulator use these instead of real dumps, which hold real UIDs and keys.
UIDs, tray UIDs, trailer keys and signature bytes are random; the product fields are
whatever the caller chooses. The signature is not valid, and nothing here can make a tag
a printer would accept.
"""

import secrets
import struct
from dataclasses import dataclass, field
from datetime import datetime

from filament_tracker.decoder.blocks import (
    BLOCK_SIZE,
    BLOCKS_PER_SECTOR,
    TOTAL_BLOCKS,
    is_trailer,
    strip_trailers,
)

_ACCESS_BITS = bytes.fromhex("87878769")
_SIGNATURE_BLOCKS = range(40, TOTAL_BLOCKS)


@dataclass
class SyntheticTag:
    """Field values for a generated tag. Defaults describe a Black PLA Basic roll."""

    tag_uid: bytes = field(default_factory=lambda: secrets.token_bytes(4))
    tray_uid: bytes = field(default_factory=lambda: secrets.token_bytes(16))
    variant_id: str = "A00-K00"
    material_id: str = "GFA00"
    filament_type: str = "PLA"
    detailed_filament_type: str = "PLA Basic"
    color_rgba: str = "000000FF"
    second_color_rgba: str | None = None
    spool_weight_g: int = 1000
    filament_diameter_mm: float = 1.75
    nozzle_diameter_mm: float = 0.2
    spool_width_mm: float = 66.25
    filament_length_m: int = 330
    drying_temp_c: int = 55
    drying_time_h: int = 8
    bed_temp_type: int = 1
    bed_temp_c: int = 35
    max_hotend_temp_c: int = 230
    min_hotend_temp_c: int = 190
    production_date: datetime = datetime(2026, 9, 14, 8, 30)

    def image(self) -> bytes:
        """Return a full 1024-byte tag image, sector trailers included."""
        blocks = [bytes(BLOCK_SIZE)] * TOTAL_BLOCKS
        blocks[0] = self.tag_uid + _bcc(self.tag_uid) + secrets.token_bytes(11)
        blocks[1] = _pad(self.variant_id, 8) + _pad(self.material_id, 8)
        blocks[2] = _pad(self.filament_type)
        blocks[4] = _pad(self.detailed_filament_type)
        blocks[5] = (
            bytes.fromhex(self.color_rgba)
            + struct.pack("<H", self.spool_weight_g)
            + bytes(2)
            + struct.pack("<f", self.filament_diameter_mm)
            + bytes(4)
        )
        blocks[6] = struct.pack(
            "<6H4x",
            self.drying_temp_c,
            self.drying_time_h,
            self.bed_temp_type,
            self.bed_temp_c,
            self.max_hotend_temp_c,
            self.min_hotend_temp_c,
        )
        blocks[8] = bytes(12) + struct.pack("<f", self.nozzle_diameter_mm)
        blocks[9] = self.tray_uid
        blocks[10] = bytes(4) + struct.pack("<H", round(self.spool_width_mm * 100)) + bytes(10)
        blocks[12] = _pad(self.production_date.strftime("%Y_%m_%d_%H_%M"))
        blocks[14] = bytes(4) + struct.pack("<H", self.filament_length_m) + bytes(10)
        if self.second_color_rgba is not None:
            abgr = bytes.fromhex(self.second_color_rgba)[::-1]
            blocks[16] = struct.pack("<HH", 2, 2) + abgr + bytes(8)
        for n in _SIGNATURE_BLOCKS:
            if not is_trailer(n):
                blocks[n] = secrets.token_bytes(BLOCK_SIZE)
        for n in range(BLOCKS_PER_SECTOR - 1, TOTAL_BLOCKS, BLOCKS_PER_SECTOR):
            blocks[n] = secrets.token_bytes(6) + _ACCESS_BITS + bytes(6)
        return b"".join(blocks)

    def data_blocks(self) -> list[str]:
        """Return the 48 data blocks as hex, as a scanner sends them."""
        return [b.hex().upper() for b in strip_trailers(self.image())]


def _pad(text: str, size: int = BLOCK_SIZE) -> bytes:
    raw = text.encode("ascii")
    if len(raw) > size:
        raise ValueError(f"{text!r} does not fit in {size} bytes")
    return raw.ljust(size, b"\x00")


def _bcc(uid: bytes) -> bytes:
    """Block check character: the XOR of the four UID bytes, as on real tags."""
    return bytes([uid[0] ^ uid[1] ^ uid[2] ^ uid[3]])
