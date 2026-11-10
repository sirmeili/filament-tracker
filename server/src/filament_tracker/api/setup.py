"""First-start setup: create the first Admin and the starter settings.

Answers only from `TRUSTED_NETWORKS` (others get 404, as if it did not exist), needs the
setup code from the server's log, throttles wrong codes like sign-ins, and closes for good
once an Admin exists. A successful setup signs the new Admin in.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, StringConstraints

from filament_tracker.api.account_schemas import Me, Password, Username
from filament_tracker.api.auth import me_out
from filament_tracker.api.schemas import Strict
from filament_tracker.app_settings.store import SettingsInvalid, SettingsStore, Source
from filament_tracker.auth import DbSession, check_csrf, set_session_cookie, settings_of
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.net import client_ip, is_trusted
from filament_tracker.services.accounts import (
    AccountError,
    check_password_rules,
    create_user,
    normalize_username,
    start_session,
)
from filament_tracker.services.setup import SetupGate, setup_open
from filament_tracker.services.throttle import LoginThrottle

logger = logging.getLogger(__name__)
router = APIRouter(tags=["setup"])

# The throttle's "username" for wrong codes: there is one code, not one per user.
THROTTLE_KEY = "setup"
TOO_MANY = "too many wrong setup codes; try again later"
# The starter settings: the request field, and the setting it fills.
STARTERS = {"time_zone": "tz", "kdf_salt": "bambu_kdf_salt"}

Code = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Value = Annotated[str, StringConstraints(max_length=512)]


class SetupStatus(BaseModel):
    open: bool
    # Starter settings to ask for: those set neither in `.env` nor in the app.
    time_zone_needed: bool = False
    kdf_salt_needed: bool = False


class SetupRequest(Strict):
    code: Code
    username: Username
    password: Password
    time_zone: Value | None = None
    kdf_salt: Value | None = None


def _gate(request: Request) -> SetupGate:
    return request.app.state.setup_gate


def _store(request: Request) -> SettingsStore:
    return request.app.state.settings_store


def _throttle(request: Request) -> LoginThrottle:
    return request.app.state.setup_throttle


def _lan_only(request: Request) -> None:
    if not is_trusted(request, settings_of(request)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")


def _needed(store: SettingsStore, key: str) -> bool:
    return store.current(key).source == Source.DEFAULT


def _problems(problems: dict[str, str]) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"problems": problems})


def _starter_values(body: SetupRequest, store: SettingsStore) -> dict[str, str]:
    """The starter settings to save: given, not blank, and not already set."""
    values = {}
    for field, key in STARTERS.items():
        value = getattr(body, field)
        if value and value.strip() and _needed(store, key):
            values[key] = value
    return values


def _check(body: SetupRequest, store: SettingsStore, values: dict[str, str]) -> dict[str, str]:
    """Every problem with the request at once, by field; values are never repeated."""
    problems: dict[str, str] = {}
    try:
        normalize_username(body.username)
    except AccountError as error:
        problems["username"] = str(error)
    try:
        check_password_rules(body.password)
    except AccountError as error:
        problems["password"] = str(error)
    try:
        cleaned = store.check(values)
    except SettingsInvalid as error:
        fields = {key: field for field, key in STARTERS.items()}
        problems.update({fields[key]: message for key, message in error.problems.items()})
        cleaned = {}
    if problems:
        raise _problems(problems)
    return cleaned


@router.get("/setup", response_model=SetupStatus)
def setup_status(request: Request, session: DbSession) -> SetupStatus:
    """Whether setup is open, and which starter settings it asks for."""
    _lan_only(request)
    if not setup_open(session):
        return SetupStatus(open=False)
    store = _store(request)
    return SetupStatus(
        open=True,
        time_zone_needed=_needed(store, "tz"),
        kdf_salt_needed=_needed(store, "bambu_kdf_salt"),
    )


@router.post("/setup", response_model=Me, status_code=status.HTTP_201_CREATED)
def finish_setup(
    body: SetupRequest, request: Request, response: Response, session: DbSession
) -> Me:
    """Create the first Admin and save the starter settings, then sign the Admin in.
    Setup is then closed for good."""
    check_csrf(request)
    _lan_only(request)
    gate, throttle = _gate(request), _throttle(request)
    address = str(client_ip(request, settings_of(request)) or "unknown")
    with gate.lock:
        if not setup_open(session):
            raise HTTPException(status.HTTP_409_CONFLICT, "setup is closed: an admin exists")
        if throttle.blocked(THROTTLE_KEY, address):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
        if not gate.matches(body.code):
            throttle.failed(THROTTLE_KEY, address)
            logger.warning("first-start setup: a wrong setup code was entered")
            raise HTTPException(status.HTTP_403_FORBIDDEN, "the setup code is wrong")
        store = _store(request)
        values = _check(body, store, _starter_values(body, store))
        try:
            user = create_user(session, body.username, body.password, Role.ADMIN)
        except AccountError as error:
            raise _problems({"username": str(error)}) from None
        session.commit()
        store.save(values, user_id=user.id)
        gate.close()
        throttle.succeeded(THROTTLE_KEY)
        logger.info("first-start setup finished: admin user %s created; setup closed", user.id)
    days = store.session_days()
    token = start_session(session, user, days, utcnow())
    session.commit()
    set_session_cookie(request, response, token, days)
    return me_out(request, user)
