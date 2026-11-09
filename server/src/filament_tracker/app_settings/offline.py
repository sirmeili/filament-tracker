"""The settings in use, for command-line tools that run beside the server (`ft-ha check`,
`ft-sim check-salt`, `ft-printer check`): a value saved in the app wins over `.env`, as in
the server.

The server's database and key are only read. Nothing is created or upgraded, and without
the key, saved secrets count as unreadable.
"""

import secrets
from pathlib import Path

from sqlalchemy import inspect as sql_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import KEY_BYTES, SecretBox, key_file_for, parse_key
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.models import Base


def database_file(url: str) -> Path | None:
    """The SQLite file the server uses, or None for an in-memory database."""
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or parsed.database in (None, "", ":memory:"):
        return None
    return Path(parsed.database)


def read_key(settings: Settings) -> bytes | None:
    """The settings key, read but never created: no key means saved secrets can't be read."""
    if settings.settings_key is not None and settings.settings_key.get_secret_value().strip():
        return parse_key(settings.settings_key.get_secret_value())
    path = key_file_for(settings.database_url)
    if path is None or not path.exists():
        return None
    return parse_key(path.read_text(encoding="utf-8"))


def empty_sessions() -> sessionmaker[Session]:
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def open_database(settings: Settings, table: str = "setting") -> sessionmaker[Session] | None:
    """The server's database, if it exists and has `table` (so it is new enough)."""
    path = database_file(settings.database_url)
    if path is None or not path.exists():
        return None
    engine = create_db_engine(settings.database_url)
    if not sql_inspect(engine).has_table(table):
        return None
    return create_session_factory(engine)


def open_box(settings: Settings) -> SecretBox:
    """The settings key's box; without the key, one that opens nothing saved."""
    key = read_key(settings)
    return SecretBox(key if key is not None else secrets.token_bytes(KEY_BYTES))


def open_store(settings: Settings) -> tuple[SettingsStore, bool]:
    """The settings in use, and whether the server's database was found. Without it, only
    server/.env counts."""
    sessions = open_database(settings)
    store = SettingsStore(settings, sessions or empty_sessions(), open_box(settings))
    return store, sessions is not None
