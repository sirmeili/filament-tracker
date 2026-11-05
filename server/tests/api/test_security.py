"""Security suite (Testing table in docs/SPEC.md): unauthenticated access refused, revoked
tokens refused, scopes enforced, oversized payloads rejected, no UIDs in normal logs."""

import json
import logging
from collections.abc import Iterator
from uuid import uuid4

import pytest
from api_helpers import admin, bearer, register, scan, scan_body
from fastapi.testclient import TestClient

from filament_tracker.config import Settings
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.main import create_app

PROTECTED = [
    ("post", "/api/v1/scans"),
    ("get", "/api/v1/devices"),
    ("post", "/api/v1/devices"),
    ("delete", "/api/v1/devices/scanner-1"),
    ("post", f"/api/v1/events/{uuid4()}/revert"),
]
ADMIN_ONLY = [
    ("get", "/api/v1/devices"),
    ("post", "/api/v1/devices"),
    ("delete", "/api/v1/devices/scanner-1"),
]


def _call(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None):  # noqa: ANN202
    if method in ("post",):
        return client.post(path, json={}, headers=headers)
    return client.request(method.upper(), path, headers=headers)


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_route_except_health_needs_a_token(
    client: TestClient, method: str, path: str
) -> None:
    response = _call(client, method, path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path"), PROTECTED)
@pytest.mark.parametrize(
    "header",
    ["Bearer wrong-token", "Bearer ftd_not-a-real-token", "Basic dXNlcjpwYXNz", "Bearer", ""],
)
def test_bad_credentials_are_refused(
    client: TestClient, method: str, path: str, header: str
) -> None:
    assert _call(client, method, path, {"Authorization": header}).status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ONLY)
def test_device_tokens_cannot_use_admin_routes(
    client: TestClient, token: str, method: str, path: str
) -> None:
    assert _call(client, method, path, bearer(token)).status_code == 401


def test_the_admin_token_cannot_submit_scans(client: TestClient) -> None:
    body = scan_body(SyntheticTag(), "lookup")

    assert client.post("/api/v1/scans", json=body, headers=admin()).status_code == 401


def test_a_revoked_token_is_refused_everywhere(client: TestClient, token: str) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    client.delete("/api/v1/devices/scanner-1", headers=admin())

    body = scan_body(SyntheticTag(), "lookup")
    assert client.post("/api/v1/scans", json=body, headers=bearer(token)).status_code == 401
    revert = client.post(f"/api/v1/events/{received['event_id']}/revert", headers=bearer(token))
    assert revert.status_code == 401


def test_health_needs_no_token(client: TestClient) -> None:
    assert client.get("/api/v1/health").status_code == 200


@pytest.fixture
def unconfigured_client(db_url: str) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=db_url, admin_token=None, _env_file=None))
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("token", ["", "None", "null"])
def test_without_an_admin_token_configured_admin_routes_are_closed(
    unconfigured_client: TestClient, token: str
) -> None:
    response = unconfigured_client.get("/api/v1/devices", headers=bearer(token))

    assert response.status_code == 401


def test_an_empty_admin_token_setting_does_not_open_admin_routes(db_url: str) -> None:
    app = create_app(Settings(database_url=db_url, admin_token="", _env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/devices", headers=bearer("")).status_code == 401


def test_oversized_bodies_are_rejected_before_parsing(client: TestClient, token: str) -> None:
    body = scan_body(SyntheticTag(), "lookup", fw_version="x" * 20_000)

    response = client.post("/api/v1/scans", json=body, headers=bearer(token))

    assert response.status_code == 413


def test_oversized_streamed_bodies_are_rejected(client: TestClient, token: str) -> None:
    payload = json.dumps(scan_body(SyntheticTag(), "lookup", fw_version="x" * 20_000)).encode()

    def chunks() -> Iterator[bytes]:
        for start in range(0, len(payload), 1024):
            yield payload[start : start + 1024]

    response = client.post(
        "/api/v1/scans",
        content=chunks(),
        headers={**bearer(token), "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_invalid_content_length_is_rejected(client: TestClient, token: str) -> None:
    response = client.post(
        "/api/v1/scans", content=b"{}", headers={**bearer(token), "Content-Length": "abc"}
    )

    assert response.status_code == 413


def test_tag_and_tray_uids_are_not_logged_above_debug(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    tag = SyntheticTag()
    caplog.set_level(logging.INFO)

    scan(client, token, tag, "received")
    scan(client, token, tag, "opened", read_ok=False, blocks=[])

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "received scan from scanner-1" in logged
    assert tag.tag_uid.hex().upper() not in logged
    assert tag.tray_uid.hex().upper() not in logged


def test_uids_do_appear_at_debug_level(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    tag = SyntheticTag()
    caplog.set_level(logging.DEBUG, logger="filament_tracker")

    scan(client, token, tag, "received")

    assert tag.tray_uid.hex().upper() in " ".join(r.getMessage() for r in caplog.records)


def test_a_second_device_is_independent(client: TestClient) -> None:
    first, second = register(client, "scanner-1"), register(client, "scanner-2")

    assert scan(client, first, SyntheticTag(), "lookup")["feedback"] == "ok"
    assert scan(client, second, SyntheticTag(), "lookup", device_id="scanner-2")["feedback"] == "ok"
