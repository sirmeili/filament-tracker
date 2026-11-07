"""Encryption for secrets saved in the app (see Settings and first start in docs/SPEC.md).

Each value is sealed with AES-256-GCM under its own random nonce, with the setting's name
as associated data, so a sealed value cannot be moved to another setting. The key comes
from SETTINGS_KEY, or else from a key file beside the database, created on first start
and readable only by the server's user.

Nothing here logs a value or a key, and errors never include either.
"""

import base64
import binascii
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr
from sqlalchemy.engine import make_url

KEY_BYTES = 32
NONCE_BYTES = 12
PREFIX = "v1:"
KEY_FILE = "settings.key"


class SettingsKeyError(ValueError):
    """SETTINGS_KEY or the key file is not a usable key. The message never holds it."""


class Unreadable(Exception):
    """A sealed value that this key cannot open: the key changed, or it was tampered with."""


def parse_key(text: str) -> bytes:
    """A base64 key of exactly 32 bytes."""
    try:
        key = base64.b64decode(text.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise SettingsKeyError("SETTINGS_KEY must be 32 random bytes in base64") from None
    if len(key) != KEY_BYTES:
        raise SettingsKeyError("SETTINGS_KEY must be 32 random bytes in base64")
    return key


def new_key_text() -> str:
    return base64.b64encode(secrets.token_bytes(KEY_BYTES)).decode()


def key_file_for(database_url: str) -> Path | None:
    """settings.key beside a SQLite database file; None for an in-memory database."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None
    return Path(url.database).parent / KEY_FILE


def read_or_create_key_file(path: Path) -> bytes:
    """Read the key file, or create it with a new key, readable only by this user."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass  # another process made it first; read theirs
        else:
            with os.fdopen(fd, "w") as file:
                file.write(new_key_text() + "\n")
    try:
        return parse_key(path.read_text())
    except SettingsKeyError:
        raise SettingsKeyError(f"{path.name} does not hold a usable key") from None


def load_key(settings_key: SecretStr | None, database_url: str) -> bytes:
    """The key from SETTINGS_KEY, else from the key file, else (in memory) a key that
    lasts only as long as the process."""
    if settings_key is not None and settings_key.get_secret_value().strip():
        return parse_key(settings_key.get_secret_value())
    path = key_file_for(database_url)
    if path is None:
        return secrets.token_bytes(KEY_BYTES)
    return read_or_create_key_file(path)


class SecretBox:
    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise SettingsKeyError("the settings key must be 32 bytes")
        self._aead = AESGCM(key)

    def seal(self, name: str, value: str) -> str:
        nonce = secrets.token_bytes(NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, value.encode(), name.encode())
        return PREFIX + base64.b64encode(nonce + sealed).decode()

    def open(self, name: str, sealed: str) -> str:
        if not sealed.startswith(PREFIX):
            raise Unreadable
        try:
            raw = base64.b64decode(sealed[len(PREFIX) :], validate=True)
            nonce, body = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
            if len(nonce) != NONCE_BYTES:
                raise Unreadable
            return self._aead.decrypt(nonce, body, name.encode()).decode()
        except (binascii.Error, ValueError, InvalidTag, UnicodeDecodeError):
            raise Unreadable from None
