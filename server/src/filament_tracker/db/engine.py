"""Database engine and sessions.

SQLite connections get write-ahead logging (so readers do not block the writer), foreign
key enforcement and a busy timeout, as the spec's stack calls for.
"""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

BUSY_TIMEOUT_MS = 5000


def create_db_engine(url: str) -> Engine:
    """Create an engine; for a SQLite file, create its folder and set the pragmas."""
    parsed = make_url(url)
    is_sqlite = parsed.get_backend_name() == "sqlite"
    in_memory = is_sqlite and parsed.database in (None, "", ":memory:")
    if is_sqlite and not in_memory:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            if not in_memory:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
