import pytest

from filament_tracker.domain.actions import ScreenAction, menu_for
from filament_tracker.domain.enums import SpoolState

RECV, OPEN, EMPTY, INFO, CANCEL = (
    ScreenAction.RECEIVED,
    ScreenAction.OPENED,
    ScreenAction.EMPTY,
    ScreenAction.INFO,
    ScreenAction.CANCEL,
)


@pytest.mark.parametrize(
    ("state", "slots", "suggested"),
    [
        (None, (RECV, OPEN, EMPTY), RECV),
        (SpoolState.SEALED, (OPEN, EMPTY, CANCEL), OPEN),
        (SpoolState.OPEN, (EMPTY, INFO, CANCEL), EMPTY),
        (SpoolState.EMPTY, (INFO, None, CANCEL), INFO),
    ],
)
def test_menus_match_the_spec_table(
    state: SpoolState | None,
    slots: tuple[ScreenAction | None, ...],
    suggested: ScreenAction,
) -> None:
    menu = menu_for(state)

    assert menu.slots == slots
    assert menu.suggested == suggested
    assert menu.suggested in menu.allowed


def test_empty_slots_are_not_allowed_actions() -> None:
    assert menu_for(SpoolState.EMPTY).allowed == [INFO, CANCEL]
