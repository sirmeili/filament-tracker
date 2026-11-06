"""Printers watched over MQTT, for the Devices page (Admin): online status, the certificate
pin and each AMS slot. The access code is never part of a response."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from filament_tracker.api.read_schemas import ProductDetail
from filament_tracker.api.views import product_detail
from filament_tracker.auth import Admin, DbSession
from filament_tracker.db.models import Printer, PrinterSlot, Spool
from filament_tracker.db.types import utcnow
from filament_tracker.printer.link import LinkStatus
from filament_tracker.services.queries import UNKNOWN

router = APIRouter(tags=["printers"])

# A printer reports at least every few minutes while connected (pushall every 30 min,
# and changes as they happen); one silent for 5 minutes counts as offline.
ONLINE_WINDOW = timedelta(minutes=5)


class SlotSpool(BaseModel):
    id: int
    state: str
    product: ProductDetail


class SlotOut(BaseModel):
    ams_index: int = Field(description="0-based; shown as AMS 1, 2...")
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
    configured: bool = Field(description="False for a printer no longer in PRINTERS")
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


def _out(printer: Printer, link: LinkStatus | None, now: datetime) -> PrinterOut:
    return PrinterOut(
        id=printer.id,
        name=printer.name,
        host=printer.host,
        port=printer.port,
        configured=link is not None,
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
    return [_out(p, _status(request, p.id), now) for p in session.scalars(query)]


@router.post("/printers/{printer_id}/unpin", response_model=PrinterOut)
def unpin(printer_id: int, request: Request, _: Admin, session: DbSession) -> PrinterOut:
    """Forget the pinned certificate; the next connection pins the one it finds."""
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such printer")
    printer.cert_sha256 = None
    session.commit()
    session.refresh(printer)
    return _out(printer, _status(request, printer.id), utcnow())
