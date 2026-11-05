from pathlib import Path

from sqlalchemy import Engine, text

from filament_tracker.db.engine import BUSY_TIMEOUT_MS, create_db_engine


def _pragma(engine: Engine, name: str) -> object:
    with engine.connect() as connection:
        return connection.execute(text(f"PRAGMA {name}")).scalar()


def test_file_database_uses_wal_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'a.db'}")

    assert _pragma(engine, "journal_mode") == "wal"
    assert _pragma(engine, "foreign_keys") == 1
    assert _pragma(engine, "busy_timeout") == BUSY_TIMEOUT_MS
    engine.dispose()


def test_missing_database_folder_is_created(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "folder" / "a.db"

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect():
        pass

    assert path.exists()
    engine.dispose()


def test_in_memory_database_skips_wal_but_enforces_foreign_keys() -> None:
    engine = create_db_engine("sqlite://")

    assert _pragma(engine, "journal_mode") == "memory"
    assert _pragma(engine, "foreign_keys") == 1
    engine.dispose()
