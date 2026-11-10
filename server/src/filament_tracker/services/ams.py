"""Apply what the AMS reports to spools and slots ("Automatic detection from the AMS").

- A tray UID seen for the first time becomes a spool, recorded as `opened` (an implicit
  receive) with source `ams` and flagged for review. Its product is the one existing
  product with the same material ID and color, or else a new provisional product marked
  as made from the AMS, which keeps the tray's material ID so a scanned tag can fill it in.
- A known spool that has never been opened by the AMS, and is sealed or Unknown, is
  recorded as `opened`. Once per spool: an undone AMS `opened` is not recorded again.
- The remaining % is written to the spool only when it changes; more than 0% brings back a
  dismissed "Likely empty" suggestion.
- Each slot's row records what is loaded, so pages can show where a spool is.

Callers own the transaction: this flushes but does not commit.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Printer, PrinterSlot, Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.events import append_event

logger = logging.getLogger(__name__)

UNKNOWN_TYPE = "Unknown"
UNKNOWN_COLOR = "00000000"


def ingest(session: Session, printer: Printer, trays: list[TrayReport], now: datetime) -> None:
    """Bring the printer's slots and their spools up to date with a full AMS view."""
    slots = {(s.ams_index, s.tray_index): s for s in printer.slots}
    for tray in trays:
        key = (tray.ams_index, tray.tray_index)
        slot = slots.pop(key, None)
        if slot is None:
            slot = PrinterSlot(ams_index=key[0], tray_index=key[1], updated_at=now)
            printer.slots.append(slot)
        spool = _track_spool(session, printer, tray, now) if tray.tray_uuid else None
        _update_slot(slot, tray, spool, now)
    for gone in slots.values():
        # The AMS unit is no longer reported.
        printer.slots.remove(gone)
    session.flush()


def _update_slot(slot: PrinterSlot, tray: TrayReport, spool: Spool | None, now: datetime) -> None:
    values = {
        "tray_uuid": tray.tray_uuid,
        "spool_id": spool.id if spool else None,
        "filament_type": tray.filament_type,
        "color_rgba": tray.color_rgba,
        "remaining_pct": tray.remaining_pct,
    }
    if any(getattr(slot, name) != value for name, value in values.items()):
        for name, value in values.items():
            setattr(slot, name, value)
        slot.spool = spool
        slot.updated_at = now


def _track_spool(session: Session, printer: Printer, tray: TrayReport, now: datetime) -> Spool:
    spool = session.scalar(select(Spool).where(Spool.tray_uid == tray.tray_uuid))
    where = {"printer_id": printer.id, "ams": tray.ams_index, "tray": tray.tray_index}
    if spool is None:
        spool = Spool(tray_uid=tray.tray_uuid, product=_match_product(session, tray))
        session.add(spool)
        append_event(
            session, spool, EventType.OPENED, EventSource.AMS, now, payload=where, flag=True
        )
        logger.info("new spool %s first seen in %s", spool.id, printer.name)
    elif spool.state in (None, SpoolState.SEALED) and not _opened_by_ams(spool):
        append_event(session, spool, EventType.OPENED, EventSource.AMS, now, payload=where)
        logger.info("spool %s opened in %s", spool.id, printer.name)

    remaining = tray.remaining_pct
    if remaining is not None and spool.remaining_pct != remaining:
        spool.remaining_pct = remaining
        if remaining > 0:
            spool.likely_empty_dismissed_at = None
    return spool


def _opened_by_ams(spool: Spool) -> bool:
    return any(e.type == EventType.OPENED and e.source == EventSource.AMS for e in spool.events)


def _match_product(session: Session, tray: TrayReport) -> Product:
    """The one product with the tray's material ID and color, or a new provisional one."""
    if tray.material_id and tray.color_rgba:
        candidates = session.scalars(
            select(Product).where(
                Product.material_id == tray.material_id,
                Product.color_rgba == tray.color_rgba,
            )
        ).all()
        if len(candidates) == 1:
            return candidates[0]
    color = tray.color_rgba or UNKNOWN_COLOR
    kind = tray.sub_brand or tray.filament_type or UNKNOWN_TYPE
    product = Product(
        material_id=tray.material_id or None,
        filament_type=tray.filament_type or UNKNOWN_TYPE,
        color_rgba=color,
        display_name=f"{kind} #{color[:6]}",
        provisional=True,
        from_ams=True,
    )
    session.add(product)
    return product
