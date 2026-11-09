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
from filament_tracker.domain.enums import EventSource, EventType, Role, SpoolState

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
    # AMS remaining % at or below which an open spool is shown as nearly out.
    nearly_out_pct: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
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
    # Set when its "Likely empty" suggestion is dismissed; cleared when the AMS reports more.
    likely_empty_dismissed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    product: Mapped[Product] = relationship(back_populates="spools")
    tags: Mapped[list["Tag"]] = relationship(back_populates="spool")
    events: Mapped[list["Event"]] = relationship(back_populates="spool")
    # The AMS slot the spool is loaded in, if any (normally at most one).
    slots: Mapped[list["PrinterSlot"]] = relationship(viewonly=True)


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
    # Set when an unidentified tag is dismissed from Review.
    dismissed_at: Mapped[datetime | None]

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
    # Scans waiting in the device's offline queue, from its last heartbeat.
    queue_length: Mapped[int | None]
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
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    occurred_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set when a person accepts a flagged event as correct (Review).
    reviewed_at: Mapped[datetime | None]
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reverted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event.id"))
    # The response sent for this event, returned again if the same event ID is retried.
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    spool: Mapped[Spool] = relationship(back_populates="events")
    device: Mapped[Device | None] = relationship()
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])


class User(Base):
    """A web app account. Usernames are stored in lower case, so they are unique
    regardless of case. Only an Argon2id hash of the password is stored."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(str_enum(Role, "user_role"))
    disabled_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    password_changed_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """A signed-in browser. Only a hash of the cookie value is stored."""

    __tablename__ = "session"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class Printer(Base):
    """A printer (or MQTT proxy) watched over MQTT, added on the Devices page or seeded once
    from the PRINTERS setting."""

    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    serial: Mapped[str] = mapped_column(String(32), unique=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=8883, server_default="8883")
    # The LAN access code, sealed with the settings key (AES-GCM); never the plain value.
    # None: not set, so the server does not connect.
    access_code: Mapped[str | None] = mapped_column(String(512))
    # SHA-256 of the TLS certificate pinned on first connect, as lower-case hex.
    cert_sha256: Mapped[str | None] = mapped_column(String(64))
    last_report_at: Mapped[datetime | None]

    slots: Mapped[list["PrinterSlot"]] = relationship(
        back_populates="printer",
        cascade="all, delete-orphan",
        order_by="(PrinterSlot.ams_index, PrinterSlot.tray_index)",
    )


class PrinterSlot(Base):
    """What the AMS last reported in one slot, and the spool it is (if it has a tray UID)."""

    __tablename__ = "printer_slot"
    __table_args__ = (UniqueConstraint("printer_id", "ams_index", "tray_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printer.id"), index=True)
    ams_index: Mapped[int]
    tray_index: Mapped[int]
    tray_uuid: Mapped[str | None] = mapped_column(String(32))
    spool_id: Mapped[int | None] = mapped_column(ForeignKey("spool.id"), index=True)
    filament_type: Mapped[str | None] = mapped_column(String(32))
    color_rgba: Mapped[str | None] = mapped_column(String(8))
    remaining_pct: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)

    printer: Mapped[Printer] = relationship(back_populates="slots")
    spool: Mapped[Spool | None] = relationship()


class Setting(Base):
    """A setting saved in the app, which wins over the `.env` value (see Settings and first
    start in docs/SPEC.md). Secrets hold AES-GCM ciphertext, never the plain value. No row
    means the `.env` value or the default is used."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(4096))
    secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))


class SeededPrinter(Base):
    """A serial from PRINTERS that has been added once. PRINTERS only seeds printers: after
    that they are edited (or removed) in the app, and a restart does not bring them back."""

    __tablename__ = "seeded_printer"

    serial: Mapped[str] = mapped_column(String(32), primary_key=True)
    seeded_at: Mapped[datetime] = mapped_column(default=utcnow)
