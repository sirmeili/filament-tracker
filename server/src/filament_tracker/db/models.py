"""Database tables, following the Tables section of docs/SPEC.md.

The event table is the source of truth. A spool's state and dates are a projection of
its events, rebuilt by the event log after every write.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from filament_tracker.db.types import UtcDateTime, str_enum, utcnow
from filament_tracker.domain.enums import EventSource, EventType, SpoolState

# Stable constraint names, so Alembic can alter SQLite tables in batch mode.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UtcDateTime()}


class Product(Base):
    """One filament product, such as Black PLA Basic.

    Provisional products (from the AMS or manual entry) have no material or variant ID
    until one of their tags is scanned. SQLite treats NULLs as distinct, so any number of
    provisional products can exist alongside the unique product key.
    """

    __tablename__ = "product"
    __table_args__ = (UniqueConstraint("material_id", "variant_id", "color_rgba"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[str | None] = mapped_column(String(16))
    variant_id: Mapped[str | None] = mapped_column(String(16))
    filament_type: Mapped[str] = mapped_column(String(32))
    color_rgba: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str] = mapped_column(String(100))
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0)
    provisional: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    spools: Mapped[list["Spool"]] = relationship(back_populates="product")


class Spool(Base):
    """One physical spool. A manual placeholder has no tray UID until it is scanned.

    `state` is None ("Unknown" in the spec's action table) when every event that would
    give the spool a state has been undone.
    """

    __tablename__ = "spool"

    id: Mapped[int] = mapped_column(primary_key=True)
    tray_uid: Mapped[str | None] = mapped_column(String(32), unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    state: Mapped[SpoolState | None] = mapped_column(str_enum(SpoolState, "spool_state"))
    received_at: Mapped[datetime | None]
    opened_at: Mapped[datetime | None]
    emptied_at: Mapped[datetime | None]
    remaining_pct: Mapped[int | None]
    location: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    product: Mapped[Product] = relationship(back_populates="spools")
    tags: Mapped[list["Tag"]] = relationship(back_populates="spool")
    events: Mapped[list["Event"]] = relationship(back_populates="spool")


class Tag(Base):
    """One RFID tag. Unreadable or unknown tags are kept with no spool."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(8), unique=True)
    spool_id: Mapped[int | None] = mapped_column(ForeignKey("spool.id"), index=True)
    raw_blocks: Mapped[list[str] | None] = mapped_column(JSON)
    decoded_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decoder_version: Mapped[int | None]
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow)

    spool: Mapped[Spool | None] = relationship(back_populates="tags")


class Device(Base):
    """A registered scanner. Only a hash of its token is stored."""

    __tablename__ = "device"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    revoked_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime | None]
    fw_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Event(Base):
    """An immutable entry in a spool's history. Undo writes a new `revert` event.

    `recorded_at` is when the server stored the event; replay orders by `occurred_at`
    and breaks ties with it.
    """

    __tablename__ = "event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"), index=True)
    type: Mapped[EventType] = mapped_column(str_enum(EventType, "event_type"))
    source: Mapped[EventSource] = mapped_column(str_enum(EventSource, "event_source"))
    device_id: Mapped[str | None] = mapped_column(ForeignKey("device.id"))
    occurred_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reverted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event.id"))

    spool: Mapped[Spool] = relationship(back_populates="events")


class Printer(Base):
    """A printer watched over MQTT (used from M5)."""

    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    serial: Mapped[str] = mapped_column(String(32), unique=True)
    host: Mapped[str] = mapped_column(String(255))
