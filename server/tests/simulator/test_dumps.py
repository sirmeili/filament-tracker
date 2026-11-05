import zipfile
from pathlib import Path

import pytest

from filament_tracker.decoder import decode
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.simulator.dumps import DumpError, from_image, load_dump


def _export_zip(path: Path, tag: SyntheticTag, extra: dict[str, bytes] | None = None) -> Path:
    """Build a ZIP shaped like a BambuTagScanner export."""
    stem = f"{tag.tag_uid.hex().upper()}-PLA_Basic-Black"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{stem}.bin", tag.image())
        archive.writestr(f"{stem}-key.bin", bytes(96))
        archive.writestr(f"{stem}.dic", "FFFFFFFFFFFF\n")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def test_a_bin_image_loads_without_its_trailers(tmp_path: Path) -> None:
    tag = SyntheticTag()
    path = tmp_path / "tag.bin"
    path.write_bytes(tag.image())

    dump = load_dump(path)

    assert dump.name == "tag.bin"
    assert dump.tag_uid == tag.tag_uid.hex().upper()
    assert dump.blocks == tag.data_blocks()
    assert len(dump.blocks) == 48


def test_trailer_keys_are_never_in_the_blocks(tmp_path: Path) -> None:
    tag = SyntheticTag()
    image = tag.image()
    keys = {image[n * 16 : n * 16 + 6].hex().upper() for n in range(3, 64, 4)}
    path = tmp_path / "tag.bin"
    path.write_bytes(image)

    joined = "".join(load_dump(path).blocks)

    assert not any(key in joined for key in keys)


def test_a_bambutagscanner_zip_loads_the_dump_and_ignores_key_files(tmp_path: Path) -> None:
    tag = SyntheticTag()

    dump = load_dump(_export_zip(tmp_path / "export.zip", tag))

    assert dump.name.endswith("-PLA_Basic-Black.bin")
    assert dump.blocks == tag.data_blocks()
    assert decode(dump.blocks).tray_uid == tag.tray_uid.hex().upper()


def test_a_zip_with_two_dumps_is_refused(tmp_path: Path) -> None:
    path = _export_zip(tmp_path / "e.zip", SyntheticTag(), {"other.bin": SyntheticTag().image()})

    with pytest.raises(DumpError, match="exactly one"):
        load_dump(path)


def test_a_zip_with_no_dump_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "e.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "nothing here")

    with pytest.raises(DumpError, match="found 0"):
        load_dump(path)


def test_a_wrong_sized_dump_in_a_zip_is_refused_before_reading(tmp_path: Path) -> None:
    path = tmp_path / "e.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("big.bin", bytes(10_000_000))

    with pytest.raises(DumpError, match="1024-byte"):
        load_dump(path)


@pytest.mark.parametrize("size", [0, 1023, 1025, 4096])
def test_a_wrong_sized_bin_is_refused(tmp_path: Path, size: int) -> None:
    path = tmp_path / "tag.bin"
    path.write_bytes(bytes(size))

    with pytest.raises(DumpError, match="1024-byte"):
        load_dump(path)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DumpError, match="not a file"):
        load_dump(tmp_path / "missing.bin")


def test_from_image_checks_the_size() -> None:
    with pytest.raises(DumpError):
        from_image("x", bytes(10))
