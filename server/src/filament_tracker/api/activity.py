"""Activity (every event, newest first) and Review (what needs a person's attention)."""

from typing import Annotated

from fastapi import APIRouter, Query

from filament_tracker.api.read_schemas import EventOut, Page, ReviewOut
from filament_tracker.api.views import event_out, unidentified_tag
from filament_tracker.auth import DbSession, Viewer
from filament_tracker.domain.enums import EventSource
from filament_tracker.services import queries

router = APIRouter(tags=["activity"])


@router.get("/events", response_model=Page[EventOut])
def list_events(
    _: Viewer,
    session: DbSession,
    spool_id: int | None = None,
    source: EventSource | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventOut]:
    items, total = queries.events(
        session, spool_id=spool_id, source=source, limit=limit, offset=offset
    )
    return Page[EventOut](
        items=[event_out(e) for e in items], total=total, limit=limit, offset=offset
    )


@router.get("/review", response_model=ReviewOut)
def get_review(_: Viewer, session: DbSession) -> ReviewOut:
    return ReviewOut(
        flagged_events=[event_out(e) for e in queries.flagged_events(session)],
        unidentified_tags=[unidentified_tag(t) for t in queries.unidentified_tags(session)],
        likely_empty=[],
    )
