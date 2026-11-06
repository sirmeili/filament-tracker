"""Request and response bodies (Scan event payload and Server: API in docs/SPEC.md)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from filament_tracker.decoder.blocks import DATA_BLOCK_COUNT
from filament_tracker.domain.actions import ScreenAction

HexBlock = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{32}$")]
DeviceId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScanAction(StrEnum):
    RECEIVED = "received"
    OPENED = "opened"
    EMPTY = "empty"
    LOOKUP = "lookup"


class Feedback(StrEnum):
    """Scan response codes; the scanner maps each to a screen message and sound."""

    OK = "ok"
    OK_CREATED = "ok_created"
    ALREADY_IN_STATE = "already_in_state"
    FLAGGED = "flagged"
    UNREADABLE = "unreadable"
    ERROR = "error"


class ScanEvent(Strict):
    event_id: UUID
    device_id: DeviceId
    action: ScanAction
    tag_uid: Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{8}$")]
    blocks: Annotated[list[HexBlock], Field(max_length=DATA_BLOCK_COUNT)]
    read_ok: bool
    scanned_at: AwareDatetime | None = None
    fw_version: Annotated[str, StringConstraints(max_length=32)] | None = None


class ProductOut(BaseModel):
    id: int | None
    display_name: str
    filament_type: str
    color_rgba: str
    material_id: str | None
    variant_id: str | None


class SpoolOut(BaseModel):
    id: int
    state: str
    received_at: datetime | None
    opened_at: datetime | None
    emptied_at: datetime | None
    remaining_pct: int | None


class ScanResponse(BaseModel):
    """The answer to a scan.

    For a lookup, `state`, `actions` and `suggested` drive the screen. `actions` has three
    slots (left, middle, right); a null slot is blank. For an action, they describe the
    spool after the action. `placeholder` is true when the spool shown is a manual
    placeholder that this tag will be linked to.
    """

    feedback: Feedback
    event_id: UUID | None = None
    state: str
    product: ProductOut | None = None
    spool: SpoolOut | None = None
    actions: list[ScreenAction | None]
    suggested: ScreenAction | None
    placeholder: bool = False


class DeviceCreate(Strict):
    id: DeviceId
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class DeviceOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    last_seen_at: datetime | None
    fw_version: str | None
    queue_length: int | None = Field(description="Scans in the offline queue at the last heartbeat")
    online: bool = Field(description="Not revoked, and seen in the last 15 minutes")
    revoked: bool


class Heartbeat(Strict):
    """Sent by a scanner every 5 minutes."""

    fw_version: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    queue_length: Annotated[int, Field(ge=0, le=100_000)]


class DeviceCreated(DeviceOut):
    token: str = Field(description="Shown once; only a hash is stored.")


class RevertResponse(BaseModel):
    revert_event_id: UUID
    reverted_event_id: UUID
    spool: SpoolOut
