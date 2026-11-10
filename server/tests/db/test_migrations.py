from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.migrate import downgrade, upgrade
from filament_tracker.db.models import Base

TABLES = {"product", "spool", "tag", "event", "device", "printer", "user", "session"}


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


def test_upgrade_from_an_empty_database(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'empty.db'}"

    upgrade(url)

    engine = create_db_engine(url)
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_products_already_made_from_the_ams_are_marked(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade(url, "92998d06ecab")
    engine = create_db_engine(url)
    when = "2026-11-10 12:00:00.000000"
    product = (
        "INSERT INTO product (id, filament_type, color_rgba, display_name,"
        " low_stock_threshold, provisional, created_at) VALUES (:id, 'PETG', '000000FF', :name,"
        " 0, :provisional, :when)"
    )
    spool = (
        "INSERT INTO spool (id, product_id, tray_uid, created_at) VALUES (:id, :p, :tray, :when)"
    )
    event = (
        "INSERT INTO event (id, spool_id, type, source, occurred_at, recorded_at, flagged)"
        " VALUES (:id, :spool, 'opened', :source, :when, :when, 0)"
    )
    with engine.begin() as connection:
        # 1: made by the AMS; 2: by hand, a placeholder opened in the web app;
        # 3: from a tag, later seen by the AMS.
        for id_, name, provisional in [(1, "PETG HF Black", 1), (2, "Hand", 1), (3, "Tag", 0)]:
            connection.execute(
                text(product), {"id": id_, "name": name, "provisional": provisional, "when": when}
            )
        for id_, tray in [(1, "A" * 32), (2, None), (3, "B" * 32)]:
            connection.execute(text(spool), {"id": id_, "p": id_, "tray": tray, "when": when})
        for id_, spool_id, source in [(1, 1, "ams"), (2, 2, "ui"), (3, 3, "ams")]:
            connection.execute(
                text(event),
                {"id": f"{id_:032x}", "spool": spool_id, "source": source, "when": when},
            )
    engine.dispose()

    upgrade(url)

    engine = create_db_engine(url)
    with engine.connect() as connection:
        marked = connection.execute(text("SELECT id, from_ams FROM product ORDER BY id")).all()
    engine.dispose()
    assert [tuple(row) for row in marked] == [(1, 1), (2, 0), (3, 0)]
