import base64
import os
import stat
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from filament_tracker.app_settings.crypto import (
    KEY_FILE,
    SecretBox,
    SettingsKeyError,
    Unreadable,
    key_file_for,
    load_key,
    new_key_text,
    parse_key,
    read_or_create_key_file,
)

KEY = bytes(range(32))


def test_a_sealed_value_opens_with_its_name() -> None:
    box = SecretBox(KEY)
    sealed = box.seal("ha_token", "secret-value")

    assert "secret-value" not in sealed
    assert sealed.startswith("v1:")
    assert box.open("ha_token", sealed) == "secret-value"


def test_each_seal_uses_a_new_nonce() -> None:
    box = SecretBox(KEY)
    assert box.seal("ha_token", "x") != box.seal("ha_token", "x")


def test_a_value_cannot_move_to_another_setting() -> None:
    box = SecretBox(KEY)
    sealed = box.seal("ha_token", "secret-value")
    with pytest.raises(Unreadable):
        box.open("mqtt_password", sealed)


def test_another_key_cannot_open_it() -> None:
    sealed = SecretBox(KEY).seal("ha_token", "secret-value")
    with pytest.raises(Unreadable):
        SecretBox(bytes(32)).open("ha_token", sealed)


@pytest.mark.parametrize(
    "sealed",
    ["plain", "v1:not base64!", "v1:" + base64.b64encode(b"short").decode()],
)
def test_garbage_is_unreadable(sealed: str) -> None:
    with pytest.raises(Unreadable):
        SecretBox(KEY).open("ha_token", sealed)


def test_a_changed_value_is_unreadable() -> None:
    box = SecretBox(KEY)
    raw = bytearray(base64.b64decode(box.seal("ha_token", "secret-value")[3:]))
    raw[-1] ^= 1
    with pytest.raises(Unreadable):
        box.open("ha_token", "v1:" + base64.b64encode(bytes(raw)).decode())


def test_keys_must_be_32_bytes_of_base64() -> None:
    assert parse_key(base64.b64encode(KEY).decode()) == KEY
    assert len(parse_key(new_key_text())) == 32
    for bad in ("not base64!", base64.b64encode(b"short").decode()):
        with pytest.raises(SettingsKeyError) as error:
            parse_key(bad)
        assert bad not in str(error.value)
    with pytest.raises(SettingsKeyError):
        SecretBox(b"short")


def test_the_key_file_sits_beside_the_database(tmp_path: Path) -> None:
    assert key_file_for(f"sqlite:///{tmp_path}/data/filament.db") == tmp_path / "data" / KEY_FILE
    assert key_file_for("sqlite://") is None
    assert key_file_for("sqlite:///:memory:") is None
    assert key_file_for("postgresql://db/filament") is None


def test_settings_key_wins_over_the_key_file(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path}/filament.db"
    assert load_key(SecretStr(base64.b64encode(KEY).decode()), url) == KEY
    assert not (tmp_path / KEY_FILE).exists()


def test_the_key_file_is_made_once_and_kept(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path}/data/filament.db"
    first = load_key(None, url)
    second = load_key(SecretStr("  "), url)  # blank SETTINGS_KEY: the file
    assert first == second
    assert (tmp_path / "data" / KEY_FILE).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_only_the_server_user_can_read_the_key_file(tmp_path: Path) -> None:
    path = tmp_path / KEY_FILE
    read_or_create_key_file(path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_a_bad_key_file_is_refused_without_showing_it(tmp_path: Path) -> None:
    path = tmp_path / KEY_FILE
    path.write_text("garbage-key-text")
    with pytest.raises(SettingsKeyError) as error:
        read_or_create_key_file(path)
    assert "garbage-key-text" not in str(error.value)


def test_an_in_memory_database_gets_a_key_for_this_run() -> None:
    assert load_key(None, "sqlite://") != load_key(None, "sqlite://")
