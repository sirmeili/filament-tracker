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
    provisional: bool


class Counts(BaseModel):
    sealed: int = 0
    open: int = 0
    empty: int = 0
    unknown: int = 0


class ProductSummary(BaseModel):
    """A product with its spool counts: one inventory card."""

    product: ProductDetail
    counts: Counts
    low_stock: bool


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
    likely_empty: list[SpoolRow] = Field(description="From the AMS, arriving in M5")
