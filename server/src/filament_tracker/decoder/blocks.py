"""MIFARE Classic 1K block layout.

A 1K tag has 16 sectors of 4 blocks of 16 bytes. The last block of each sector is the
sector trailer, which holds the keys. Scanners send only the 48 data blocks, in absolute
order with the trailers removed, so absolute block 4 is data index 3.
"""

BLOCK_SIZE = 16
BLOCKS_PER_SECTOR = 4
TOTAL_BLOCKS = 64
DATA_BLOCK_COUNT = TOTAL_BLOCKS - TOTAL_BLOCKS // BLOCKS_PER_SECTOR
IMAGE_SIZE = TOTAL_BLOCKS * BLOCK_SIZE


def is_trailer(absolute: int) -> bool:
    """Return True if the absolute block number is a sector trailer."""
    return absolute % BLOCKS_PER_SECTOR == BLOCKS_PER_SECTOR - 1


def data_index(absolute: int) -> int:
    """Map an absolute block number to its index in the data-block array."""
    if not 0 <= absolute < TOTAL_BLOCKS:
        raise ValueError(f"block {absolute} is outside the tag")
    if is_trailer(absolute):
        raise ValueError(f"block {absolute} is a sector trailer")
    return absolute - absolute // BLOCKS_PER_SECTOR


def absolute_block(index: int) -> int:
    """Map an index in the data-block array back to its absolute block number."""
    if not 0 <= index < DATA_BLOCK_COUNT:
        raise ValueError(f"data index {index} is outside the tag")
    return index + index // (BLOCKS_PER_SECTOR - 1)


def strip_trailers(image: bytes) -> list[bytes]:
    """Split a full 1K tag image into its 48 data blocks, dropping the sector trailers."""
    if len(image) != IMAGE_SIZE:
        raise ValueError(f"tag image must be {IMAGE_SIZE} bytes, got {len(image)}")
    return [
        image[n * BLOCK_SIZE : (n + 1) * BLOCK_SIZE]
        for n in range(TOTAL_BLOCKS)
        if not is_trailer(n)
    ]
