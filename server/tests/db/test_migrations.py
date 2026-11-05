from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect

from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.migrate import downgrade, upgrade
from filament_tracker.db.models import Base

TABLES = {"product", "spool", "tag", "event", "device", "printer"}


def test_upgrade_creates_every_table(engine: Engine) -> None:
    assert TABLES <= set(inspect(engine).get_table_names())


def test_migrations_match_the_models(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_upgrade_is_safe_to_run_twice(engine: Engine, db_url: str) -> None:
    upgrade(db_url)

    assert TABLES <= set(inspect(engine).get_table_names())


def test_downgrade_removes_every_table(db_url: str) -> None:
    upgrade(db_url)
    downgrade(db_url, "base")

    engine = create_db_engine(db_url)
    assert not TABLES & set(inspect(engine).get_table_names())
    engine.dispose()
