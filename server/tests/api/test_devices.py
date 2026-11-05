from api_helpers import admin, bearer, register, scan_body
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.auth import TOKEN_PREFIX, hash_token
from filament_tracker.db.models import Device
from filament_tracker.decoder.synthetic import SyntheticTag


def test_registration_returns_a_token_once_and_stores_only_its_hash(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/api/v1/devices", json={"id": "scanner-1", "name": "Shelf"}, headers=admin()
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "scanner-1"
    assert body["revoked"] is False
    assert body["token"].startswith(TOKEN_PREFIX)
    device = db.get(Device, "scanner-1")
    assert device is not None
    assert device.token_hash == hash_token(body["token"])
    assert body["token"] not in device.token_hash


def test_every_device_gets_a_different_token(client: TestClient) -> None:
    assert register(client, "scanner-1") != register(client, "scanner-2")


def test_list_shows_devices_without_tokens(client: TestClient) -> None:
    register(client, "scanner-2")
    register(client, "scanner-1")

    response = client.get("/api/v1/devices", headers=admin())

    assert response.status_code == 200
    devices = response.json()
    assert [d["id"] for d in devices] == ["scanner-1", "scanner-2"]
    assert all("token" not in d and "token_hash" not in d for d in devices)


def test_duplicate_ids_are_refused(client: TestClient) -> None:
    register(client, "scanner-1")

    response = client.post(
        "/api/v1/devices", json={"id": "scanner-1", "name": "Again"}, headers=admin()
    )

    assert response.status_code == 409


def test_invalid_registrations_are_rejected(client: TestClient) -> None:
    for body in ({"id": "Has Spaces", "name": "x"}, {"id": "ok", "name": ""}, {"id": "ok"}):
        assert client.post("/api/v1/devices", json=body, headers=admin()).status_code == 422


def test_a_revoked_device_can_no_longer_scan(client: TestClient) -> None:
    token = register(client)
    body = scan_body(SyntheticTag(), "lookup")
    assert client.post("/api/v1/scans", json=body, headers=bearer(token)).status_code == 200

    assert client.delete("/api/v1/devices/scanner-1", headers=admin()).status_code == 204

    assert client.post("/api/v1/scans", json=body, headers=bearer(token)).status_code == 401
    listed = client.get("/api/v1/devices", headers=admin()).json()
    assert listed[0]["revoked"] is True


def test_revoking_twice_is_harmless(client: TestClient) -> None:
    register(client)
    client.delete("/api/v1/devices/scanner-1", headers=admin())

    assert client.delete("/api/v1/devices/scanner-1", headers=admin()).status_code == 204


def test_revoking_an_unknown_device_is_not_found(client: TestClient) -> None:
    assert client.delete("/api/v1/devices/nobody", headers=admin()).status_code == 404


def test_rotating_a_token_replaces_it(client: TestClient, token: str) -> None:
    response = client.post("/api/v1/devices/scanner-1/rotate", headers=admin())

    assert response.status_code == 200
    new_token = response.json()["token"]
    assert new_token != token and new_token.startswith("ftd_")
    body = scan_body(SyntheticTag(), "lookup")
    assert client.post("/api/v1/scans", json=body, headers=bearer(token)).status_code == 401
    assert client.post("/api/v1/scans", json=body, headers=bearer(new_token)).status_code == 200


def test_rotating_re_enables_a_revoked_device(client: TestClient, token: str) -> None:
    client.delete("/api/v1/devices/scanner-1", headers=admin())

    rotated = client.post("/api/v1/devices/scanner-1/rotate", headers=admin()).json()

    assert rotated["revoked"] is False
    body = scan_body(SyntheticTag(), "lookup")
    assert (
        client.post("/api/v1/scans", json=body, headers=bearer(rotated["token"])).status_code == 200
    )


def test_rotating_an_unknown_device(client: TestClient) -> None:
    assert client.post("/api/v1/devices/nope/rotate", headers=admin()).status_code == 404
