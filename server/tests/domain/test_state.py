from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.domain.state import (
    EventRecord,
    Outcome,
    Projection,
    apply,
    replay,
)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)

RECEIVED, OPENED, EMPTY = EventType.RECEIVED, EventType.OPENED, EventType.EMPTY
SCANNER, UI, AMS = EventSource.SCANNER, EventSource.UI, EventSource.AMS
SEALED, OPEN, GONE = SpoolState.SEALED, SpoolState.OPEN, SpoolState.EMPTY

UNKNOWN = Projection()
SEALED_P = Projection(SEALED, received_at=T0)
OPEN_P = Projection(OPEN, received_at=T0, opened_at=T0)
EMPTY_P = Projection(GONE, received_at=T0, opened_at=T0, emptied_at=T0)


def _event(
    event_type: EventType,
    at: datetime,
    source: EventSource = SCANNER,
    *,
    recorded_at: datetime | None = None,
    reverted: bool = False,
) -> EventRecord:
    return EventRecord(
        id=uuid4(),
        type=event_type,
        source=source,
        occurred_at=at,
        recorded_at=recorded_at or at,
        reverted=reverted,
    )


# --- Every row of "Spool states and transitions" -------------------------------------


@pytest.mark.parametrize("source", [SCANNER, UI])
def test_none_received_becomes_sealed(source: EventSource) -> None:
    step = apply(UNKNOWN, RECEIVED, source, T1)

    assert step.projection == Projection(SEALED, received_at=T1)
    assert step.outcome is Outcome.APPLIED
    assert not step.implicit_receive


@pytest.mark.parametrize("source", [SCANNER, UI, AMS])
def test_none_opened_becomes_open_with_implicit_receive(source: EventSource) -> None:
    step = apply(UNKNOWN, OPENED, source, T1)

    assert step.projection == Projection(OPEN, received_at=T1, opened_at=T1)
    assert step.outcome is Outcome.APPLIED
    assert step.implicit_receive


@pytest.mark.parametrize("source", [SCANNER, UI, AMS])
def test_sealed_opened_becomes_open(source: EventSource) -> None:
    step = apply(SEALED_P, OPENED, source, T1)

    assert step.projection == Projection(OPEN, received_at=T0, opened_at=T1)
    assert step.outcome is Outcome.APPLIED


@pytest.mark.parametrize("source", [SCANNER, UI])
def test_open_empty_becomes_empty(source: EventSource) -> None:
    step = apply(OPEN_P, EMPTY, source, T1)

    assert step.projection == Projection(GONE, received_at=T0, opened_at=T0, emptied_at=T1)
    assert step.outcome is Outcome.APPLIED


@pytest.mark.parametrize("source", [SCANNER, UI])
def test_sealed_empty_is_flagged_and_sets_both_dates(source: EventSource) -> None:
    step = apply(SEALED_P, EMPTY, source, T1)

    assert step.projection == Projection(GONE, received_at=T0, opened_at=T1, emptied_at=T1)
    assert step.outcome is Outcome.FLAGGED


def test_empty_opened_from_the_ui_is_a_correction() -> None:
    step = apply(EMPTY_P, OPENED, UI, T1)

    assert step.projection == Projection(OPEN, received_at=T0, opened_at=T0)
    assert step.outcome is Outcome.APPLIED


def test_empty_opened_from_a_queued_scan_is_flagged() -> None:
    step = apply(EMPTY_P, OPENED, SCANNER, T1)

    assert step.projection.state is OPEN
    assert step.projection.emptied_at is None
    assert step.outcome is Outcome.FLAGGED


@pytest.mark.parametrize("start", [OPEN_P, EMPTY_P])
@pytest.mark.parametrize("source", [SCANNER, UI])
def test_received_on_open_or_empty_is_flagged_with_no_change(
    start: Projection, source: EventSource
) -> None:
    step = apply(start, RECEIVED, source, T1)

    assert step.projection == start
    assert step.outcome is Outcome.FLAGGED


# --- Rules -----------------------------------------------------------------------------


def test_empty_on_a_spool_never_seen_creates_it_flagged_with_all_dates() -> None:
    step = apply(UNKNOWN, EMPTY, SCANNER, T1)

    assert step.projection == Projection(GONE, received_at=T1, opened_at=T1, emptied_at=T1)
    assert step.outcome is Outcome.FLAGGED
    assert step.implicit_receive


@pytest.mark.parametrize(
    ("start", "action"), [(SEALED_P, RECEIVED), (OPEN_P, OPENED), (EMPTY_P, EMPTY)]
)
def test_repeating_the_current_state_changes_nothing(start: Projection, action: EventType) -> None:
    step = apply(start, action, SCANNER, T1)

    assert step.projection == start
    assert step.outcome is Outcome.ALREADY_IN_STATE


def test_revert_is_not_an_action() -> None:
    with pytest.raises(ValueError, match="not an action"):
        apply(SEALED_P, EventType.REVERT, UI, T1)


# --- Replay ------------------------------------------------------------------------------


def test_replay_of_nothing_is_unknown() -> None:
    assert replay([]).projection == UNKNOWN


def test_full_lifecycle() -> None:
    events = [_event(RECEIVED, T0), _event(OPENED, T1), _event(EMPTY, T2)]

    result = replay(events)

    assert result.projection == Projection(GONE, received_at=T0, opened_at=T1, emptied_at=T2)
    assert all(step.outcome is Outcome.APPLIED for step in result.steps.values())


def test_replay_uses_occurred_at_not_arrival_order() -> None:
    received = _event(RECEIVED, T0, recorded_at=T2)  # queued offline, arrived last
    opened = _event(OPENED, T1, recorded_at=T1)

    result = replay([opened, received])

    assert result.projection == Projection(OPEN, received_at=T0, opened_at=T1)
    assert result.steps[received.id].outcome is Outcome.APPLIED
    assert result.steps[opened.id].outcome is Outcome.APPLIED


def test_ties_on_occurred_at_keep_arrival_order() -> None:
    first = _event(RECEIVED, T1, recorded_at=T1)
    second = _event(OPENED, T1, recorded_at=T1 + timedelta(microseconds=1))

    result = replay([second, first])

    assert result.projection.state is OPEN
    assert not result.steps[second.id].implicit_receive


def test_queued_opened_after_empty_reopens_the_spool_flagged() -> None:
    events = [_event(RECEIVED, T0), _event(EMPTY, T1)]
    queued = _event(OPENED, T2)

    result = replay([*events, queued])

    assert result.projection.state is OPEN
    assert result.steps[queued.id].outcome is Outcome.FLAGGED


def test_undone_events_are_skipped() -> None:
    received = _event(RECEIVED, T0)
    opened = _event(OPENED, T1, reverted=True)

    result = replay([received, opened])

    assert result.projection == Projection(SEALED, received_at=T0)
    assert opened.id not in result.steps


def test_undoing_the_only_event_returns_to_unknown() -> None:
    assert replay([_event(RECEIVED, T0, reverted=True)]).projection == UNKNOWN


def test_revert_events_themselves_are_skipped() -> None:
    received = _event(RECEIVED, T0)
    revert = _event(EventType.REVERT, T1)

    result = replay([received, revert])

    assert result.projection.state is SEALED
    assert revert.id not in result.steps
