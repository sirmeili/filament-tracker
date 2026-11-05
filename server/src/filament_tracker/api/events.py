"""Undo an event. Editors and the admin token may undo any event; a scanner only its own."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.api.schemas import RevertResponse
from filament_tracker.auth import EditorOrScanner
from filament_tracker.db.models import Event
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import EventSource
from filament_tracker.services.events import RevertError, revert_event
from filament_tracker.services.scans import spool_out

router = APIRouter(tags=["events"])


@router.post("/events/{event_id}/revert", response_model=RevertResponse)
def post_revert(
    event_id: UUID,
    caller: EditorOrScanner,
    session: Annotated[Session, Depends(get_session)],
) -> RevertResponse:
    target = session.get(Event, event_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such event")
    device = caller.device
    if device is not None and target.device_id != device.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a scanner can only undo its own events")
    try:
        revert = revert_event(
            session,
            target,
            EventSource.SCANNER if device else EventSource.UI,
            utcnow(),
            device_id=device.id if device else None,
            user_id=caller.user.id if caller.user else None,
        )
    except RevertError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return RevertResponse(
        revert_event_id=revert.id, reverted_event_id=target.id, spool=spool_out(target.spool)
    )
