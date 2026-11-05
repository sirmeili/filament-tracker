"""Spool state machine and event replay.

A spool's state is never stored on its own: it is rebuilt by replaying the spool's events
in the order they happened (`occurred_at`, then `recorded_at`), skipping undone events.
The transition rules follow "Spool states and transitions" and "Rules" in docs/SPEC.md.
Out-of-order actions are accepted, never refused; they are flagged for review.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from filament_tracker.domain.enums import EventSource, EventType, SpoolState

ACTION_TYPES = frozenset({EventType.RECEIVED, EventType.OPENED, EventType.EMPTY})


class Outcome(StrEnum):
    """What one event did to the spool when it was replayed."""

    APPLIED = "applied"
    ALREADY_IN_STATE = "already_in_state"
    FLAGGED = "flagged"


@dataclass(frozen=True)
class EventRecord:
    """The parts of an event that replay needs."""

    id: UUID
    type: EventType
    source: EventSource
    occurred_at: datetime
    recorded_at: datetime
    reverted: bool = False


@dataclass(frozen=True)
class Projection:
    """A spool's derived state and dates. `state` None means Unknown."""

    state: SpoolState | None = None
    received_at: datetime | None = None
    opened_at: datetime | None = None
    emptied_at: datetime | None = None


@dataclass(frozen=True)
class Step:
    """The result of applying one action."""

    projection: Projection
    outcome: Outcome
    implicit_receive: bool = False


@dataclass(frozen=True)
class Replay:
    """The final projection, plus each replayed event's step, keyed by event ID."""

    projection: Projection
    steps: dict[UUID, Step] = field(default_factory=dict)


def apply(current: Projection, action: EventType, source: EventSource, at: datetime) -> Step:
    """Apply one action at time `at` to a spool's current projection."""
    if action not in ACTION_TYPES:
        raise ValueError(f"{action} is not an action")
    state = current.state

    if state is None:
        return _apply_to_unknown(action, at)

    if action == EventType.RECEIVED:
        if state == SpoolState.SEALED:
            return Step(current, Outcome.ALREADY_IN_STATE)
        # A second "New" for a spool that is already open or empty: kept, flagged, no change.
        return Step(current, Outcome.FLAGGED)

    if action == EventType.OPENED:
        if state == SpoolState.OPEN:
            return Step(current, Outcome.ALREADY_IN_STATE)
        opened = replace(current, state=SpoolState.OPEN, opened_at=current.opened_at or at)
        if state == SpoolState.SEALED:
            return Step(opened, Outcome.APPLIED)
        # Empty back to open: a UI correction, or a queued scan that is flagged.
        reopened = replace(opened, emptied_at=None)
        outcome = Outcome.APPLIED if source == EventSource.UI else Outcome.FLAGGED
        return Step(reopened, outcome)

    # EventType.EMPTY
    if state == SpoolState.EMPTY:
        return Step(current, Outcome.ALREADY_IN_STATE)
    emptied = replace(
        current, state=SpoolState.EMPTY, opened_at=current.opened_at or at, emptied_at=at
    )
    outcome = Outcome.APPLIED if state == SpoolState.OPEN else Outcome.FLAGGED
    return Step(emptied, outcome)


def _apply_to_unknown(action: EventType, at: datetime) -> Step:
    if action == EventType.RECEIVED:
        return Step(Projection(SpoolState.SEALED, received_at=at), Outcome.APPLIED)
    if action == EventType.OPENED:
        return Step(
            Projection(SpoolState.OPEN, received_at=at, opened_at=at),
            Outcome.APPLIED,
            implicit_receive=True,
        )
    # Empty on a spool never seen: it was received and opened too, which is out of order.
    return Step(
        Projection(SpoolState.EMPTY, received_at=at, opened_at=at, emptied_at=at),
        Outcome.FLAGGED,
        implicit_receive=True,
    )


def replay(events: Iterable[EventRecord]) -> Replay:
    """Rebuild a spool's projection from its events, in the order they happened."""
    ordered = sorted(
        (e for e in events if e.type in ACTION_TYPES and not e.reverted),
        key=lambda e: (e.occurred_at, e.recorded_at),
    )
    projection = Projection()
    steps: dict[UUID, Step] = {}
    for event in ordered:
        step = apply(projection, event.type, event.source, event.occurred_at)
        steps[event.id] = step
        projection = step.projection
    return Replay(projection, steps)
