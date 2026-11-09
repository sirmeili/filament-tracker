"""First-start setup: LAN only, with the setup code from the log, throttled, and closed for
good once an Admin exists (Settings and first start, Security in docs/SPEC.md)."""

import logging
import re
from collections.abc import Iterator
from typing import Any

import pytest
from api_helpers import (
    ADMIN_TOKEN,
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    LAN_CLIENT,
    PASSWORD,
    browser,
    make_user,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.config import Settings
from filament_tracker.db.models import Setting, User
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app
from filament_tracker.services.setup import ALPHABET, SetupGate, new_code, normalize

CODE_PATTERN = re.compile(rf"setup code: ([{ALPHABET}]{{4}}-[{ALPHABET}]{{4}}-[{ALPHABET}]{{4}})")
SALT = "0A1B2C3D4E5F60718293A4B5C6D7E8F9"


class Started:
    """A running app, its LAN client and the setup code it logged (None if closed)."""

    def __init__(self, app: FastAPI, client: TestClient, code: str | None) -> None:
        self.app, self.client, self.code = app, client, code

    def setup(self, **fields: Any) -> Any:
        body = {"code": self.code, "username": "frank", "password": PASSWORD, **fields}
        return self.client.post("/api/v1/setup", json=body, headers=CSRF)


def _codes(caplog: pytest.LogCaptureFixture) -> list[str]:
    return CODE_PATTERN.findall(caplog.text)


@pytest.fixture
def start(caplog: pytest.LogCaptureFixture, db_url: str) -> Iterator[Any]:
    """Start the app (again, on the same database) with these settings."""
    caplog.set_level(logging.WARNING, logger="filament_tracker.services.setup")
    clients: list[TestClient] = []

    def started(**settings: Any) -> Started:
        app = create_app(
            Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None, **settings)
        )
        before = len(_codes(caplog))
        client = TestClient(app, base_url=BASE_URL, client=LAN_CLIENT)
        client.__enter__()
        clients.append(client)
        codes = _codes(caplog)[before:]
        assert len(codes) <= 1
        return Started(app, client, codes[0] if codes else None)

    yield started
    for client in clients:
        client.__exit__(None, None, None)


def _db(started: Started) -> Session:
    return started.app.state.session_factory()


# --- The code -------------------------------------------------------------------------------


def test_codes_are_random_and_readable() -> None:
    codes = {new_code() for _ in range(50)}

    assert len(codes) == 50
    assert all(re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code) for code in codes)
    assert not any(ch in code for code in codes for ch in "ILOU01")


def test_a_code_matches_typed_either_way() -> None:
    assert normalize(" k7qm-x3rd 9pta ") == "K7QMX3RD9PTA"


def test_a_closed_gate_matches_nothing() -> None:
    gate = SetupGate()

    assert not gate.matches("")
    assert not gate.matches("K7QM-X3RD-9PTA")


def test_each_start_logs_a_new_code_while_setup_is_open(start: Any) -> None:
    first = start()
    second = start()

    assert first.code is not None
    assert second.code is not None
    assert first.code != second.code
    # The first start's code no longer works.
    assert second.setup(code=first.code).status_code == 403


def test_no_code_is_made_once_an_admin_exists(start: Any) -> None:
    first = start()
    make_user(first.app, "frank", Role.ADMIN)

    again = start()

    assert again.code is None
    assert again.client.get("/api/v1/setup").json() == {
        "open": False,
        "time_zone_needed": False,
        "kdf_salt_needed": False,
    }


# --- Finishing setup ------------------------------------------------------------------------


def test_setup_asks_for_the_starter_settings_that_are_not_set(start: Any) -> None:
    started = start()

    assert started.client.get("/api/v1/setup").json() == {
        "open": True,
        "time_zone_needed": True,
        "kdf_salt_needed": True,
    }


def test_setup_skips_the_starter_settings_set_in_env(start: Any) -> None:
    started = start(tz="America/Chicago", bambu_kdf_salt=SALT)

    status = started.client.get("/api/v1/setup").json()
    response = started.setup(time_zone="Europe/Paris", kdf_salt="FF")

    assert status == {"open": True, "time_zone_needed": False, "kdf_salt_needed": False}
    assert response.status_code == 201
    assert response.json()["time_zone"] == "America/Chicago"
    with _db(started) as session:
        assert session.scalars(select(Setting)).all() == []


def test_setup_creates_the_admin_signs_them_in_and_closes(start: Any) -> None:
    started = start()

    response = started.setup(username="Frank", time_zone="America/Chicago", kdf_salt=SALT.lower())

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "username": "frank",
        "role": "admin",
        "time_zone": "America/Chicago",
    }
    assert started.client.get("/api/v1/auth/me").json()["username"] == "frank"
    assert started.client.get("/api/v1/setup").json()["open"] is False
    store = started.app.state.settings_store
    assert store.secret("bambu_kdf_salt").get_secret_value() == SALT
    with _db(started) as session:
        user = session.scalar(select(User))
        assert user.role == Role.ADMIN
        saved = session.get(Setting, "bambu_kdf_salt")
        assert SALT not in saved.value
        assert SALT.lower() not in saved.value
        assert saved.updated_by == user.id
    # Closed for good: the same code cannot make a second admin.
    assert started.setup(username="mallory").status_code == 409


def test_blank_starter_settings_are_left_unset(start: Any) -> None:
    started = start()

    response = started.setup(time_zone="  ", kdf_salt="")

    assert response.status_code == 201
    assert response.json()["time_zone"] == "UTC"
    assert started.app.state.settings_store.secret("bambu_kdf_salt") is None


def test_the_code_may_be_typed_in_lower_case_without_dashes(start: Any) -> None:
    started = start()

    assert started.setup(code=started.code.replace("-", "").lower()).status_code == 201


def test_setup_closes_when_an_admin_is_made_another_way(start: Any) -> None:
    started = start()
    make_user(started.app, "frank", Role.ADMIN)

    assert started.client.get("/api/v1/setup").json()["open"] is False
    assert started.setup(username="other").status_code == 409


def test_a_viewer_made_before_setup_does_not_close_it(start: Any) -> None:
    started = start()
    make_user(started.app, "frank", Role.VIEWER)

    taken = started.setup(username="frank")
    made = started.setup(username="frank-admin")

    assert taken.status_code == 422
    assert taken.json()["detail"] == {"problems": {"username": "that username is taken"}}
    assert made.status_code == 201


def test_every_problem_is_reported_at_once_without_echoing_values(start: Any) -> None:
    started = start()

    response = started.setup(
        username="x!",
        password="too-short",  # noqa: S106 - test value
        time_zone="Mars/Olympus",
        kdf_salt="not-hex-zz",
    )

    assert response.status_code == 422
    problems = response.json()["detail"]["problems"]
    assert set(problems) == {"username", "password", "time_zone", "kdf_salt"}
    for value in ("too-short", "Mars/Olympus", "not-hex-zz"):
        assert value not in response.text
    # Nothing was made, and setup is still open.
    assert started.client.get("/api/v1/setup").json()["open"] is True


def test_unknown_fields_are_refused(start: Any) -> None:
    started = start()

    assert started.setup(role="viewer").status_code == 422


# --- Security -------------------------------------------------------------------------------


def test_setup_is_hidden_from_the_internet(start: Any) -> None:
    started = start()
    outside = browser(started.app, INTERNET_CLIENT)

    assert outside.get("/api/v1/setup").status_code == 404
    body = {"code": started.code, "username": "frank", "password": PASSWORD}
    assert outside.post("/api/v1/setup", json=body, headers=CSRF).status_code == 404
    assert started.client.get("/api/v1/setup").json()["open"] is True


def test_setup_needs_the_csrf_header(start: Any) -> None:
    started = start()
    body = {"code": started.code, "username": "frank", "password": PASSWORD}

    assert started.client.post("/api/v1/setup", json=body).status_code == 403


def test_a_wrong_code_is_refused_and_not_logged(
    start: Any, caplog: pytest.LogCaptureFixture
) -> None:
    started = start()
    caplog.set_level(logging.DEBUG)

    response = started.setup(
        code="WRONG-CODE-HERE",
        password="a-password-not-logged",  # noqa: S106 - test value
    )

    assert response.status_code == 403
    assert "WRONG-CODE-HERE" not in caplog.text
    assert "a-password-not-logged" not in caplog.text
    assert "wrong setup code" in caplog.text
    # The real code appears in the log once, from the start.
    assert caplog.text.count(started.code) == 1


def test_wrong_codes_are_throttled(start: Any) -> None:
    started = start()

    statuses = [started.setup(code="AAAA-AAAA-AAAA").status_code for _ in range(6)]

    assert statuses == [403] * 5 + [429]
    # Even the right code waits until the window passes.
    assert started.setup().status_code == 429


def test_the_setup_throttle_is_apart_from_sign_in(start: Any) -> None:
    started = start()
    for _ in range(5):
        started.setup(code="AAAA-AAAA-AAAA")

    response = started.client.post(
        "/api/v1/auth/login", json={"username": "setup", "password": "x" * 12}, headers=CSRF
    )

    assert response.status_code == 401
