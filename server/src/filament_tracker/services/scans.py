"""Handle a scan from a scanner (POST /scans).

A lookup only reads: it decodes the tag and reports the spool, its state and the menu.
An action (received, opened, empty) creates whatever is missing (product, spool, tag),
records the event and stores the response on it, so a retry with the same event ID gets
the same answer without a second event. Unreadable tags are kept by UID with no spool.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_tracker.api.schemas import (
    Feedback,
    ProductOut,
    ScanAction,
    ScanEvent,
    ScanResponse,
    SpoolOut,
)
from filament_tracker.db.models import Device, Event, Product, Spool, Tag
from filament_tracker.decoder import DecodeError, TagRecord, decode
from filament_tracker.domain.actions import menu_for
from filament_tracker.domain.enums import EventSource, EventType
from filament_tracker.domain.state import Outcome
from filament_tracker.services.events import AppendResult, append_event

logger = logging.getLogger(__name__)

UNKNOWN = "unknown"


class EventIdConflict(Exception):
    """The event ID was already used by a different device."""


def handle_scan(session: Session, device: Device, scan: ScanEvent, now: datetime) -> ScanResponse:
    device.last_seen_at = now
    if scan.fw_version:
        device.fw_version = scan.fw_version

    if scan.action != ScanAction.LOOKUP:
        existing = session.get(Event, scan.event_id)
        if existing is not None:
            if existing.device_id != device.id or existing.result_json is None:
                raise EventIdConflict
            logger.info("scan %s from %s is a retry", scan.event_id, device.id)
            session.commit()
            return ScanResponse.model_validate(existing.result_json)

    record = _decode(scan)
    if record is None:
        _keep_unidentified(session, scan)
        session.commit()
        logger.info("unreadable %s scan from %s", scan.action, device.id)
        logger.debug("unreadable tag UID %s", scan.tag_uid.upper())
        return _response(Feedback.UNREADABLE, None, None)

    product = _find_product(session, record)
    spool = session.scalar(select(Spool).where(Spool.tray_uid == record.tray_uid))
    placeholder = _oldest_placeholder(session, product) if spool is None and product else None

    if scan.action == ScanAction.LOOKUP:
        session.commit()
        return _response(
            Feedback.OK,
            _product_out(product, record),
            spool or placeholder,
            placeholder=spool is None and placeholder is not None,
        )

    product = _ensure_product(session, product, record)
    linked = False
    if spool is None and placeholder is not None:
        spool, linked = placeholder, True
        spool.tray_uid = record.tray_uid
    elif spool is None:
        spool = Spool(tray_uid=record.tray_uid, product=product)
        session.add(spool)
    _keep_tag(session, scan, record, spool)

    result = append_event(
        session,
        spool,
        EventType(scan.action.value),
        EventSource.SCANNER,
        scan.scanned_at or now,
        device_id=device.id,
        event_id=scan.event_id,
        payload={"tag_uid": scan.tag_uid.upper(), "linked_placeholder": linked},
        flag=linked,
    )
    response = _response(
        _feedback(result), _product_out(product, record), spool, event_id=scan.event_id
    )
    result.event.result_json = response.model_dump(mode="json")
    session.commit()
    logger.info("%s scan from %s: %s", scan.action, device.id, response.feedback)
    logger.debug("tag %s, tray %s", record.tag_uid, record.tray_uid)
    return response


def _decode(scan: ScanEvent) -> TagRecord | None:
    if not scan.read_ok:
        return None
    try:
        record = decode(scan.blocks)
    except DecodeError:
        return None
    # A UID that disagrees with block 0 means the read is not trustworthy.
    return record if record.tag_uid == scan.tag_uid.upper() else None


def _find_product(session: Session, record: TagRecord) -> Product | None:
    """The product with this tag's key, or else the one provisional product it can fill in.

    A provisional product (made by hand for manual entry) matches when it has the tag's
    filament type and color and still has unlinked placeholders.
    """
    exact = session.scalar(
        select(Product).where(
            Product.material_id == record.material_id,
            Product.variant_id == record.variant_id,
            Product.color_rgba == record.color_rgba,
        )
    )
    if exact is not None:
        return exact
    candidates = session.scalars(
        select(Product)
        .join(Spool)
        .where(
            Product.provisional.is_(True),
            func.upper(Product.filament_type).in_(
                [record.filament_type.upper(), record.detailed_filament_type.upper()]
            ),
            func.upper(Product.color_rgba) == record.color_rgba,
            Spool.tray_uid.is_(None),
        )
        .distinct()
    ).all()
    return candidates[0] if len(candidates) == 1 else None


def _oldest_placeholder(session: Session, product: Product) -> Spool | None:
    return session.scalar(
        select(Spool)
        .where(
            Spool.product_id == product.id,
            Spool.tray_uid.is_(None),
            Spool.state.is_not(None),
        )
        .order_by(Spool.received_at, Spool.id)
        .limit(1)
    )


def _ensure_product(session: Session, product: Product | None, record: TagRecord) -> Product:
    if product is None:
        product = Product(
            material_id=record.material_id,
            variant_id=record.variant_id,
            filament_type=record.filament_type,
            color_rgba=record.color_rgba,
            display_name=_default_name(record),
        )
        session.add(product)
    elif product.provisional:
        # The first scanned tag fills in the provisional product's real identity.
        product.material_id = record.material_id
        product.variant_id = record.variant_id
        product.color_rgba = record.color_rgba
        product.provisional = False
    return product


def _keep_tag(session: Session, scan: ScanEvent, record: TagRecord, spool: Spool) -> None:
    tag = session.scalar(select(Tag).where(Tag.uid == record.tag_uid))
    if tag is None:
        tag = Tag(uid=record.tag_uid)
        session.add(tag)
    tag.spool = spool
    tag.raw_blocks = [b.upper() for b in scan.blocks]
    tag.decoded_json = record.to_json_dict()
    tag.decoder_version = record.decoder_version


def _keep_unidentified(session: Session, scan: ScanEvent) -> None:
    """Keep an unreadable tag by UID, without overwriting anything already known."""
    uid = scan.tag_uid.upper()
    if session.scalar(select(Tag).where(Tag.uid == uid)) is None:
        blocks = [b.upper() for b in scan.blocks] if scan.read_ok and scan.blocks else None
        session.add(Tag(uid=uid, raw_blocks=blocks))


def _feedback(result: AppendResult) -> Feedback:
    if result.event.flagged:
        return Feedback.FLAGGED
    if result.step.outcome is Outcome.ALREADY_IN_STATE:
        return Feedback.ALREADY_IN_STATE
    if result.step.implicit_receive:
        return Feedback.OK_CREATED
    return Feedback.OK


def _default_name(record: TagRecord) -> str:
    return f"{record.detailed_filament_type or record.filament_type} #{record.color_rgba[:6]}"


def _product_out(product: Product | None, record: TagRecord) -> ProductOut:
    if product is not None:
        return ProductOut.model_validate(product, from_attributes=True)
    return ProductOut(
        id=None,
        display_name=_default_name(record),
        filament_type=record.filament_type,
        color_rgba=record.color_rgba,
        material_id=record.material_id,
        variant_id=record.variant_id,
    )


def spool_out(spool: Spool) -> SpoolOut:
    return SpoolOut(
        id=spool.id,
        state=spool.state.value if spool.state else UNKNOWN,
        received_at=spool.received_at,
        opened_at=spool.opened_at,
        emptied_at=spool.emptied_at,
        remaining_pct=spool.remaining_pct,
    )


def _response(
    feedback: Feedback,
    product: ProductOut | None,
    spool: Spool | None,
    *,
    event_id: UUID | None = None,
    placeholder: bool = False,
) -> ScanResponse:
    if feedback is Feedback.UNREADABLE:
        return ScanResponse(
            feedback=feedback, state=UNKNOWN, actions=[None, None, None], suggested=None
        )
    menu = menu_for(spool.state if spool else None)
    return ScanResponse(
        feedback=feedback,
        event_id=event_id,
        state=spool.state.value if spool and spool.state else UNKNOWN,
        product=product,
        spool=spool_out(spool) if spool else None,
        actions=list(menu.slots),
        suggested=menu.suggested,
        placeholder=placeholder,
    )
