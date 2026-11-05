"""The event log: append actions, undo them, and keep each spool's row in sync.

Events are never edited, apart from `reverted_by`, which an undo sets on the event it
undoes. After every write the spool's state and dates are rebuilt from its events.
Callers own the transaction: these functions flush but do not commit.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Spool
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import EventSource, EventType
from filament_tracker.domain.state import (
    ACTION_TYPES,
    EventRecord,
    Outcome,
    Replay,
    Step,
    replay,
)


class RevertError(ValueError):
    """The event cannot be undone."""


@dataclass(frozen=True)
class AppendResult:
    event: Event
    step: Step


def to_record(event: Event) -> EventRecord:
    return EventRecord(
        id=event.id,
        type=event.type,
        source=event.source,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        reverted=event.reverted_by is not None,
    )


def reproject(spool: Spool) -> Replay:
    """Rebuild the spool's state and dates from its events."""
    result = replay(to_record(e) for e in spool.events)
    projection = result.projection
    spool.state = projection.state
    spool.received_at = projection.received_at
    spool.opened_at = projection.opened_at
    spool.emptied_at = projection.emptied_at
    return result


def append_event(
    session: Session,
    spool: Spool,
    event_type: EventType,
    source: EventSource,
    occurred_at: datetime,
    *,
    device_id: str | None = None,
    user_id: int | None = None,
    event_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    flag: bool = False,
) -> AppendResult:
    """Record an action on a spool (new or existing) and update the spool.

    The event is flagged for review if replay finds it out of order, or if `flag` is set
    by the caller (for example, when a scan was linked to a manual placeholder).
    """
    if event_type not in ACTION_TYPES:
        raise ValueError(f"{event_type} is not an action; use revert_event to undo")
    event = Event(
        id=event_id or uuid4(),
        spool=spool,
        type=event_type,
        source=source,
        device_id=device_id,
        user_id=user_id,
        occurred_at=occurred_at,
        recorded_at=_next_recorded_at(spool),
        payload_json=payload,
    )
    session.add(event)
    step = reproject(spool).steps[event.id]
    event.flagged = flag or step.outcome is Outcome.FLAGGED
    session.flush()
    return AppendResult(event, step)


def revert_event(
    session: Session,
    target: Event,
    source: EventSource,
    occurred_at: datetime,
    *,
    device_id: str | None = None,
    user_id: int | None = None,
    event_id: UUID | None = None,
) -> Event:
    """Undo an event by writing a `revert` event, then rebuild the spool."""
    if target.type == EventType.REVERT:
        raise RevertError("an undo cannot itself be undone")
    if target.reverted_by is not None:
        raise RevertError("the event has already been undone")
    session.flush()
    spool = target.spool
    revert = Event(
        id=event_id or uuid4(),
        spool=spool,
        type=EventType.REVERT,
        source=source,
        device_id=device_id,
        user_id=user_id,
        occurred_at=occurred_at,
        recorded_at=_next_recorded_at(spool),
        payload_json={"reverts": str(target.id)},
    )
    session.add(revert)
    session.flush()
    target.reverted_by = revert.id
    reproject(spool)
    session.flush()
    return revert


def _next_recorded_at(spool: Spool) -> datetime:
    """Now, but always after the spool's latest event, so ties keep arrival order."""
    now = utcnow()
    latest = max((e.recorded_at for e in spool.events), default=None)
    if latest is not None and now <= latest:
        return latest + timedelta(microseconds=1)
    return now
