import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from filament_tracker.db.models import Device, Event, Printer, Product, Spool, Tag
from filament_tracker.domain.enums import EventSource, EventType, SpoolState

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _product(**overrides: object) -> Product:
    values: dict[str, object] = {
        "material_id": "GFA00",
        "variant_id": "A00-K00",
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "display_name": "Black PLA Basic",
    }
    values.update(overrides)
    return Product(**values)


def _spool(product: Product, tray_uid: str | None = "AA" * 16) -> Spool:
    return Spool(tray_uid=tray_uid, product=product, state=SpoolState.SEALED, received_at=NOW)


def test_a_spool_with_its_tags_and_events_round_trips(session: Session) -> None:
    device = Device(id="scanner-1", name="Shelf", token_hash="ab" * 32)
    spool = _spool(_product())
    tag = Tag(uid="A1B2C3D4", spool=spool, raw_blocks=["00" * 16], decoded_json={"a": 1})
    event = Event(
        spool=spool,
        type=EventType.RECEIVED,
        source=EventSource.SCANNER,
        device_id=device.id,
        occurred_at=NOW,
        payload_json={"action": "received"},
    )
    session.add_all([device, spool, tag, event])
    session.commit()
    session.expunge_all()

    stored = session.get(Spool, spool.id)
    assert stored is not None
    assert stored.state is SpoolState.SEALED
    assert stored.product.display_name == "Black PLA Basic"
    assert stored.product.low_stock_threshold == 0
    assert stored.product.provisional is False
    assert [t.uid for t in stored.tags] == ["A1B2C3D4"]
    assert stored.tags[0].raw_blocks == ["00" * 16]
    [stored_event] = stored.events
    assert isinstance(stored_event.id, uuid.UUID)
    assert stored_event.type is EventType.RECEIVED
    assert stored_event.flagged is False
    assert stored_event.reverted_by is None


def test_timestamps_come_back_in_utc(session: Session) -> None:
    eastern = timezone(timedelta(hours=-5))
    spool = _spool(_product())
    spool.received_at = datetime(2026, 11, 5, 7, 0, tzinfo=eastern)
    session.add(spool)
    session.commit()
    session.expunge_all()

    stored = session.get(Spool, spool.id)
    assert stored is not None
    assert stored.received_at == datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    assert stored.received_at.tzinfo is UTC
    assert stored.created_at.tzinfo is UTC


def test_naive_timestamps_are_refused(session: Session) -> None:
    spool = _spool(_product())
    spool.received_at = datetime(2026, 11, 5, 12, 0)
    session.add(spool)

    with pytest.raises(StatementError, match="timezone-aware"):
        session.commit()


def test_tray_uid_is_unique(session: Session) -> None:
    product = _product()
    session.add_all([_spool(product, "AB" * 16), _spool(product, "AB" * 16)])

    with pytest.raises(IntegrityError):
        session.commit()


def test_manual_placeholders_can_share_a_null_tray_uid(session: Session) -> None:
    product = _product()
    session.add_all([_spool(product, None), _spool(product, None)])
    session.commit()

    assert session.query(Spool).filter(Spool.tray_uid.is_(None)).count() == 2


def test_tag_uid_is_unique(session: Session) -> None:
    session.add_all([Tag(uid="A1B2C3D4"), Tag(uid="A1B2C3D4")])

    with pytest.raises(IntegrityError):
        session.commit()


def test_unidentified_tags_need_no_spool(session: Session) -> None:
    session.add(Tag(uid="0A0B0C0D"))
    session.commit()

    assert session.query(Tag).one().spool_id is None


def test_product_key_is_unique(session: Session) -> None:
    session.add_all([_product(), _product(display_name="Duplicate")])

    with pytest.raises(IntegrityError):
        session.commit()


def test_provisional_products_without_ids_can_coexist(session: Session) -> None:
    for name in ("TPU from the AMS", "TPU entered by hand"):
        session.add(
            _product(material_id=None, variant_id=None, display_name=name, provisional=True)
        )
    session.commit()

    assert session.query(Product).filter_by(provisional=True).count() == 2


def test_foreign_keys_are_enforced(session: Session) -> None:
    session.add(Spool(tray_uid="CD" * 16, product_id=999, state=SpoolState.OPEN))

    with pytest.raises(IntegrityError):
        session.commit()


def test_unknown_state_values_are_refused_by_the_database(session: Session) -> None:
    product = _product()
    session.add(product)
    session.commit()

    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO spool (product_id, state, created_at) "
                "VALUES (:product_id, 'lost', '2026-11-05 12:00:00')"
            ),
            {"product_id": product.id},
        )


def test_a_revert_points_at_the_event_it_undoes(session: Session) -> None:
    spool = _spool(_product())
    opened = Event(spool=spool, type=EventType.OPENED, source=EventSource.UI, occurred_at=NOW)
    revert = Event(spool=spool, type=EventType.REVERT, source=EventSource.UI, occurred_at=NOW)
    session.add_all([spool, opened, revert])
    session.flush()
    opened.reverted_by = revert.id
    session.commit()
    session.expunge_all()

    stored = session.get(Event, opened.id)
    assert stored is not None
    assert stored.reverted_by == revert.id


def test_device_token_hash_is_unique(session: Session) -> None:
    session.add_all(
        [
            Device(id="scanner-1", name="Shelf", token_hash="cd" * 32),
            Device(id="scanner-2", name="Printer", token_hash="cd" * 32),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_printer_serial_is_unique(session: Session) -> None:
    session.add_all(
        [
            Printer(name="P1S", serial="01P00A000000000", host="192.0.2.10"),
            Printer(name="Copy", serial="01P00A000000000", host="192.0.2.11"),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()
