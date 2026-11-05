"""Resolve Review items (Editor and up). Undo uses `/events/{id}/revert`."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from filament_tracker.api.read_schemas import EventOut
from filament_tracker.api.views import event_out
from filament_tracker.auth import DbSession, Editor
from filament_tracker.db.models import Event
from filament_tracker.db.types import utcnow
from filament_tracker.services import edits

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/events/{event_id}/accept", response_model=EventOut)
def accept(event_id: UUID, caller: Editor, session: DbSession) -> EventOut:
    """The flagged event was right: keep it and take it out of Review."""
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such event")
    try:
        edits.accept_event(event, utcnow(), user_id=caller.user.id if caller.user else None)
    except edits.EditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    session.refresh(event)
    return event_out(event)


@router.post("/tags/{uid}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(uid: str, _: Editor, session: DbSession) -> Response:
    """Hide an unidentified tag from Review."""
    try:
        edits.dismiss_tag(session, uid, utcnow())
    except edits.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except edits.EditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
