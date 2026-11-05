"""Column types."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, Enum, TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp stored as UTC and always returned timezone-aware.

    SQLite has no timezone support, so values are stored as naive UTC. Naive values are
    refused on the way in, so a local time can never be stored by mistake.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def str_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """Store a StrEnum by value as text, with a CHECK constraint on the allowed values."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(m.value) for m in enum_class),
        values_callable=lambda members: [m.value for m in members],
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
