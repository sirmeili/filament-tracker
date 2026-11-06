from datetime import timedelta

from api_helpers import admin, bearer, register, scan_body
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.auth import TOKEN_PREFIX, hash_token
from filament_tracker.db.models import Device
from filament_tracker.db.types import utcnow
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


# --- Heartbeat and online status -------------------------------------------------------------

HEARTBEAT = {"fw_version": "0.3.1", "queue_length": 2}


def _listed(client: TestClient, device_id: str = "scanner-1") -> dict:
    return next(
        d for d in client.get("/api/v1/devices", headers=admin()).json() if d["id"] == device_id
    )


def test_a_new_device_is_offline_with_no_queue(client: TestClient, token: str) -> None:
    device = _listed(client)

    assert (device["online"], device["queue_length"], device["fw_version"]) == (False, None, None)


def test_a_heartbeat_records_firmware_queue_and_last_seen(client: TestClient, token: str) -> None:
    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(token))

    assert response.status_code == 204
    device = _listed(client)
    assert (device["fw_version"], device["queue_length"], device["online"]) == ("0.3.1", 2, True)
    assert device["last_seen_at"] is not None


def test_a_device_is_offline_after_fifteen_minutes(
    client: TestClient, token: str, db: Session
) -> None:
    client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(token))
    device = db.get(Device, "scanner-1")

    device.last_seen_at = utcnow() - timedelta(minutes=14, seconds=50)
    db.commit()
    assert _listed(client)["online"] is True

    device.last_seen_at = utcnow() - timedelta(minutes=15, seconds=10)
    db.commit()
    assert _listed(client)["online"] is False


def test_a_revoked_device_is_offline_and_cannot_send_heartbeats(
    client: TestClient, token: str
) -> None:
    client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(token))
    client.delete("/api/v1/devices/scanner-1", headers=admin())

    assert _listed(client)["online"] is False
    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(token))
    assert response.status_code == 401


def test_heartbeats_need_a_device_token(client: TestClient) -> None:
    assert client.post("/api/v1/devices/heartbeat", json=HEARTBEAT).status_code == 401
    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=admin())
    assert response.status_code in (401, 403)


def test_heartbeats_are_validated(client: TestClient, token: str) -> None:
    for body in (
        {},
        {**HEARTBEAT, "queue_length": -1},
        {**HEARTBEAT, "queue_length": 100_001},
        {**HEARTBEAT, "fw_version": ""},
        {**HEARTBEAT, "fw_version": "x" * 33},
        {**HEARTBEAT, "device_id": "scanner-2"},
    ):
        response = client.post("/api/v1/devices/heartbeat", json=body, headers=bearer(token))
        assert response.status_code == 422, body
