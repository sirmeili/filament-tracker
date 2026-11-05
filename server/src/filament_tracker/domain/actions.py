"""Actions the scanner offers after a scan ("Actions offered after a scan" in the spec).

Each state maps to three soft-key slots (left, middle, right) and a suggested action.
"""

from dataclasses import dataclass
from enum import StrEnum

from filament_tracker.domain.enums import SpoolState


class ScreenAction(StrEnum):
    RECEIVED = "received"
    OPENED = "opened"
    EMPTY = "empty"
    INFO = "info"
    CANCEL = "cancel"


@dataclass(frozen=True)
class ActionMenu:
    slots: tuple[ScreenAction | None, ScreenAction | None, ScreenAction | None]
    suggested: ScreenAction

    @property
    def allowed(self) -> list[ScreenAction]:
        return [slot for slot in self.slots if slot is not None]


_MENUS: dict[SpoolState | None, ActionMenu] = {
    None: ActionMenu(
        (ScreenAction.RECEIVED, ScreenAction.OPENED, ScreenAction.EMPTY), ScreenAction.RECEIVED
    ),
    SpoolState.SEALED: ActionMenu(
        (ScreenAction.OPENED, ScreenAction.EMPTY, ScreenAction.CANCEL), ScreenAction.OPENED
    ),
    SpoolState.OPEN: ActionMenu(
        (ScreenAction.EMPTY, ScreenAction.INFO, ScreenAction.CANCEL), ScreenAction.EMPTY
    ),
    SpoolState.EMPTY: ActionMenu((ScreenAction.INFO, None, ScreenAction.CANCEL), ScreenAction.INFO),
}


def menu_for(state: SpoolState | None) -> ActionMenu:
    """Return the soft-key menu for a spool in `state`; None means Unknown."""
    return _MENUS[state]
