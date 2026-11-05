import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.services import accounts


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database migrated once per test run; each test gets a copy (much faster than
    migrating every test's database from scratch)."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    upgrade(f"sqlite:///{path}")
    return path


@pytest.fixture
def db_url(tmp_path: Path, migrated_template: Path) -> str:
    """A fresh database, already migrated to the latest revision."""
    path = tmp_path / "test.db"
    with sqlite3.connect(migrated_template) as source, sqlite3.connect(path) as target:
        source.backup(target)
    source.close()
    target.close()
    return f"sqlite:///{path}"


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    upgrade(db_url)
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with create_session_factory(engine)() as session:
        yield session


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cheap Argon2 parameters in tests; production keeps the library's defaults."""
    fast = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    monkeypatch.setattr(accounts, "_hasher", fast)
    monkeypatch.setattr(accounts, "_DUMMY_HASH", fast.hash("dummy"))
