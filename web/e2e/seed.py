"""Create the end-to-end test database with one user per role and a little stock.

Run with the server's environment: uv run --project ../server python e2e/seed.py <db-url>
"""

import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.db.models import Product
from filament_tracker.domain.enums import EventType, Role
from filament_tracker.services.accounts import create_user
from filament_tracker.services.edits import add_placeholder, record_action

PASSWORD = "e2e password 123"  # noqa: S105 - test value for a throwaway database


def add_stock(session: Session) -> None:
    """Black PLA: spool 1 sealed, spool 2 open at 12% (low stock, nearly out).
    Gray PETG: spool 3 sealed."""
    start = datetime.now(UTC) - timedelta(days=10)
    black = Product(
        material_id="GFA00",
        variant_id="A00-K00",
        filament_type="PLA",
        color_rgba="000000FF",
        display_name="Black PLA Basic",
        low_stock_threshold=1,
    )
    petg = Product(
        filament_type="PETG",
        color_rgba="515151FF",
        display_name="Dark Gray PETG HF",
        provisional=True,
    )
    add_placeholder(session, black, start, user_id=None, location="Shelf A")
    opened = add_placeholder(session, black, start, user_id=None, location="AMS slot 1")
    record_action(session, opened, EventType.OPENED, start + timedelta(days=1), user_id=None)
    opened.remaining_pct = 12
    add_placeholder(session, petg, start, user_id=None, location="Shelf B")


def main(url: str) -> None:
    upgrade(url)
    engine = create_db_engine(url)
    with create_session_factory(engine)() as session:
        for role in Role:
            create_user(session, f"e2e-{role.value}", PASSWORD, role)
        add_stock(session)
        session.commit()
    engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
