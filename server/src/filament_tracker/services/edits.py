"""Changes made by people in the web app: manual actions and entry, spool and product
edits, and resolving Review items. Callers own the transaction; nothing here commits.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Product, Spool, Tag
from filament_tracker.domain.enums import EventSource, EventType
from filament_tracker.services.events import AppendResult, append_event


class EditError(ValueError):
    """The change conflicts with the current data (HTTP 409)."""


class NotFound(LookupError):
    """Something the change refers to does not exist (HTTP 404)."""


def record_action(
    session: Session,
    spool: Spool,
    action: EventType,
    occurred_at: datetime,
    *,
    user_id: int | None,
) -> AppendResult:
    """A manual received, opened or empty. The state rules are the scanner's, except
    that reopening an empty spool from the web app is a correction and not flagged."""
    return append_event(session, spool, action, EventSource.UI, occurred_at, user_id=user_id)


def add_placeholder(
    session: Session,
    product: Product,
    received_at: datetime,
    *,
    user_id: int | None,
    location: str | None = None,
    notes: str | None = None,
) -> Spool:
    """Manual entry: a spool with no tray UID yet, recorded as received. The first scan
    of this product's tag links to the oldest such placeholder."""
    spool = Spool(product=product, location=location, notes=notes)
    session.add(spool)
    session.flush()
    record_action(session, spool, EventType.RECEIVED, received_at, user_id=user_id)
    return spool


def set_location(session: Session, spool_ids: Sequence[int], location: str | None) -> list[Spool]:
    """Move several spools at once. All must exist, or nothing changes."""
    wanted = set(spool_ids)
    spools = list(session.scalars(select(Spool).where(Spool.id.in_(wanted)).order_by(Spool.id)))
    missing = wanted - {s.id for s in spools}
    if missing:
        raise NotFound(f"no such spool: {', '.join(str(i) for i in sorted(missing))}")
    for spool in spools:
        spool.location = location
    return spools


def accept_event(event: Event, now: datetime, *, user_id: int | None) -> None:
    """Review: the flagged event was right. Accepting twice changes nothing."""
    if not event.flagged:
        raise EditError("only flagged events can be accepted")
    if event.reverted_by is not None:
        raise EditError("the event has been undone")
    if event.reviewed_at is None:
        event.reviewed_at = now
        event.reviewed_by = user_id


def dismiss_tag(session: Session, uid: str, now: datetime) -> Tag:
    """Review: hide an unidentified tag. Dismissing twice changes nothing."""
    tag = session.scalar(select(Tag).where(Tag.uid == uid.strip().upper()))
    if tag is None:
        raise NotFound("no such tag")
    if tag.spool_id is not None:
        raise EditError("the tag belongs to a spool, so it is not unidentified")
    if tag.dismissed_at is None:
        tag.dismissed_at = now
    return tag
