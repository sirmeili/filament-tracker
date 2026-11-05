import pytest

from filament_tracker.decoder.blocks import (
    DATA_BLOCK_COUNT,
    IMAGE_SIZE,
    absolute_block,
    data_index,
    is_trailer,
    strip_trailers,
)


def test_a_1k_tag_has_48_data_blocks() -> None:
    assert DATA_BLOCK_COUNT == 48
    assert IMAGE_SIZE == 1024


@pytest.mark.parametrize("absolute", [3, 7, 11, 39, 63])
def test_sector_trailers_are_detected(absolute: int) -> None:
    assert is_trailer(absolute)


@pytest.mark.parametrize(("absolute", "index"), [(0, 0), (2, 2), (4, 3), (9, 7), (62, 47)])
def test_data_index_skips_trailers(absolute: int, index: int) -> None:
    assert data_index(absolute) == index
    assert absolute_block(index) == absolute


def test_every_data_index_round_trips() -> None:
    for index in range(DATA_BLOCK_COUNT):
        assert data_index(absolute_block(index)) == index


@pytest.mark.parametrize("absolute", [-1, 3, 64])
def test_data_index_rejects_trailers_and_out_of_range(absolute: int) -> None:
    with pytest.raises(ValueError):
        data_index(absolute)


@pytest.mark.parametrize("index", [-1, 48])
def test_absolute_block_rejects_out_of_range(index: int) -> None:
    with pytest.raises(ValueError):
        absolute_block(index)


def test_strip_trailers_keeps_data_blocks_in_order() -> None:
    image = b"".join(bytes([n]) * 16 for n in range(64))

    blocks = strip_trailers(image)

    assert len(blocks) == 48
    assert [b[0] for b in blocks] == [n for n in range(64) if n % 4 != 3]


@pytest.mark.parametrize("size", [0, 1023, 1025, 4096])
def test_strip_trailers_rejects_wrong_sizes(size: int) -> None:
    with pytest.raises(ValueError):
        strip_trailers(bytes(size))
