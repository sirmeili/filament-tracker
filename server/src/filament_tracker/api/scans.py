from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.api.schemas import ScanEvent, ScanResponse
from filament_tracker.auth import ScannerDevice
from filament_tracker.db.types import utcnow
from filament_tracker.services.scans import EventIdConflict, handle_scan

router = APIRouter(tags=["scans"])


@router.post("/scans", response_model=ScanResponse)
def post_scan(
    scan: ScanEvent,
    device: ScannerDevice,
    session: Annotated[Session, Depends(get_session)],
) -> ScanResponse:
    """Submit a scan. A lookup reads only; an action records an event."""
    if scan.device_id != device.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "device_id does not match the token")
    try:
        return handle_scan(session, device, scan, utcnow())
    except EventIdConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "event_id is already in use") from exc
