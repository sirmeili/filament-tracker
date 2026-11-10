from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.api.schemas import ScanAction, ScanEvent, ScanResponse
from filament_tracker.auth import ScannerDevice
from filament_tracker.db.types import utcnow
from filament_tracker.services.scans import EventIdConflict, handle_scan, may_record

router = APIRouter(tags=["scans"])

# A Viewer's phone looks spools up but records nothing (Users and roles in docs/SPEC.md).
VIEW_ONLY = "this phone's account can look spools up but not record them"


@router.post("/scans", response_model=ScanResponse)
def post_scan(
    scan: ScanEvent,
    device: ScannerDevice,
    session: Annotated[Session, Depends(get_session)],
) -> ScanResponse:
    """Submit a scan. A lookup reads only; an action records an event."""
    if scan.device_id != device.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "device_id does not match the token")
    if scan.action != ScanAction.LOOKUP and not may_record(device):
        raise HTTPException(status.HTTP_403_FORBIDDEN, VIEW_ONLY)
    try:
        return handle_scan(session, device, scan, utcnow())
    except EventIdConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "event_id is already in use") from exc
