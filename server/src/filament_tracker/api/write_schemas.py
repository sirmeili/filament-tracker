"""Request bodies for changes made in the web app, and the answer to a manual action."""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field, StringConstraints

from filament_tracker.api.read_schemas import EventOut, SpoolDetail
from filament_tracker.api.schemas import Strict


def _blank_is_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


Location = Annotated[str | None, StringConstraints(max_length=100), AfterValidator(_blank_is_none)]
Notes = Annotated[str | None, StringConstraints(max_length=2000), AfterValidator(_blank_is_none)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Threshold = Annotated[int, Field(ge=0, le=1000, description="Low on stock at or below; 0 is off")]
Rgba = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{8}$"), AfterValidator(str.upper)]
FilamentType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class ManualActionType(StrEnum):
    RECEIVED = "received"
    OPENED = "opened"
    EMPTY = "empty"


class SpoolUpdate(Strict):
    """Only the fields sent change; send null or "" to clear one."""

    location: Location = None
    notes: Notes = None


class BulkLocation(Strict):
    spool_ids: Annotated[list[int], Field(min_length=1, max_length=500)]
    location: Location = None


class ManualAction(Strict):
    action: ManualActionType
    occurred_at: AwareDatetime | None = Field(
        default=None, description="When it happened; defaults to now. Not in the future."
    )


class ManualSpool(Strict):
    """Manual entry: a spool whose tag cannot be read yet, recorded as received."""

    product_id: int
    received_at: AwareDatetime | None = None
    location: Location = None
    notes: Notes = None


class ProductCreate(Strict):
    """A provisional product, for manual entry before any of its tags is scanned."""

    display_name: Name
    filament_type: FilamentType
    color_rgba: Rgba
    low_stock_threshold: Threshold = 0


class ProductUpdate(Strict):
    display_name: Name | None = None
    low_stock_threshold: Threshold | None = None


class ActionResult(BaseModel):
    outcome: str = Field(description="applied, already_in_state or flagged")
    event: EventOut
    spool: SpoolDetail
