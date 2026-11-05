import json
import struct
from datetime import datetime

import pytest

from filament_tracker.decoder import (
    DECODER_VERSION,
    DecodeError,
    ProductKey,
    decode,
    decode_bytes,
)
from filament_tracker.decoder.blocks import data_index
from filament_tracker.decoder.synthetic import SyntheticTag


def _with_block(blocks: list[str], absolute: int, raw: bytes) -> list[str]:
    changed = list(blocks)
    changed[data_index(absolute)] = raw.hex()
    return changed


def test_every_field_is_decoded() -> None:
    tag = SyntheticTag(
        tag_uid=bytes.fromhex("A1B2C3D4"),
        tray_uid=bytes.fromhex("00112233445566778899AABBCCDDEEFF"),
        variant_id="A50-K0",
        material_id="GFA50",
        filament_type="PLA",
        detailed_filament_type="PLA Matte",
        color_rgba="FF8800FF",
        second_color_rgba="11223344",
        spool_weight_g=500,
        filament_diameter_mm=1.75,
        nozzle_diameter_mm=0.4,
        spool_width_mm=66.25,
        filament_length_m=165,
        drying_temp_c=55,
        drying_time_h=8,
        bed_temp_type=1,
        bed_temp_c=45,
        max_hotend_temp_c=230,
        min_hotend_temp_c=190,
        production_date=datetime(2026, 1, 2, 3, 4),
    )

    record = decode(tag.data_blocks())

    assert record.decoder_version == DECODER_VERSION
    assert record.tag_uid == "A1B2C3D4"
    assert record.tray_uid == "00112233445566778899AABBCCDDEEFF"
    assert record.variant_id == "A50-K0"
    assert record.material_id == "GFA50"
    assert record.filament_type == "PLA"
    assert record.detailed_filament_type == "PLA Matte"
    assert record.color_rgba == "FF8800FF"
    assert record.second_color_rgba == "11223344"
    assert record.spool_weight_g == 500
    assert record.filament_diameter_mm == 1.75
    assert record.nozzle_diameter_mm == 0.4
    assert record.spool_width_mm == 66.25
    assert record.filament_length_m == 165
    assert record.drying_temp_c == 55
    assert record.drying_time_h == 8
    assert record.bed_temp_type == 1
    assert record.bed_temp_c == 45
    assert record.max_hotend_temp_c == 230
    assert record.min_hotend_temp_c == 190
    assert record.production_date == datetime(2026, 1, 2, 3, 4)


def test_lowercase_hex_is_accepted() -> None:
    blocks = [b.lower() for b in SyntheticTag(tag_uid=bytes.fromhex("0a0b0c0d")).data_blocks()]

    assert decode(blocks).tag_uid == "0A0B0C0D"


def test_two_rolls_of_one_product_share_a_product_key_but_not_a_tray_uid() -> None:
    first = decode(SyntheticTag().data_blocks())
    second = decode(SyntheticTag().data_blocks())

    assert first.product_key == second.product_key
    assert first.tray_uid != second.tray_uid
    assert first.tag_uid != second.tag_uid


def test_different_colors_are_different_products() -> None:
    black = decode(SyntheticTag(color_rgba="000000FF").data_blocks())
    white = decode(SyntheticTag(color_rgba="FFFFFFFF").data_blocks())

    assert black.product_key != white.product_key


def test_product_key_fields() -> None:
    record = decode(SyntheticTag().data_blocks())

    assert record.product_key == ProductKey("GFA00", "A00-K0", "000000FF")


def test_decoding_is_pure() -> None:
    blocks = SyntheticTag().data_blocks()

    assert decode(blocks) == decode(blocks)


def test_strings_stop_at_the_first_nul_and_are_trimmed() -> None:
    blocks = _with_block(SyntheticTag().data_blocks(), 4, b" PLA Silk \x00junk\x00")

    assert decode(blocks).detailed_filament_type == "PLA Silk"


def test_non_ascii_bytes_do_not_break_decoding() -> None:
    blocks = _with_block(SyntheticTag().data_blocks(), 2, b"PL\xffA".ljust(16, b"\x00"))

    assert decode(blocks).filament_type == "PL�A"


def test_single_color_tags_have_no_second_color() -> None:
    assert decode(SyntheticTag().data_blocks()).second_color_rgba is None


def test_unusable_optional_fields_become_none() -> None:
    tag = SyntheticTag()
    blocks = tag.data_blocks()
    nan = struct.pack("<f", float("nan"))
    blocks = _with_block(blocks, 5, bytes.fromhex("000000FF") + bytes(4) + nan + bytes(4))
    blocks = _with_block(blocks, 8, bytes(16))
    blocks = _with_block(blocks, 10, bytes(16))
    blocks = _with_block(blocks, 12, b"not a date".ljust(16, b"\x00"))
    blocks = _with_block(blocks, 14, bytes(16))

    record = decode(blocks)

    assert record.filament_diameter_mm is None
    assert record.nozzle_diameter_mm is None
    assert record.spool_width_mm is None
    assert record.production_date is None
    assert record.filament_length_m is None


def test_to_json_dict_is_json_safe() -> None:
    record = decode(SyntheticTag(production_date=datetime(2026, 5, 6, 7, 8)).data_blocks())

    data = json.loads(json.dumps(record.to_json_dict()))

    assert data["production_date"] == "2026-05-06T07:08:00"
    assert data["tray_uid"] == record.tray_uid


def test_to_json_dict_without_production_date() -> None:
    blocks = _with_block(SyntheticTag().data_blocks(), 12, bytes(16))

    assert decode(blocks).to_json_dict()["production_date"] is None


def test_decode_bytes_accepts_raw_blocks() -> None:
    blocks = [bytes.fromhex(b) for b in SyntheticTag().data_blocks()]

    assert decode_bytes(blocks).material_id == "GFA00"


@pytest.mark.parametrize("count", [0, 47, 49, 64])
def test_wrong_block_count_is_rejected(count: int) -> None:
    with pytest.raises(DecodeError, match="48 data blocks"):
        decode(["00" * 16] * count)


def test_non_hex_block_is_rejected() -> None:
    blocks = SyntheticTag().data_blocks()
    blocks[5] = "zz" * 16

    with pytest.raises(DecodeError, match="not hex"):
        decode(blocks)


@pytest.mark.parametrize("raw", ["00" * 15, "00" * 17])
def test_wrong_block_length_is_rejected(raw: str) -> None:
    blocks = SyntheticTag().data_blocks()
    blocks[5] = raw

    with pytest.raises(DecodeError, match="16 bytes"):
        decode(blocks)


def test_decode_bytes_rejects_wrong_shapes() -> None:
    with pytest.raises(DecodeError):
        decode_bytes([bytes(16)] * 47)
    with pytest.raises(DecodeError):
        decode_bytes([bytes(15)] * 48)


def test_a_blank_tag_is_rejected() -> None:
    with pytest.raises(DecodeError, match="material ID"):
        decode(["00" * 16] * 48)


def test_a_tag_without_a_tray_uid_is_rejected() -> None:
    blocks = _with_block(SyntheticTag().data_blocks(), 9, bytes(16))

    with pytest.raises(DecodeError, match="tray UID"):
        decode(blocks)
