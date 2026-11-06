"""Create the end-to-end test database with one user per role and a little stock.

Run with the server's environment: uv run --project ../server python e2e/seed.py <db-url>
"""

import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.db.models import Printer, PrinterSlot, Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, Role
from filament_tracker.services.accounts import create_user
from filament_tracker.services.edits import add_placeholder, record_action
from filament_tracker.services.events import append_event

PASSWORD = "e2e password 123"  # noqa: S105 - test value for a throwaway database


def add_stock(session: Session) -> None:
    """Black PLA: spool 1 sealed, spool 2 open at 12% (low stock, nearly out).
    Gray PETG: spool 3 sealed. Spool 1 also has a second Received flagged for Review."""
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
    sealed = add_placeholder(session, black, start, user_id=None, location="Shelf A")
    append_event(
        session, sealed, EventType.RECEIVED, EventSource.UI, start + timedelta(days=2), flag=True
    )
    opened = add_placeholder(session, black, start, user_id=None, location="AMS slot 1")
    record_action(session, opened, EventType.OPENED, start + timedelta(days=1), user_id=None)
    opened.remaining_pct = 12
    add_placeholder(session, petg, start, user_id=None, location="Shelf B")
    add_printer(session, opened, add_used_up(session, start))


def add_used_up(session: Session, start: datetime) -> Spool:
    """White PLA: spool 4 open at 0%, so Review suggests marking it used up."""
    white = Product(
        material_id="GFA00",
        variant_id="A00-W01",
        filament_type="PLA",
        color_rgba="FFFFFFFF",
        display_name="White PLA Basic",
    )
    spool = add_placeholder(session, white, start, user_id=None, location=None)
    record_action(session, spool, EventType.OPENED, start + timedelta(days=3), user_id=None)
    spool.remaining_pct = 0
    return spool


def add_printer(session: Session, *loaded: Spool) -> None:
    """A printer that is not in PRINTERS (so not connected): its AMS has spool 2 in slot 1,
    spool 4 in slot 2, a filament without a Bambu tag in slot 3 and nothing in slot 4."""
    now = datetime.now(UTC)
    printer = Printer(name="E2E P1S", serial="E2E0001", host="192.0.2.10", port=8883)
    printer.slots = [
        PrinterSlot(
            ams_index=0,
            tray_index=i,
            spool=spool,
            filament_type="PLA",
            color_rgba=spool.product.color_rgba,
            remaining_pct=spool.remaining_pct,
            updated_at=now,
        )
        for i, spool in enumerate(loaded)
    ]
    printer.slots += [
        PrinterSlot(
            ams_index=0, tray_index=2, filament_type="PETG", color_rgba="FF0000FF", updated_at=now
        ),
        PrinterSlot(ams_index=0, tray_index=3, updated_at=now),
    ]
    session.add(printer)


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
