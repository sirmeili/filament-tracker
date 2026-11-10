from datetime import timedelta

import pytest
from api_helpers import (
    ADMIN_TOKEN,
    BASE_URL,
    CSRF,
    INTERNET_CLIENT,
    LAN_CLIENT,
    admin,
    bearer,
    browser,
    register,
    scan_body,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.auth import TOKEN_PREFIX, hash_token
from filament_tracker.config import Settings
from filament_tracker.db.models import Device
from filament_tracker.db.types import utcnow
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app


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


# --- Unlinking ---------------------------------------------------------------------------


def test_a_device_can_revoke_its_own_token(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")

    response = client.post("/api/v1/devices/unlink", headers=bearer(token))

    assert response.status_code == 204
    assert _listed(client)["revoked"] is True
    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(token))
    assert response.status_code == 401
    assert client.post("/api/v1/devices/unlink", headers=bearer(token)).status_code == 401
    assert "scanner-1 unlinked itself" in caplog.text
    assert token not in caplog.text


def test_unlinking_leaves_other_devices_alone(client: TestClient, token: str) -> None:
    other = register(client, "scanner-2")

    client.post("/api/v1/devices/unlink", headers=bearer(token))

    assert _listed(client, "scanner-2")["revoked"] is False
    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(other))
    assert response.status_code == 204


def test_rotating_re_enables_an_unlinked_device(client: TestClient, token: str) -> None:
    client.post("/api/v1/devices/unlink", headers=bearer(token))

    new = client.post("/api/v1/devices/scanner-1/rotate", headers=admin()).json()["token"]

    response = client.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=bearer(new))
    assert response.status_code == 204


def test_unlinking_needs_a_device_token(client: TestClient, app: FastAPI, token: str) -> None:
    assert client.post("/api/v1/devices/unlink").status_code == 401
    assert client.post("/api/v1/devices/unlink", headers=admin()).status_code == 403
    with signed_in(app, Role.ADMIN) as user:
        response = user.post("/api/v1/devices/unlink", headers=CSRF)
        assert response.status_code == 401
    assert _listed(client)["revoked"] is False


def test_only_the_local_network_refusal_is_marked(client: TestClient, app: FastAPI) -> None:
    assert "x-rollcall-refused" not in client.post("/api/v1/devices/unlink").headers
    with signed_in(app, Role.EDITOR) as user:
        response = user.post("/api/v1/devices/unlink", headers=CSRF)
    assert "x-rollcall-refused" not in response.headers
    with browser(app, INTERNET_CLIENT) as outside:
        response = outside.post("/api/v1/devices/heartbeat", json=HEARTBEAT, headers=admin())
    assert response.status_code == 403
    assert response.headers["x-rollcall-refused"] == "local-network-only"


def test_unlinking_is_refused_from_outside_the_lan(
    client: TestClient, app: FastAPI, token: str
) -> None:
    with browser(app, INTERNET_CLIENT) as outside:
        assert outside.post("/api/v1/devices/unlink", headers=bearer(token)).status_code == 403

    assert _listed(client)["revoked"] is False


# --- Provisioning -------------------------------------------------------------------------

SALT = "00112233445566778899AABBCCDDEEFF"  # made up; the real constant is never in the repo


def salted_app(db_url: str, salt: str | None = SALT) -> FastAPI:
    settings = Settings(
        database_url=db_url, admin_token=ADMIN_TOKEN, bambu_kdf_salt=salt, _env_file=None
    )
    return create_app(settings)


def test_a_device_gets_the_kdf_salt(db_url: str) -> None:
    with TestClient(salted_app(db_url), base_url=BASE_URL, client=LAN_CLIENT) as client:
        response = client.get("/api/v1/devices/provisioning", headers=bearer(register(client)))

    assert response.status_code == 200
    assert response.json() == {"kdf_salt": SALT, "access": None, "records": True}
    assert response.headers["cache-control"] == "no-store"


def test_the_salt_is_only_for_devices(db_url: str, caplog: pytest.LogCaptureFixture) -> None:
    app = salted_app(db_url)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        token = register(client)
        url = "/api/v1/devices/provisioning"
        assert client.get(url).status_code == 401
        assert client.get(url, headers=admin()).status_code == 403
        assert signed_in(app, Role.ADMIN).get(url).status_code == 401
        outside = browser(app, INTERNET_CLIENT)
        refused = outside.get(url, headers=bearer(token))
        assert refused.status_code == 403
        # Marked, so the phone app keeps its scans queued while away from home.
        assert refused.headers["x-rollcall-refused"] == "local-network-only"
        client.delete("/api/v1/devices/scanner-1", headers=admin())
        assert client.get(url, headers=bearer(token)).status_code == 401
        for path in ("/api/v1/devices", "/api/v1/health"):
            assert SALT not in client.get(path, headers=admin()).text

    assert SALT not in caplog.text


def test_without_a_salt_provisioning_is_unavailable(db_url: str) -> None:
    with TestClient(salted_app(db_url, None), base_url=BASE_URL, client=LAN_CLIENT) as client:
        response = client.get("/api/v1/devices/provisioning", headers=bearer(register(client)))

    assert response.status_code == 503
    assert "salt is not set" in response.json()["detail"]
