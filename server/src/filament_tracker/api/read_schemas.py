"""Response bodies for the pages of the web app (Server: web UI in docs/SPEC.md)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Matching items across all pages")
    limit: int
    offset: int


class ProductDetail(BaseModel):
    id: int
    display_name: str
    filament_type: str
    color_rgba: str = Field(description="RRGGBBAA, for the color swatch")
    material_id: str | None
    variant_id: str | None
    low_stock_threshold: int = Field(description="Low on stock at or below this; 0 is off")
    nearly_out_pct: int = Field(description="An open spool at or below this AMS % is nearly out")
    provisional: bool
    from_ams: bool = Field(description="Made from an AMS report rather than by hand")


class Counts(BaseModel):
    sealed: int = 0
    open: int = 0
    empty: int = 0
    unknown: int = 0


class OpenSpool(BaseModel):
    id: int
    remaining_pct: int | None = Field(description="From the AMS; null until it reports one")
    nearly_out: bool = Field(description="Remaining % known and at or below the product's cutoff")


class ProductSummary(BaseModel):
    """A product with its spool counts: one inventory card."""

    product: ProductDetail
    counts: Counts
    low_stock: bool
    open_spools: list[OpenSpool] = Field(description="Open spools, oldest opened first")


class AmsSlotRef(BaseModel):
    printer_id: int
    printer_name: str
    ams_index: int = Field(description="0-3: AMS 1 to 4; 128 and up: AMS HT 1, 2...")
    tray_index: int = Field(description="0-based; shown as slot 1 to 4")


class SpoolRow(BaseModel):
    id: int
    state: str = Field(description="sealed, open, empty or unknown")
    product: ProductDetail
    placeholder: bool = Field(description="Added by hand and not yet linked to a tag")
    location: str | None
    remaining_pct: int | None
    received_at: datetime | None
    opened_at: datetime | None
    emptied_at: datetime | None
    ams_slot: AmsSlotRef | None = Field(description="Where the spool is loaded, if anywhere")


class TagOut(BaseModel):
    uid: str
    first_seen_at: datetime
    decoded: dict[str, Any] | None = Field(description="Decoded tag fields; null if unreadable")
    decoder_version: int | None


class EventOut(BaseModel):
    id: UUID
    spool_id: int
    product_name: str
    color_rgba: str
    type: str
    source: str
    occurred_at: datetime
    recorded_at: datetime
    flagged: bool
    device_id: str | None
    device_name: str | None
    username: str | None
    reverts: UUID | None = Field(description="For an undo: the event it undid")
    reverted_by: UUID | None
    can_undo: bool
    reviewed_at: datetime | None = Field(description="When a flagged event was accepted")
    reviewed_by: str | None = Field(description="Who accepted it; null for the admin token")


class SpoolDetail(SpoolRow):
    notes: str | None
    spool_weight_g: int | None = Field(description="Filament weight from the tag")
    grams_left: int | None = Field(description="Remaining % of the tag's weight, when both known")
    tags: list[TagOut]
    events: list[EventOut] = Field(description="Newest first")


class UnidentifiedTag(BaseModel):
    uid: str
    first_seen_at: datetime
    readable: bool = Field(description="False if the tag's blocks could not be decoded")
    decoded: dict[str, Any] | None


class ReviewOut(BaseModel):
    flagged_events: list[EventOut] = Field(description="Flagged and not undone, newest first")
    unidentified_tags: list[UnidentifiedTag]
    likely_empty: list[SpoolRow] = Field(
        description="Open spools the AMS reports at 0%, not dismissed"
    )
