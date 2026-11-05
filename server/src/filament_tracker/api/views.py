"""Turn database rows into the response bodies in `read_schemas`."""

from uuid import UUID

from filament_tracker.api.read_schemas import (
    Counts,
    EventOut,
    ProductDetail,
    ProductSummary,
    SpoolDetail,
    SpoolRow,
    TagOut,
    UnidentifiedTag,
)
from filament_tracker.db.models import Event, Product, Spool, Tag
from filament_tracker.domain.enums import EventType
from filament_tracker.services.queries import UNKNOWN, ProductCounts


def product_detail(product: Product) -> ProductDetail:
    return ProductDetail.model_validate(product, from_attributes=True)


def product_summary(item: ProductCounts) -> ProductSummary:
    return ProductSummary(
        product=product_detail(item.product),
        counts=Counts(**item.counts),
        low_stock=item.low_stock,
    )


def spool_row(spool: Spool) -> SpoolRow:
    return SpoolRow(
        id=spool.id,
        state=spool.state.value if spool.state else UNKNOWN,
        product=product_detail(spool.product),
        placeholder=spool.tray_uid is None,
        location=spool.location,
        remaining_pct=spool.remaining_pct,
        received_at=spool.received_at,
        opened_at=spool.opened_at,
        emptied_at=spool.emptied_at,
    )


def _reverts(event: Event) -> UUID | None:
    if event.type != EventType.REVERT or not event.payload_json:
        return None
    target = event.payload_json.get("reverts")
    return UUID(target) if target else None


def event_out(event: Event) -> EventOut:
    product = event.spool.product
    return EventOut(
        id=event.id,
        spool_id=event.spool_id,
        product_name=product.display_name,
        color_rgba=product.color_rgba,
        type=event.type.value,
        source=event.source.value,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        flagged=event.flagged,
        device_id=event.device_id,
        device_name=event.device.name if event.device else None,
        username=event.user.username if event.user else None,
        reverts=_reverts(event),
        reverted_by=event.reverted_by,
        can_undo=event.type != EventType.REVERT and event.reverted_by is None,
        reviewed_at=event.reviewed_at,
        reviewed_by=event.reviewer.username if event.reviewer else None,
    )


def tag_out(tag: Tag) -> TagOut:
    return TagOut(
        uid=tag.uid,
        first_seen_at=tag.first_seen_at,
        decoded=tag.decoded_json,
        decoder_version=tag.decoder_version,
    )


def spool_detail(spool: Spool, events: list[Event]) -> SpoolDetail:
    return SpoolDetail(
        **spool_row(spool).model_dump(),
        notes=spool.notes,
        tags=[tag_out(t) for t in sorted(spool.tags, key=lambda t: t.first_seen_at)],
        events=[event_out(e) for e in events],
    )


def unidentified_tag(tag: Tag) -> UnidentifiedTag:
    return UnidentifiedTag(
        uid=tag.uid,
        first_seen_at=tag.first_seen_at,
        readable=tag.decoded_json is not None,
        decoded=tag.decoded_json,
    )
