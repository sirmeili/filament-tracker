"""Machine tokens: made on the Settings page, shown once, stored hashed, limited to their
role, refused once revoked and accepted only from the LAN (Security in docs/SPEC.md)."""

import logging
from datetime import timedelta

import pytest
from api_helpers import (
    CSRF,
    INTERNET_CLIENT,
    admin,
    bearer,
    browser,
    scan_body,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_access import ROUTES, _call

from filament_tracker import auth
from filament_tracker.auth import hash_token
from filament_tracker.db.models import MachineToken
from filament_tracker.db.types import utcnow
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role


def make_token(client: TestClient, role: Role = Role.VIEWER, name: str = "Home Assistant") -> dict:
    response = client.post(
        "/api/v1/tokens", json={"name": name, "role": role.value}, headers=admin()
    )
    assert response.status_code == 201
    return response.json()


# --- Making, listing and revoking ----------------------------------------------------------


def test_a_new_token_is_shown_once_and_stored_hashed(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    user = signed_in(app, Role.ADMIN, username="frank")

    response = user.post(
        "/api/v1/tokens", json={"name": "  Home Assistant ", "role": "editor"}, headers=CSRF
    )

    assert response.status_code == 201
    made = response.json()
    assert made["token"].startswith("ftm_")
    assert len(made["token"]) > 40
    assert made["name"] == "Home Assistant"
    assert made["role"] == "editor"
    assert made["created_by"] == "frank"
    assert made["last_used_at"] is None
    assert made["revoked"] is False
    stored = db.scalar(select(MachineToken))
    assert stored.token_hash == hash_token(made["token"])
    assert made["token"] not in repr(vars(stored))
    listed = user.get("/api/v1/tokens").json()
    assert [t["id"] for t in listed] == [made["id"]]
    assert "token" not in listed[0]


def test_a_token_made_with_the_admin_token_has_no_creator(client: TestClient) -> None:
    assert make_token(client)["created_by"] is None


def test_each_token_is_different(client: TestClient) -> None:
    assert make_token(client)["token"] != make_token(client)["token"]


def test_the_list_shows_tokens_in_use_first(client: TestClient) -> None:
    old = make_token(client, name="old")
    revoked = make_token(client, name="revoked")
    new = make_token(client, name="new")
    client.delete(f"/api/v1/tokens/{revoked['id']}", headers=admin())

    listed = client.get("/api/v1/tokens", headers=admin()).json()

    assert [t["name"] for t in listed] == ["new", "old", "revoked"]
    assert [t["revoked"] for t in listed] == [False, False, True]
    assert new["id"] > old["id"]


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "role": "viewer"},
        {"name": "   ", "role": "viewer"},
        {"name": "x" * 101, "role": "viewer"},
        {"name": "HA", "role": "owner"},
        {"name": "HA"},
        {"name": "HA", "role": "viewer", "token": "ftm_mine"},
    ],
)
def test_bad_requests_are_refused_without_echoing_them(client: TestClient, body: dict) -> None:
    response = client.post("/api/v1/tokens", json=body, headers=admin())

    assert response.status_code == 422
    assert "ftm_mine" not in response.text
    assert "owner" not in response.text


def test_revoking_is_idempotent_and_unknown_tokens_are_404(client: TestClient) -> None:
    made = make_token(client)

    assert client.delete(f"/api/v1/tokens/{made['id']}", headers=admin()).status_code == 204
    assert client.delete(f"/api/v1/tokens/{made['id']}", headers=admin()).status_code == 204
    assert client.delete("/api/v1/tokens/999", headers=admin()).status_code == 404


def test_the_token_never_reaches_the_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    made = make_token(client, Role.ADMIN)
    client.get("/api/v1/tokens", headers=bearer(made["token"]))
    client.delete(f"/api/v1/tokens/{made['id']}", headers=bearer(made["token"]))

    assert "machine token" in caplog.text
    assert made["token"] not in caplog.text
    assert hash_token(made["token"]) not in caplog.text


# --- Using a token -------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "needed"), ROUTES)
@pytest.mark.parametrize("role", list(Role))
def test_a_token_is_limited_to_its_role(
    client: TestClient, method: str, path: str, needed: Role, role: Role
) -> None:
    made = make_token(client, role)

    status = _call(client, method, path, bearer(made["token"])).status_code

    if role.allows(needed):
        assert status not in (401, 403)
    else:
        assert status == 403


def test_a_revoked_token_is_refused_at_once(client: TestClient) -> None:
    made = make_token(client)
    assert client.get("/api/v1/inventory", headers=bearer(made["token"])).status_code == 200

    client.delete(f"/api/v1/tokens/{made['id']}", headers=admin())

    assert client.get("/api/v1/inventory", headers=bearer(made["token"])).status_code == 401


def test_an_admin_token_can_revoke_itself(client: TestClient) -> None:
    made = make_token(client, Role.ADMIN)
    own = bearer(made["token"])

    assert client.delete(f"/api/v1/tokens/{made['id']}", headers=own).status_code == 204
    assert client.get("/api/v1/tokens", headers=own).status_code == 401


def test_an_unknown_machine_token_is_refused(client: TestClient) -> None:
    response = client.get("/api/v1/inventory", headers=bearer("ftm_" + "A" * 43))

    assert response.status_code == 401


def test_a_token_is_refused_from_the_internet(app: FastAPI, client: TestClient) -> None:
    made = make_token(client, Role.ADMIN)
    outside = browser(app, INTERNET_CLIENT)

    assert outside.get("/api/v1/inventory", headers=bearer(made["token"])).status_code == 403


def test_a_token_cannot_act_as_a_scanner(client: TestClient) -> None:
    made = make_token(client, Role.ADMIN)
    headers = bearer(made["token"])

    body = scan_body(SyntheticTag(), "lookup")
    assert client.post("/api/v1/scans", json=body, headers=headers).status_code == 403
    heartbeat = {"fw_version": "1.0", "queue_length": 0}
    assert (
        client.post("/api/v1/devices/heartbeat", json=heartbeat, headers=headers).status_code == 403
    )


def test_a_token_is_not_a_signed_in_user(client: TestClient) -> None:
    made = make_token(client, Role.ADMIN)

    assert client.get("/api/v1/auth/me", headers=bearer(made["token"])).status_code == 403


def test_the_admin_token_keeps_working(client: TestClient) -> None:
    make_token(client)

    assert client.get("/api/v1/tokens", headers=admin()).status_code == 200


# --- Last use ------------------------------------------------------------------------------


def test_last_use_is_recorded_at_most_once_a_minute(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = make_token(client)
    headers = bearer(made["token"])
    start = utcnow()
    monkeypatch.setattr(auth, "utcnow", lambda: start)

    client.get("/api/v1/inventory", headers=headers)
    first = client.get("/api/v1/tokens", headers=admin()).json()[0]["last_used_at"]
    monkeypatch.setattr(auth, "utcnow", lambda: start + timedelta(seconds=30))
    client.get("/api/v1/inventory", headers=headers)
    same = client.get("/api/v1/tokens", headers=admin()).json()[0]["last_used_at"]
    monkeypatch.setattr(auth, "utcnow", lambda: start + timedelta(minutes=2))
    client.get("/api/v1/inventory", headers=headers)
    later = client.get("/api/v1/tokens", headers=admin()).json()[0]["last_used_at"]

    assert first is not None
    assert same == first
    assert later != first
