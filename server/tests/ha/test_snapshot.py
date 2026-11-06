from datetime import UTC, datetime

from ha_helpers import add_product, add_spools
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Spool, Tag
from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.ha.snapshot import ProductState, take_snapshot


def test_counts_low_stock_and_review(session: Session) -> None:
    black = add_product(session, "Black PLA Basic", low_stock_threshold=2)
    white = add_product(session, "White PETG", filament_type="PETG", color_rgba="FFFFFFFF")
    add_spools(session, black, SpoolState.SEALED, 2)
    add_spools(session, black, SpoolState.OPEN)
    add_spools(session, white, SpoolState.SEALED, 3)
    add_spools(session, white, SpoolState.EMPTY)
    # One of each kind of review item: a flagged event, an unknown tag, a likely-empty spool.
    spool = Spool(product_id=white.id, state=SpoolState.OPEN, remaining_pct=0)
    session.add(spool)
    session.flush()
    session.add(
        Event(
            spool_id=spool.id,
            type=EventType.OPENED,
            source=EventSource.UI,
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
            flagged=True,
        )
    )
    session.add(Tag(uid="0A0B0C0D"))
    session.flush()

    snapshot = take_snapshot(session)

    assert snapshot.products == (
        ProductState(black.id, "Black PLA Basic", "PLA", "000000FF", 2, 1, low_stock=True),
        ProductState(white.id, "White PETG", "PETG", "FFFFFFFF", 3, 1, low_stock=False),
    )
    assert snapshot.total_sealed == 5
    assert snapshot.in_review == 3


def test_an_empty_database(session: Session) -> None:
    snapshot = take_snapshot(session)
    assert (snapshot.products, snapshot.total_sealed, snapshot.in_review) == ((), 0, 0)
