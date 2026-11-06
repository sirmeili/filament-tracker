"""Register scanners and issue or revoke their tokens (Admin role or the admin token), and
receive their heartbeats."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.api.schemas import DeviceCreate, DeviceCreated, DeviceOut, Heartbeat
from filament_tracker.auth import Admin, ScannerDevice, hash_token, new_device_token
from filament_tracker.db.models import Device
from filament_tracker.db.types import utcnow

router = APIRouter(tags=["devices"])
SessionDep = Annotated[Session, Depends(get_session)]

# Scanners send a heartbeat every 5 minutes; three missed ones mark a scanner offline.
ONLINE_WINDOW = timedelta(minutes=15)


def is_online(device: Device, now: datetime) -> bool:
    return (
        device.revoked_at is None
        and device.last_seen_at is not None
        and now - device.last_seen_at <= ONLINE_WINDOW
    )


def _out(device: Device) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        name=device.name,
        created_at=device.created_at,
        last_seen_at=device.last_seen_at,
        fw_version=device.fw_version,
        queue_length=device.queue_length,
        online=is_online(device, utcnow()),
        revoked=device.revoked_at is not None,
    )


@router.post("/devices/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(body: Heartbeat, device: ScannerDevice, session: SessionDep) -> Response:
    """A scanner reports that it is online, its firmware version and its queue length."""
    device.last_seen_at = utcnow()
    device.fw_version = body.fw_version
    device.queue_length = body.queue_length
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(_: Admin, session: SessionDep) -> list[DeviceOut]:
    return [_out(d) for d in session.scalars(select(Device).order_by(Device.id))]


@router.post("/devices", response_model=DeviceCreated, status_code=status.HTTP_201_CREATED)
def register_device(body: DeviceCreate, _: Admin, session: SessionDep) -> DeviceCreated:
    """Register a scanner. The token is returned once and only its hash is stored."""
    if session.get(Device, body.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "a device with this id already exists")
    token = new_device_token()
    device = Device(id=body.id, name=body.name, token_hash=hash_token(token))
    session.add(device)
    session.commit()
    return DeviceCreated(**_out(device).model_dump(), token=token)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(device_id: str, _: Admin, session: SessionDep) -> Response:
    """Revoke a scanner's token. The device stays listed so its events keep their link."""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such device")
    if device.revoked_at is None:
        device.revoked_at = utcnow()
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/devices/{device_id}/rotate", response_model=DeviceCreated)
def rotate_token(device_id: str, _: Admin, session: SessionDep) -> DeviceCreated:
    """Issue a new token; the old one stops working at once. A revoked device is
    re-enabled with the new token. The token is returned once and only its hash is stored."""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such device")
    token = new_device_token()
    device.token_hash = hash_token(token)
    device.revoked_at = None
    session.commit()
    return DeviceCreated(**_out(device).model_dump(), token=token)
