from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from filament_tracker.db.models import Device, Event, Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.domain.state import Outcome
from filament_tracker.services.events import RevertError, append_event, revert_event

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)
SCANNER, UI = EventSource.SCANNER, EventSource.UI


@pytest.fixture
def spool(session: Session) -> Spool:
    product = Product(
        material_id="GFA00",
        variant_id="A00-K00",
        filament_type="PLA",
        color_rgba="000000FF",
        display_name="Black PLA Basic",
    )
    spool = Spool(tray_uid="AB" * 16, product=product)
    session.add(spool)
    return spool


def _reload(session: Session, spool: Spool) -> Spool:
    session.commit()
    session.expunge_all()
    stored = session.get(Spool, spool.id)
    assert stored is not None
    return stored


def test_a_new_spool_is_received_opened_and_emptied(session: Session, spool: Spool) -> None:
    append_event(session, spool, EventType.RECEIVED, SCANNER, T0)
    append_event(session, spool, EventType.OPENED, SCANNER, T1)
    append_event(session, spool, EventType.EMPTY, SCANNER, T2)

    stored = _reload(session, spool)
    assert stored.state is SpoolState.EMPTY
    assert (stored.received_at, stored.opened_at, stored.emptied_at) == (T0, T1, T2)
    assert [e.type for e in sorted(stored.events, key=lambda e: e.recorded_at)] == [
        EventType.RECEIVED,
        EventType.OPENED,
        EventType.EMPTY,
    ]
    assert not any(e.flagged for e in stored.events)


def test_the_result_reports_outcome_and_implicit_receive(session: Session, spool: Spool) -> None:
    result = append_event(session, spool, EventType.OPENED, SCANNER, T0)

    assert result.step.outcome is Outcome.APPLIED
    assert result.step.implicit_receive
    assert spool.state is SpoolState.OPEN
    assert spool.received_at == T0


def test_out_of_order_events_are_stored_flagged(session: Session, spool: Spool) -> None:
    append_event(session, spool, EventType.RECEIVED, SCANNER, T0)
    result = append_event(session, spool, EventType.EMPTY, SCANNER, T1)

    assert result.step.outcome is Outcome.FLAGGED
    _reload(session, spool)
    stored = session.get(Event, result.event.id)
    assert stored is not None
    assert stored.flagged


def test_callers_can_force_a_flag(session: Session, spool: Spool) -> None:
    result = append_event(session, spool, EventType.OPENED, SCANNER, T0, flag=True)

    assert result.step.outcome is Outcome.APPLIED
    assert result.event.flagged


def test_repeated_actions_are_stored_but_change_nothing(session: Session, spool: Spool) -> None:
    append_event(session, spool, EventType.RECEIVED, SCANNER, T0)
    result = append_event(session, spool, EventType.RECEIVED, SCANNER, T1)

    assert result.step.outcome is Outcome.ALREADY_IN_STATE
    stored = _reload(session, spool)
    assert stored.received_at == T0
    assert len(stored.events) == 2


def test_a_queued_event_takes_its_true_place(session: Session, spool: Spool) -> None:
    append_event(session, spool, EventType.OPENED, SCANNER, T1)
    queued = append_event(session, spool, EventType.RECEIVED, SCANNER, T0)

    assert queued.step.outcome is Outcome.APPLIED
    stored = _reload(session, spool)
    assert stored.state is SpoolState.OPEN
    assert (stored.received_at, stored.opened_at) == (T0, T1)


def test_event_ids_and_details_are_kept(session: Session, spool: Spool) -> None:
    session.add(Device(id="scanner-1", name="Shelf", token_hash="ab" * 32))
    event_id = uuid4()

    append_event(
        session,
        spool,
        EventType.RECEIVED,
        SCANNER,
        T0,
        device_id="scanner-1",
        event_id=event_id,
        payload={"fw_version": "0.1.0"},
    )

    stored = session.get(Event, event_id)
    assert stored is not None
    assert stored.device_id == "scanner-1"
    assert stored.payload_json == {"fw_version": "0.1.0"}


def test_recorded_at_always_increases(session: Session, spool: Spool) -> None:
    for _ in range(5):
        append_event(session, spool, EventType.RECEIVED, SCANNER, T0)

    times = [e.recorded_at for e in spool.events]
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_events_recorded_in_the_same_instant_keep_arrival_order(
    session: Session, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("filament_tracker.services.events.utcnow", lambda: T2)

    first = append_event(session, spool, EventType.RECEIVED, SCANNER, T0).event
    second = append_event(session, spool, EventType.OPENED, SCANNER, T0).event

    assert second.recorded_at == first.recorded_at + timedelta(microseconds=1)
    assert spool.state is SpoolState.OPEN


def test_revert_is_not_appended_as_an_action(session: Session, spool: Spool) -> None:
    with pytest.raises(ValueError, match="revert_event"):
        append_event(session, spool, EventType.REVERT, UI, T0)


def test_undo_restores_the_previous_state(session: Session, spool: Spool) -> None:
    append_event(session, spool, EventType.RECEIVED, SCANNER, T0)
    opened = append_event(session, spool, EventType.OPENED, SCANNER, T1).event

    revert = revert_event(session, opened, UI, T2)

    stored = _reload(session, spool)
    assert stored.state is SpoolState.SEALED
    assert stored.opened_at is None
    undone = session.get(Event, opened.id)
    assert undone is not None
    assert undone.reverted_by == revert.id
    stored_revert = session.get(Event, revert.id)
    assert stored_revert is not None
    assert stored_revert.type is EventType.REVERT
    assert stored_revert.payload_json == {"reverts": str(opened.id)}


def test_undoing_the_only_event_leaves_the_spool_unknown(session: Session, spool: Spool) -> None:
    received = append_event(session, spool, EventType.RECEIVED, SCANNER, T0).event

    revert_event(session, received, SCANNER, T1, device_id=None)

    stored = _reload(session, spool)
    assert stored.state is None
    assert stored.received_at is None


def test_undoing_an_earlier_event_replays_the_rest(session: Session, spool: Spool) -> None:
    received = append_event(session, spool, EventType.RECEIVED, SCANNER, T0).event
    append_event(session, spool, EventType.OPENED, SCANNER, T1)

    revert_event(session, received, UI, T2)

    stored = _reload(session, spool)
    assert stored.state is SpoolState.OPEN
    assert stored.received_at == T1  # the Opened now implies the receive


def test_an_event_cannot_be_undone_twice(session: Session, spool: Spool) -> None:
    received = append_event(session, spool, EventType.RECEIVED, SCANNER, T0).event
    revert_event(session, received, UI, T1)

    with pytest.raises(RevertError, match="already been undone"):
        revert_event(session, received, UI, T2)


def test_an_undo_cannot_be_undone(session: Session, spool: Spool) -> None:
    received = append_event(session, spool, EventType.RECEIVED, SCANNER, T0).event
    revert = revert_event(session, received, UI, T1)

    with pytest.raises(RevertError, match="cannot itself be undone"):
        revert_event(session, revert, UI, T2)
