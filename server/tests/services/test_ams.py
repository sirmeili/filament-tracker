import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Printer, PrinterSlot, Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.printer.report import AmsView, TrayReport
from filament_tracker.services import queries
from filament_tracker.services.ams import ingest
from filament_tracker.services.edits import add_placeholder, record_action
from filament_tracker.services.events import revert_event

REPORTS = Path(__file__).parents[1] / "printer" / "reports"
BLACK = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
GRAY = "0F1E2D3C4B5A69788796A5B4C3D2E1F0"
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)


@pytest.fixture
def printer(session: Session) -> Printer:
    printer = Printer(name="P1S", serial="01P00A000000001", host="192.168.1.40")
    session.add(printer)
    session.flush()
    return printer


def trays(*names: str) -> list[TrayReport]:
    view = AmsView()
    for name in names:
        view.apply(json.loads((REPORTS / f"{name}.json").read_text(encoding="utf-8")))
    return view.trays()


def spool_by_uid(session: Session, uid: str) -> Spool:
    spool = session.scalar(select(Spool).where(Spool.tray_uid == uid))
    assert spool is not None
    return spool


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def product(session: Session, **fields: object) -> Product:
    values = {
        "material_id": "GFA00",
        "variant_id": "A00-K00",
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "display_name": "Black PLA Basic",
    } | fields
    item = Product(**values)
    session.add(item)
    session.flush()
    return item


def sealed_spool(session: Session, item: Product, uid: str) -> Spool:
    spool = add_placeholder(session, item, T0 - timedelta(days=3), user_id=None)
    spool.tray_uid = uid
    session.flush()
    return spool


def test_new_tray_uids_become_open_spools_flagged_for_review(
    session: Session, printer: Printer
) -> None:
    ingest(session, printer, trays("pushall"), T0)

    black, gray = spool_by_uid(session, BLACK), spool_by_uid(session, GRAY)
    assert (black.state, black.opened_at, black.remaining_pct) == (SpoolState.OPEN, T0, 85)
    assert (gray.state, gray.remaining_pct) == (SpoolState.OPEN, 0)
    event = black.events[0]
    assert (event.type, event.source, event.flagged) == (EventType.OPENED, EventSource.AMS, True)
    assert event.payload_json == {"printer_id": printer.id, "ams": 0, "tray": 0}
    assert black.product.provisional and black.product.display_name == "PLA Basic #000000"
    assert gray.product.display_name == "PETG HF #515151"
    assert count(session, Spool) == 2  # the zero tray UID in slot 2 is not a spool


def test_slots_record_what_is_loaded(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)

    slots = [
        (s.tray_index, s.tray_uuid, s.spool_id is not None, s.filament_type, s.color_rgba)
        for s in printer.slots
    ]
    assert slots == [
        (0, BLACK, True, "PLA", "000000FF"),
        (1, None, False, None, None),
        (2, None, False, "PETG", "FF6A13FF"),
        (3, GRAY, True, "PETG", "515151FF"),
    ]
    assert printer.slots[0].spool is spool_by_uid(session, BLACK)
    assert all(s.updated_at == T0 for s in printer.slots)


def test_an_unchanged_report_writes_nothing(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    ingest(session, printer, trays("pushall"), T1)

    assert count(session, Event) == 2
    assert all(s.updated_at == T0 for s in printer.slots)


def test_remaining_changes_update_the_spool_and_slot(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    ingest(session, printer, trays("pushall", "remain-delta"), T1)

    assert spool_by_uid(session, BLACK).remaining_pct == 80
    assert [s.updated_at for s in printer.slots] == [T1, T0, T0, T0]


def test_an_unloaded_slot_forgets_its_spool(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    ingest(session, printer, trays("pushall", "unloaded"), T1)

    slot = printer.slots[3]
    assert (slot.tray_uuid, slot.spool_id, slot.updated_at) == (None, None, T1)
    assert spool_by_uid(session, GRAY).state is SpoolState.OPEN


def test_a_removed_ams_unit_drops_its_slots(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    ingest(session, printer, [], T1)

    assert count(session, PrinterSlot) == 0


def test_a_new_spool_uses_the_one_matching_product(session: Session, printer: Printer) -> None:
    black = product(session)

    ingest(session, printer, trays("pushall"), T0)

    assert spool_by_uid(session, BLACK).product is black
    assert count(session, Product) == 2  # Black PLA, and a provisional PETG HF


def test_several_matching_products_give_a_provisional_one(
    session: Session, printer: Printer
) -> None:
    product(session)
    product(session, variant_id="A00-K01")

    ingest(session, printer, trays("pushall"), T0)

    assert spool_by_uid(session, BLACK).product.provisional


def test_a_tray_with_little_data_still_gets_a_product(session: Session, printer: Printer) -> None:
    ingest(session, printer, [TrayReport(0, 0, tray_uuid=BLACK)], T0)

    item = spool_by_uid(session, BLACK).product
    assert (item.filament_type, item.color_rgba, item.display_name) == (
        "Unknown",
        "00000000",
        "Unknown #000000",
    )


def test_a_sealed_spool_is_opened_by_the_ams_without_a_flag(
    session: Session, printer: Printer
) -> None:
    spool = sealed_spool(session, product(session), BLACK)

    ingest(session, printer, trays("pushall"), T0)

    assert spool.state is SpoolState.OPEN
    opened = spool.events[-1]
    assert (opened.source, opened.flagged) == (EventSource.AMS, False)
    assert spool.product.display_name == "Black PLA Basic"


def test_an_undone_ams_opened_is_not_recorded_again(session: Session, printer: Printer) -> None:
    spool = sealed_spool(session, product(session), BLACK)
    ingest(session, printer, trays("pushall"), T0)
    revert_event(session, spool.events[-1], EventSource.UI, T1)

    ingest(session, printer, trays("pushall", "remain-delta"), T1)

    assert spool.state is SpoolState.SEALED
    assert spool.remaining_pct == 80


@pytest.mark.parametrize("action", [EventType.OPENED, EventType.EMPTY])
def test_open_or_empty_spools_get_no_new_event(
    session: Session, printer: Printer, action: EventType
) -> None:
    spool = sealed_spool(session, product(session), BLACK)
    record_action(session, spool, EventType.OPENED, T0, user_id=None)
    if action == EventType.EMPTY:
        record_action(session, spool, EventType.EMPTY, T0, user_id=None)
    before = len(spool.events)

    ingest(session, printer, trays("pushall"), T1)

    assert len(spool.events) == before


def test_likely_empty_lists_open_spools_at_zero(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    gray = spool_by_uid(session, GRAY)

    assert queries.likely_empty(session) == [gray]

    gray.likely_empty_dismissed_at = T1
    assert queries.likely_empty(session) == []


def test_more_than_zero_brings_back_a_dismissed_suggestion(
    session: Session, printer: Printer
) -> None:
    ingest(session, printer, trays("pushall"), T0)
    gray = spool_by_uid(session, GRAY)
    gray.likely_empty_dismissed_at = T1

    ingest(session, printer, [TrayReport(0, 3, tray_uuid=GRAY, remaining_pct=0)], T1)
    assert gray.likely_empty_dismissed_at == T1

    ingest(session, printer, [TrayReport(0, 3, tray_uuid=GRAY, remaining_pct=40)], T1)
    assert gray.likely_empty_dismissed_at is None


def test_an_emptied_spool_is_not_likely_empty(session: Session, printer: Printer) -> None:
    ingest(session, printer, trays("pushall"), T0)
    record_action(session, spool_by_uid(session, GRAY), EventType.EMPTY, T1, user_id=None)

    assert queries.likely_empty(session) == []
