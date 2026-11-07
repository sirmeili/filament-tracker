"""App settings, by group (Admin only). See Settings and first start in docs/SPEC.md.

Secrets are write-only: they read back only as set or not set. Saving a group applies it
at once (the Home Assistant links restart). Errors name the setting, never its value.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from filament_tracker.app_settings.registry import GROUPS, HOME_ASSISTANT, MAX_VALUE, group
from filament_tracker.app_settings.store import (
    Current,
    SettingsInvalid,
    SettingsStore,
    Source,
    UnknownSetting,
)
from filament_tracker.auth import Admin
from filament_tracker.ha.check import CheckResult, check_broker, check_rest
from filament_tracker.ha.link import HomeAssistantLink, ha_config

router = APIRouter(tags=["settings"])

Value = Annotated[str, Field(max_length=MAX_VALUE * 2)]


class SettingOut(BaseModel):
    key: str
    # None for a secret (write-only) and for a setting that is not set.
    value: str | None
    secret: bool
    # Whether it has a value: for a secret, the only thing that is ever read back.
    set: bool
    source: Source
    # Whether .env sets it, so "Use the .env value" can say what it goes back to.
    has_env: bool
    # A saved secret this server's key cannot open; it needs entering again.
    unreadable: bool


class GroupOut(BaseModel):
    group: str
    settings: list[SettingOut]


class GroupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # New values by key. An empty secret keeps the saved one; an empty plain value turns
    # the setting off in the app.
    values: dict[str, Value] = Field(default_factory=dict, max_length=32)
    # Secrets to remove.
    clear: list[str] = Field(default_factory=list, max_length=32)


class TestOut(BaseModel):
    mqtt: CheckResult
    events: CheckResult


def _out(current: Current) -> SettingOut:
    secret = current.definition.secret
    return SettingOut(
        key=current.key,
        value=None if secret else current.value,
        secret=secret,
        set=current.value is not None,
        source=current.source,
        has_env=current.has_env,
        unreadable=current.unreadable,
    )


def _store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def _apply(request: Request, name: str) -> None:
    if name == HOME_ASSISTANT:
        link: HomeAssistantLink = request.app.state.home_assistant
        link.reload()


def _group_name(name: str) -> str:
    if name not in GROUPS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such settings group")
    return name


def _invalid(error: SettingsInvalid) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"problems": error.problems})


GroupName = Annotated[str, Path(max_length=64)]


@router.get("/settings/{name}", response_model=GroupOut)
def read_group(name: GroupName, _: Admin, request: Request) -> GroupOut:
    name = _group_name(name)
    return GroupOut(group=name, settings=[_out(c) for c in _store(request).group(name)])


@router.put("/settings/{name}", response_model=GroupOut)
def save_group(name: GroupName, body: GroupIn, principal: Admin, request: Request) -> GroupOut:
    name = _group_name(name)
    store = _store(request)
    user_id = principal.user.id if principal.user else None
    keys = [d.key for d in group(name)]
    try:
        written = store.save(body.values, body.clear, keys=keys, user_id=user_id)
    except SettingsInvalid as error:
        raise _invalid(error) from None
    if written:
        _apply(request, name)
    return GroupOut(group=name, settings=[_out(c) for c in store.group(name)])


@router.delete("/settings/{name}/{key}", status_code=status.HTTP_204_NO_CONTENT)
def use_env_value(
    name: GroupName, key: Annotated[str, Path(max_length=64)], principal: Admin, request: Request
) -> Response:
    name = _group_name(name)
    if key not in {d.key for d in group(name)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such setting")
    user_id = principal.user.id if principal.user else None
    try:
        if _store(request).reset(key, user_id=user_id):
            _apply(request, name)
    except UnknownSetting:  # pragma: no cover - checked above
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such setting") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(f"/settings/{HOME_ASSISTANT}/test", response_model=TestOut)
def test_home_assistant(body: GroupIn, _: Admin, request: Request) -> TestOut:
    """Try the broker and Home Assistant once, with the values entered (not saved) on top of
    the saved ones. Results are categories only."""
    store = _store(request)
    keys = {d.key for d in group(HOME_ASSISTANT)}
    try:
        entered = store.check(body.values, keys)
    except SettingsInvalid as error:
        raise _invalid(error) from None
    unknown = {k: "not a setting here" for k in body.clear if k not in keys}
    if unknown:
        raise _invalid(SettingsInvalid(unknown))
    config = ha_config(store, entered, cleared=body.clear)
    return TestOut(mqtt=check_broker(config.broker), events=check_rest(config.rest))
