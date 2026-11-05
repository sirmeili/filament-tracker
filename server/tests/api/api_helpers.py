"""Helpers for API tests: auth headers, device registration and scan bodies."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from filament_tracker.decoder.synthetic import SyntheticTag

ADMIN_TOKEN = "test-admin-token-0123456789abcdef"  # noqa: S105 - test value


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
