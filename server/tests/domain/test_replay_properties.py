"""Property tests: replay must hold these for any history, not just the examples."""

import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st

from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.domain.state import EventRecord, replay

BASE = datetime(2026, 1, 1, tzinfo=UTC)

actions = st.sampled_from([EventType.RECEIVED, EventType.OPENED, EventType.EMPTY])
sources = st.sampled_from(list(EventSource))


@st.composite
def histories(draw: st.DrawFn) -> list[EventRecord]:
    """Events with distinct times, a random arrival order and some undone."""
    count = draw(st.integers(min_value=0, max_value=12))
    minutes = draw(st.lists(st.integers(0, 100_000), min_size=count, max_size=count, unique=True))
    events = [
        EventRecord(
            id=uuid4(),
            type=draw(actions),
            source=draw(sources),
            occurred_at=BASE + timedelta(minutes=m),
            recorded_at=BASE + timedelta(minutes=draw(st.integers(0, 200_000))),
            reverted=draw(st.booleans()),
        )
        for m in minutes
    ]
    return draw(st.permutations(events))


@given(histories(), st.randoms())
def test_arrival_order_does_not_change_the_result(
    events: list[EventRecord], rnd: random.Random
) -> None:
    shuffled = list(events)
    rnd.shuffle(shuffled)

    assert replay(shuffled) == replay(events)


@given(histories())
def test_undoing_the_latest_event_restores_the_previous_state(events: list[EventRecord]) -> None:
    live = sorted((e for e in events if not e.reverted), key=lambda e: e.occurred_at)
    if not live:
        return
    *earlier, latest = live
    undone = [
        e if e.id != latest.id else EventRecord(**{**vars(e), "reverted": True}) for e in events
    ]

    assert replay(undone).projection == replay(earlier).projection


@given(histories())
def test_dates_always_match_the_state(events: list[EventRecord]) -> None:
    p = replay(events).projection

    if p.state is None:
        assert (p.received_at, p.opened_at, p.emptied_at) == (None, None, None)
    else:
        assert p.received_at is not None
    if p.state is SpoolState.SEALED:
        assert p.opened_at is None and p.emptied_at is None
    if p.state is SpoolState.OPEN:
        assert p.opened_at is not None and p.emptied_at is None
    if p.state is SpoolState.EMPTY:
        assert p.opened_at is not None and p.emptied_at is not None


@given(histories())
def test_dates_never_go_backwards(events: list[EventRecord]) -> None:
    p = replay(events).projection
    dates = [d for d in (p.received_at, p.opened_at, p.emptied_at) if d is not None]

    assert dates == sorted(dates)


@given(histories())
def test_every_live_action_gets_exactly_one_step(events: list[EventRecord]) -> None:
    result = replay(events)

    assert set(result.steps) == {e.id for e in events if not e.reverted}
