"""Helpers for API tests: auth headers, device registration, scan bodies and users."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import create_user

ADMIN_TOKEN = "test-admin-token-0123456789abcdef"  # noqa: S105 - test value
BASE_URL = "https://testserver"
LAN_CLIENT = ("192.168.1.20", 50000)
INTERNET_CLIENT = ("203.0.113.7", 50000)


def admin() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, device_id: str = "scanner-1") -> str:
    response = client.post(
        "/api/v1/devices", json={"id": device_id, "name": "Shelf"}, headers=admin()
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def scan_body(
    tag: SyntheticTag,
    action: str,
    *,
    device_id: str = "scanner-1",
    scanned_at: datetime | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": str(uuid4()),
        "device_id": device_id,
        "action": action,
        "tag_uid": tag.tag_uid.hex().upper(),
        "blocks": tag.data_blocks(),
        "read_ok": True,
        "fw_version": "0.1.0",
    }
    if scanned_at is not None:
        body["scanned_at"] = scanned_at.isoformat()
    body.update(overrides)
    return body


def post_scan(client: TestClient, token: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v1/scans", json=body, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


def scan(
    client: TestClient, token: str, tag: SyntheticTag, action: str, **kw: Any
) -> dict[str, Any]:
    return post_scan(client, token, scan_body(tag, action, **kw))


# --- Web app users ------------------------------------------------------------------------

PASSWORD = "correct horse battery"  # noqa: S105 - test value
CSRF = {"X-Requested-With": "filament-tracker"}


def make_user(app: FastAPI, username: str, role: Role, password: str = PASSWORD) -> int:
    with app.state.session_factory() as session:
        user = create_user(session, username, password, role)
        session.commit()
        return user.id


def login(client: TestClient, username: str, password: str = PASSWORD) -> Response:
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}, headers=CSRF
    )


def browser(app: FastAPI, client: tuple[str, int] = LAN_CLIENT) -> TestClient:
    """Another browser on the same running app (the `client` fixture started it)."""
    return TestClient(app, base_url=BASE_URL, client=client)


def signed_in(
    app: FastAPI, role: Role, client: tuple[str, int] = LAN_CLIENT, username: str | None = None
) -> TestClient:
    """A browser signed in as a new user with `role`."""
    name = username or f"{role.value}-user"
    make_user(app, name, role)
    session = browser(app, client)
    assert login(session, name).status_code == 200
    return session
