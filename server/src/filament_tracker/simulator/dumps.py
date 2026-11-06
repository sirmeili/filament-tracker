"""Read saved tag dumps.

Supported: a BambuTagScanner export (the ZIP its Export button shares) or the bare `.bin`
inside it, which is a 1024-byte image of the whole tag in Proxmark3 layout, sector
trailers included. The trailers hold the tag's keys, so they are dropped here and never
sent anywhere. Key files in the ZIP (`-key.bin`, `.dic`) are ignored.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

from filament_tracker.decoder.blocks import IMAGE_SIZE, strip_trailers


class DumpError(ValueError):
    """The file is not a usable tag dump."""


@dataclass(frozen=True)
class Dump:
    name: str
    tag_uid: str
    blocks: list[str]


def load_dump(path: Path) -> Dump:
    """Load a `.bin` image or a BambuTagScanner ZIP export."""
    return from_image(*load_image(path))


def load_image(path: Path) -> tuple[str, bytes]:
    """The full tag image, sector trailers (and so keys) included, and its name."""
    if not path.is_file():
        raise DumpError("not a file")
    if zipfile.is_zipfile(path):
        return _image_from_zip(path)
    if path.stat().st_size != IMAGE_SIZE:
        raise DumpError(f"must be a {IMAGE_SIZE}-byte tag image")
    return path.name, path.read_bytes()


def from_image(name: str, image: bytes) -> Dump:
    """Turn a full tag image into the data a scanner would send."""
    try:
        blocks = strip_trailers(image)
    except ValueError as exc:
        raise DumpError(str(exc)) from exc
    return Dump(
        name=name, tag_uid=blocks[0][:4].hex().upper(), blocks=[b.hex().upper() for b in blocks]
    )


def _image_from_zip(path: Path) -> tuple[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        dumps = [
            info
            for info in archive.infolist()
            if info.filename.lower().endswith(".bin")
            and not info.filename.lower().endswith("-key.bin")
            and not info.is_dir()
        ]
        if len(dumps) != 1:
            raise DumpError(f"must contain exactly one tag dump, found {len(dumps)}")
        info = dumps[0]
        # Check the declared size before reading, so a bad archive cannot fill memory.
        if info.file_size != IMAGE_SIZE:
            raise DumpError(f"the dump inside must be a {IMAGE_SIZE}-byte tag image")
        return Path(info.filename).name, archive.read(info)
