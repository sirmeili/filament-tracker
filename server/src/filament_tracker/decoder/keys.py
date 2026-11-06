"""Bambu tag sector keys.

Each of a tag's 16 sector keys (key A) is derived from its 4-byte UID with HKDF-SHA256,
using the published key-derivation constant as the salt and "RFID-A\0" as the info. The
constant is configuration (`BAMBU_KDF_SALT`), never part of the repo. The server derives
keys only to check that constant against a saved dump; it never sends or logs them.
"""

import hashlib
import hmac

from filament_tracker.decoder.blocks import BLOCK_SIZE, BLOCKS_PER_SECTOR, IMAGE_SIZE

SECTORS = 16
KEY_SIZE = 6
INFO_KEY_A = b"RFID-A\x00"


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """HKDF (RFC 5869) with SHA-256."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out, block = b"", b""
    counter = 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def sector_keys(uid: bytes, salt: bytes) -> list[bytes]:
    """The 16 key A values for a tag with this UID."""
    material = hkdf_sha256(uid, salt, INFO_KEY_A, SECTORS * KEY_SIZE)
    return [material[i * KEY_SIZE : (i + 1) * KEY_SIZE] for i in range(SECTORS)]


def matching_keys(image: bytes, salt: bytes) -> int:
    """How many of a full tag image's trailer keys (key A) the salt reproduces."""
    if len(image) != IMAGE_SIZE:
        raise ValueError(f"tag image must be {IMAGE_SIZE} bytes, got {len(image)}")
    keys = sector_keys(image[:4], salt)
    matched = 0
    for sector, key in enumerate(keys):
        start = (sector * BLOCKS_PER_SECTOR + BLOCKS_PER_SECTOR - 1) * BLOCK_SIZE
        matched += hmac.compare_digest(image[start : start + KEY_SIZE], key)
    return matched
