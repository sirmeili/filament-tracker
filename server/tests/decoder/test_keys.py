import pytest

from filament_tracker.decoder.keys import hkdf_sha256, matching_keys, sector_keys
from filament_tracker.decoder.synthetic import SyntheticTag

# A made-up salt: the real constant is configuration and never in the repo.
SALT = bytes(range(16))


def test_hkdf_matches_rfc_5869_test_case_1() -> None:
    okm = hkdf_sha256(
        bytes.fromhex("0b" * 22),
        bytes.fromhex("000102030405060708090a0b0c"),
        bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
        42,
    )

    assert okm.hex() == (
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    )


def test_sector_keys_are_16_six_byte_keys_from_the_uid() -> None:
    keys = sector_keys(b"\x01\x02\x03\x04", SALT)

    assert len(keys) == 16
    assert all(len(key) == 6 for key in keys)
    assert len(set(keys)) == 16
    assert keys == sector_keys(b"\x01\x02\x03\x04", SALT)
    assert keys != sector_keys(b"\x01\x02\x03\x05", SALT)
    assert keys != sector_keys(b"\x01\x02\x03\x04", bytes(16))


def test_matching_keys_counts_the_trailers_the_salt_reproduces() -> None:
    tag = SyntheticTag()
    image = tag.image(salt=SALT)

    assert matching_keys(image, SALT) == 16
    assert matching_keys(image, bytes(16)) == 0
    assert matching_keys(tag.image(), SALT) == 0
    assert tag.image(salt=SALT)[:48] == tag.image()[:48]  # only the trailers differ


def test_matching_keys_needs_a_full_image() -> None:
    with pytest.raises(ValueError, match="1024 bytes"):
        matching_keys(b"\x00" * 10, SALT)
