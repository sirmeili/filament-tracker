"""Printers watched over MQTT, for the Devices page (Admin): add, edit, test and remove a
printer, and see its online status, certificate pin and AMS slots. The access code is
write-only: it is never part of a response or a log line.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, SecretStr, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.api.read_schemas import ProductDetail
from filament_tracker.api.schemas import Strict
from filament_tracker.api.views import product_detail
from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.auth import Admin, DbSession, Principal
from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer, PrinterSlot, Spool
from filament_tracker.db.types import utcnow
from filament_tracker.printer.link import LinkStatus
from filament_tracker.printer.probe import PrinterCheck, check_printer
from filament_tracker.services.printers import (
    access_code,
    access_code_unreadable,
    seal_access_code,
)
from filament_tracker.services.queries import UNKNOWN

logger = logging.getLogger(__name__)

router = APIRouter(tags=["printers"])

# A printer reports at least every few minutes while connected (pushall every 30 min,
# and changes as they happen); one silent for 5 minutes counts as offline.
ONLINE_WINDOW = timedelta(minutes=5)


class SlotSpool(BaseModel):
    id: int
    state: str
    product: ProductDetail


class SlotOut(BaseModel):
    ams_index: int = Field(description="0-3: AMS 1 to 4; 128 and up: AMS HT 1, 2...")
    tray_index: int = Field(description="0-based; shown as slot 1 to 4")
    filament_type: str | None
    color_rgba: str | None
    remaining_pct: int | None
    spool: SlotSpool | None = Field(description="Null for an empty slot or a spool without a tag")
    updated_at: datetime


class PrinterOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    serial: str = Field(description="The printer's serial, or the alias an MQTT proxy uses")
    configured: bool = Field(description="False without a usable access code: not connecting")
    access_code_set: bool = Field(description="Whether an access code is saved; never the code")
    access_code_unreadable: bool = Field(
        description="A saved access code this server's key cannot open; enter it again"
    )
    connection: str = Field(
        description="starting, connected, disconnected, pin_mismatch, or not_configured"
    )
    online: bool = Field(description="Reported in the last 5 minutes")
    last_report_at: datetime | None
    pinned_sha256: str | None = Field(description="The pinned certificate's fingerprint")
    presented_sha256: str | None = Field(
        description="On a pin mismatch, the fingerprint the printer presented instead"
    )
    slots: list[SlotOut]


def _slot(slot: PrinterSlot) -> SlotOut:
    spool: Spool | None = slot.spool
    return SlotOut(
        ams_index=slot.ams_index,
        tray_index=slot.tray_index,
        filament_type=slot.filament_type,
        color_rgba=slot.color_rgba,
        remaining_pct=slot.remaining_pct,
        spool=SlotSpool(
            id=spool.id,
            state=spool.state.value if spool.state else UNKNOWN,
            product=product_detail(spool.product),
        )
        if spool
        else None,
        updated_at=slot.updated_at,
    )


def _out(printer: Printer, link: LinkStatus | None, now: datetime, box: SecretBox) -> PrinterOut:
    return PrinterOut(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        port=printer.port,
        serial=printer.serial,
        configured=link is not None,
        access_code_set=bool(printer.access_code),
        access_code_unreadable=access_code_unreadable(box, printer),
        connection=link.state.value if link else "not_configured",
        online=printer.last_report_at is not None and now - printer.last_report_at <= ONLINE_WINDOW,
        last_report_at=printer.last_report_at,
        pinned_sha256=printer.cert_sha256,
        presented_sha256=link.presented_sha256 if link else None,
        slots=[_slot(s) for s in printer.slots],
    )


def _status(request: Request, printer_id: int) -> LinkStatus | None:
    manager = getattr(request.app.state, "printers", None)
    return manager.status(printer_id) if manager else None


def _box(request: Request) -> SecretBox:
    return request.app.state.secret_box


def _who(caller: Principal) -> int | None:
    return caller.user.id if caller.user is not None else None


def _reload(request: Request, printer_id: int) -> None:
    manager = getattr(request.app.state, "printers", None)
    if manager is not None:
        manager.reload(printer_id)


def _one(session: Session, printer_id: int) -> Printer:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such printer")
    return printer


def _respond(request: Request, session: Session, printer: Printer) -> PrinterOut:
    session.refresh(printer)
    return _out(printer, _status(request, printer.id), utcnow(), _box(request))


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# A host name, IPv4 or IPv6 address; no scheme, path or user.
Host = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.:\[\]-]+$"
    ),
]
Port = Annotated[int, Field(ge=1, le=65535)]
Serial = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,32}$")]
AccessCode = Annotated[SecretStr, Field(min_length=1, max_length=64)]


class PrinterCreate(Strict):
    name: Name
    host: Host
    port: Port = 8883
    serial: Serial
    access_code: AccessCode


class PrinterUpdate(Strict):
    """Only the fields given change. A missing access code keeps the saved one."""

    name: Name | None = None
    host: Host | None = None
    port: Port | None = None
    serial: Serial | None = None
    access_code: AccessCode | None = None


class PrinterTest(Strict):
    """Values entered on the page but not saved; the rest come from the saved printer."""

    host: Host | None = None
    port: Port | None = None
    access_code: AccessCode | None = None


class PrinterTestOut(BaseModel):
    result: PrinterCheck


def _serial_taken(session: Session, serial: str, printer_id: int | None = None) -> None:
    other = session.scalar(select(Printer).where(Printer.serial == serial))
    if other is not None and other.id != printer_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "another printer has this serial")


@router.post("/printers", response_model=PrinterOut, status_code=status.HTTP_201_CREATED)
def add_printer(
    body: PrinterCreate, request: Request, caller: Admin, session: DbSession
) -> PrinterOut:
    """Add a printer and connect to it. The first connection pins its certificate."""
    _serial_taken(session, body.serial)
    printer = Printer(name=body.name, host=body.host, port=body.port, serial=body.serial)
    session.add(printer)
    session.flush()
    seal_access_code(_box(request), printer, body.access_code.get_secret_value())
    session.commit()
    logger.info("printer %s added by user %s", printer.id, _who(caller))
    _reload(request, printer.id)
    return _respond(request, session, printer)


@router.patch("/printers/{printer_id}", response_model=PrinterOut)
def edit_printer(
    printer_id: int, body: PrinterUpdate, request: Request, caller: Admin, session: DbSession
) -> PrinterOut:
    """Change a printer and reconnect it. The certificate pin is kept, so a different
    certificate at a new address is refused like any other."""
    printer = _one(session, printer_id)
    if body.serial is not None:
        _serial_taken(session, body.serial, printer.id)
    for field in ("name", "host", "port", "serial"):
        value = getattr(body, field)
        if value is not None:
            setattr(printer, field, value)
    if body.access_code is not None:
        seal_access_code(_box(request), printer, body.access_code.get_secret_value())
    session.commit()
    logger.info("printer %s changed by user %s", printer.id, _who(caller))
    _reload(request, printer.id)
    return _respond(request, session, printer)


@router.delete("/printers/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_printer(
    printer_id: int, request: Request, caller: Admin, session: DbSession
) -> Response:
    """Stop watching a printer and forget it and its AMS slots. Events it recorded stay."""
    printer = _one(session, printer_id)
    session.delete(printer)
    session.commit()
    logger.info("printer %s removed by user %s", printer_id, _who(caller))
    _reload(request, printer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/printers/{printer_id}/test", response_model=PrinterTestOut)
def test_printer(
    printer_id: int, body: PrinterTest, request: Request, _: Admin, session: DbSession
) -> PrinterTestOut:
    """Connect once with the saved values, or the ones entered, and say how it went."""
    printer = _one(session, printer_id)
    code = body.access_code or access_code(_box(request), printer)
    if code is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"problems": {"access_code": "enter the access code"}},
        )
    config = PrinterConfig(
        name=printer.name,
        host=body.host or printer.host,
        port=body.port or printer.port,
        serial=printer.serial,
        access_code=code,
    )
    return PrinterTestOut(result=check_printer(config, printer.cert_sha256))


@router.get("/printers", response_model=list[PrinterOut])
def list_printers(request: Request, _: Admin, session: DbSession) -> list[PrinterOut]:
    query = (
        select(Printer)
        .options(
            selectinload(Printer.slots).selectinload(PrinterSlot.spool).selectinload(Spool.product)
        )
        .order_by(Printer.name, Printer.id)
    )
    now = utcnow()
    box = _box(request)
    return [_out(p, _status(request, p.id), now, box) for p in session.scalars(query)]


@router.post("/printers/{printer_id}/unpin", response_model=PrinterOut)
def unpin(printer_id: int, request: Request, _: Admin, session: DbSession) -> PrinterOut:
    """Forget the pinned certificate; the next connection pins the one it finds."""
    printer = _one(session, printer_id)
    printer.cert_sha256 = None
    session.commit()
    return _respond(request, session, printer)
