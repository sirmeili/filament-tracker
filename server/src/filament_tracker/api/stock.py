"""Inventory, products and spools: what is on the shelf (Viewer and up)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from filament_tracker.api.read_schemas import (
    Page,
    ProductDetail,
    ProductSummary,
    SpoolDetail,
    SpoolRow,
)
from filament_tracker.api.views import product_detail, product_summary, spool_detail, spool_row
from filament_tracker.auth import DbSession, Viewer
from filament_tracker.db.models import Product, Spool
from filament_tracker.services import queries
from filament_tracker.services.queries import InventorySort, SpoolFilter

router = APIRouter(tags=["stock"])

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
StateName = Annotated[str, Query(pattern="^(sealed|open|empty|unknown)$")]


@router.get("/inventory", response_model=list[ProductSummary])
def get_inventory(
    _: Viewer,
    session: DbSession,
    filament_type: Annotated[
        str | None, Query(alias="type", max_length=32, description="Filament type, e.g. PLA")
    ] = None,
    sort: InventorySort = InventorySort.NAME,
) -> list[ProductSummary]:
    """Spool counts per product, with low-stock flags and each open spool's remaining %.
    Low stock: sealed count at or below the product's threshold, when the threshold is above
    0. Nearly out: an open spool's AMS % at or below the product's nearly-out %."""
    items = queries.inventory(session, filament_type=filament_type, sort=sort)
    return [product_summary(item) for item in items]


@router.get("/products", response_model=list[ProductDetail])
def list_products(_: Viewer, session: DbSession) -> list[ProductDetail]:
    return [product_detail(p) for p in queries.products(session)]


@router.get("/products/{product_id}", response_model=ProductSummary)
def get_product(product_id: int, _: Viewer, session: DbSession) -> ProductSummary:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such product")
    return product_summary(queries.product_counts(session, product))


@router.get("/spools", response_model=Page[SpoolRow])
def list_spools(
    _: Viewer,
    session: DbSession,
    state: Annotated[list[StateName] | None, Query()] = None,
    product_id: int | None = None,
    filament_type: Annotated[
        str | None, Query(alias="type", max_length=32, description="Filament type, e.g. PLA")
    ] = None,
    location: Annotated[str | None, Query(max_length=100)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Search text")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[SpoolRow]:
    """Spools, newest first. `state` may be repeated; search matches product name, filament
    type, location and notes."""
    spool_filter = SpoolFilter(
        states=tuple(state or ()),
        product_id=product_id,
        filament_type=filament_type,
        location=location,
        search=q,
    )
    items, total = queries.spools(session, spool_filter, limit=limit, offset=offset)
    return Page[SpoolRow](
        items=[spool_row(s) for s in items], total=total, limit=limit, offset=offset
    )


@router.get("/spools/{spool_id}", response_model=SpoolDetail)
def get_spool(spool_id: int, _: Viewer, session: DbSession) -> SpoolDetail:
    spool = session.get(Spool, spool_id)
    if spool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such spool")
    return spool_detail(spool, queries.spool_events(session, spool))
