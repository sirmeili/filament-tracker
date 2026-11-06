"""Read-only queries behind the web app's pages. Nothing here writes."""

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from filament_tracker.db.models import Event, PrinterSlot, Product, Spool, Tag
from filament_tracker.domain.enums import EventSource, EventType, SpoolState

UNKNOWN = "unknown"


class InventorySort(StrEnum):
    NAME = "name"
    LOW_STOCK = "low_stock"


def is_nearly_out(spool: Spool) -> bool:
    """Open, reported by the AMS, and at or below the product's nearly-out %."""
    return (
        spool.state is SpoolState.OPEN
        and spool.remaining_pct is not None
        and spool.remaining_pct <= spool.product.nearly_out_pct
    )


@dataclass(frozen=True)
class ProductCounts:
    product: Product
    counts: dict[str, int]
    open_spools: tuple[Spool, ...] = ()

    @property
    def low_stock(self) -> bool:
        threshold = self.product.low_stock_threshold
        return threshold > 0 and self.counts.get(SpoolState.SEALED, 0) <= threshold


def _counts_by_product(session: Session) -> dict[int, dict[str, int]]:
    rows = session.execute(
        select(Spool.product_id, Spool.state, func.count()).group_by(Spool.product_id, Spool.state)
    )
    counts: dict[int, dict[str, int]] = defaultdict(dict)
    for product_id, state, count in rows:
        counts[product_id][state.value if state else UNKNOWN] = count
    return counts


def _open_by_product(session: Session, product_id: int | None = None) -> dict[int, list[Spool]]:
    query = select(Spool).where(Spool.state == SpoolState.OPEN)
    if product_id is not None:
        query = query.where(Spool.product_id == product_id)
    query = query.options(selectinload(Spool.product)).order_by(Spool.opened_at, Spool.id)
    spools: dict[int, list[Spool]] = defaultdict(list)
    for spool in session.scalars(query):
        spools[spool.product_id].append(spool)
    return spools


def _name_key(product: Product) -> tuple[str, int]:
    return product.display_name.lower(), product.id


def inventory(
    session: Session, *, filament_type: str | None = None, sort: InventorySort = InventorySort.NAME
) -> list[ProductCounts]:
    """Every product with its spool counts, including products with no spools left."""
    query = select(Product)
    if filament_type:
        query = query.where(func.lower(Product.filament_type) == filament_type.strip().lower())
    counts = _counts_by_product(session)
    open_spools = _open_by_product(session)
    items = [
        ProductCounts(p, counts.get(p.id, {}), tuple(open_spools.get(p.id, ())))
        for p in session.scalars(query)
    ]
    items.sort(key=lambda item: _name_key(item.product))
    if sort is InventorySort.LOW_STOCK:
        items.sort(key=lambda item: not item.low_stock)  # stable: low first, then by name
    return items


def product_counts(session: Session, product: Product) -> ProductCounts:
    return ProductCounts(
        product,
        _counts_by_product(session).get(product.id, {}),
        tuple(_open_by_product(session, product.id).get(product.id, ())),
    )


def products(session: Session) -> list[Product]:
    return sorted(session.scalars(select(Product)), key=_name_key)


@dataclass(frozen=True)
class SpoolFilter:
    states: tuple[str, ...] = ()  # sealed, open, empty or unknown
    product_id: int | None = None
    filament_type: str | None = None
    location: str | None = None
    search: str | None = None


def _filtered_spools(spool_filter: SpoolFilter) -> Select[tuple[Spool]]:
    query = select(Spool).join(Spool.product)
    if spool_filter.states:
        known = [SpoolState(s) for s in spool_filter.states if s != UNKNOWN]
        conditions = [Spool.state.in_(known)] if known else []
        if UNKNOWN in spool_filter.states:
            conditions.append(Spool.state.is_(None))
        query = query.where(or_(*conditions))
    if spool_filter.product_id is not None:
        query = query.where(Spool.product_id == spool_filter.product_id)
    if spool_filter.filament_type is not None:
        wanted = spool_filter.filament_type.strip().lower()
        query = query.where(func.lower(Product.filament_type) == wanted)
    if spool_filter.location is not None:
        query = query.where(func.lower(Spool.location) == spool_filter.location.strip().lower())
    if spool_filter.search and spool_filter.search.strip():
        pattern = f"%{_escape_like(spool_filter.search.strip().lower())}%"
        query = query.where(
            or_(
                *(
                    func.lower(column).like(pattern, escape="\\")
                    for column in (
                        Product.display_name,
                        Product.filament_type,
                        Spool.location,
                        Spool.notes,
                    )
                )
            )
        )
    return query


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def spools(
    session: Session, spool_filter: SpoolFilter, *, limit: int, offset: int
) -> tuple[list[Spool], int]:
    """A page of matching spools, newest first, and the total number that match."""
    query = _filtered_spools(spool_filter)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = session.scalars(
        query.options(
            selectinload(Spool.product),
            selectinload(Spool.slots).selectinload(PrinterSlot.printer),
        )
        .order_by(Spool.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(page), total


def _event_query() -> Select[tuple[Event]]:
    return select(Event).options(
        selectinload(Event.spool).selectinload(Spool.product),
        selectinload(Event.device),
        selectinload(Event.user),
        selectinload(Event.reviewer),
    )


def _newest_first(query: Select[tuple[Event]]) -> Select[tuple[Event]]:
    return query.order_by(Event.recorded_at.desc(), Event.id)


def events(
    session: Session,
    *,
    spool_id: int | None = None,
    source: EventSource | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Event], int]:
    """A page of events, newest first, and the total."""
    query = _event_query()
    if spool_id is not None:
        query = query.where(Event.spool_id == spool_id)
    if source is not None:
        query = query.where(Event.source == source)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = session.scalars(_newest_first(query).limit(limit).offset(offset))
    return list(page), total


def spool_events(session: Session, spool: Spool) -> list[Event]:
    return list(session.scalars(_newest_first(_event_query().where(Event.spool_id == spool.id))))


def flagged_events(session: Session) -> list[Event]:
    """Flagged events still in effect and not yet accepted. Undoing or accepting a flagged
    event takes it out of Review."""
    query = _event_query().where(
        Event.flagged.is_(True),
        Event.reverted_by.is_(None),
        Event.reviewed_at.is_(None),
        Event.type != EventType.REVERT,
    )
    return list(session.scalars(_newest_first(query)))


def unidentified_tags(session: Session) -> list[Tag]:
    query = (
        select(Tag)
        .where(Tag.spool_id.is_(None), Tag.dismissed_at.is_(None))
        .order_by(Tag.first_seen_at.desc(), Tag.id)
    )
    return list(session.scalars(query))


def likely_empty(session: Session) -> list[Spool]:
    """Open spools the AMS reports at 0%, unless the suggestion was dismissed."""
    query = (
        select(Spool)
        .where(
            Spool.state == SpoolState.OPEN,
            Spool.remaining_pct == 0,
            Spool.likely_empty_dismissed_at.is_(None),
        )
        .options(selectinload(Spool.product))
        .order_by(Spool.opened_at, Spool.id)
    )
    return list(session.scalars(query))
