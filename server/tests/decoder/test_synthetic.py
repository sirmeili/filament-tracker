import pytest

from filament_tracker.decoder.blocks import IMAGE_SIZE, is_trailer
from filament_tracker.decoder.synthetic import SyntheticTag


def test_image_is_a_full_1k_tag_with_trailers() -> None:
    image = SyntheticTag().image()

    assert len(image) == IMAGE_SIZE
    for n in range(64):
        if is_trailer(n):
            assert image[n * 16 + 6 : n * 16 + 10] == bytes.fromhex("87878769")


def test_block_zero_holds_uid_and_check_byte() -> None:
    image = SyntheticTag(tag_uid=bytes.fromhex("01020408")).image()

    assert image[0:5] == bytes.fromhex("010204080F")


def test_data_blocks_are_48_uppercase_hex_strings() -> None:
    blocks = SyntheticTag().data_blocks()

    assert len(blocks) == 48
    assert all(len(b) == 32 and b == b.upper() for b in blocks)


def test_each_generated_tag_has_new_random_identity() -> None:
    first, second = SyntheticTag(), SyntheticTag()

    assert first.tag_uid != second.tag_uid
    assert first.tray_uid != second.tray_uid


def test_a_tag_reads_the_same_every_time() -> None:
    tag = SyntheticTag()

    assert tag.image() == tag.image()
    assert tag.data_blocks() == tag.data_blocks()


def test_text_that_does_not_fit_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not fit"):
        SyntheticTag(variant_id="TOO-LONG-ID").image()
