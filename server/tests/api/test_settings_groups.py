"""The General and Scanners settings groups: saved values take effect at once."""

import logging
from typing import Any

import pytest
from api_helpers import CSRF, admin, bearer, login, make_user, register, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.domain.enums import Role

SALT = "00112233445566778899AABBCCDDEEFF"  # made up; the real constant is never in the repo


def by_key(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in body["settings"]}


def test_general_defaults(client: TestClient) -> None:
    response = client.get("/api/v1/settings/general", headers=admin())
    assert response.status_code == 200
    settings = by_key(response.json())
    assert list(settings) == ["tz", "session_days"]
    assert settings["tz"]["value"] == "UTC"
    assert settings["tz"]["source"] == "default"
    assert settings["session_days"]["value"] == "30"


def test_the_time_zone_reaches_the_web_app(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN)
    assert user.get("/api/v1/auth/me").json()["time_zone"] == "UTC"
    sender = app.state.home_assistant.sender

    response = user.put(
        "/api/v1/settings/general", json={"values": {"tz": "America/New_York"}}, headers=CSRF
    )

    assert response.status_code == 200
    assert user.get("/api/v1/auth/me").json()["time_zone"] == "America/New_York"
    # Only the Home Assistant group reconnects anything.
    assert app.state.home_assistant.sender is sender


def test_new_sign_ins_use_the_saved_length(app: FastAPI, client: TestClient) -> None:
    put = client.put(
        "/api/v1/settings/general", json={"values": {"session_days": "7"}}, headers=admin()
    )
    assert put.status_code == 200
    make_user(app, "bob", Role.VIEWER)

    response = login(client, "bob")

    assert response.status_code == 200
    assert f"max-age={7 * 24 * 3600}" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    "values", [{"tz": "Nowhere/Land"}, {"session_days": "0"}, {"session_days": "x"}]
)
def test_bad_general_values_are_refused(client: TestClient, values: dict[str, str]) -> None:
    response = client.put("/api/v1/settings/general", json={"values": values}, headers=admin())
    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == set(values)


def test_a_salt_saved_in_the_app_is_served_to_devices_and_never_shown(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    token = register(client)
    url = "/api/v1/devices/provisioning"
    assert client.get(url, headers=bearer(token)).status_code == 503

    user = signed_in(app, Role.ADMIN)
    response = user.put(
        "/api/v1/settings/scanners",
        json={"values": {"bambu_kdf_salt": SALT.lower()}},
        headers=CSRF,
    )

    assert response.status_code == 200
    assert SALT not in response.text.upper()
    salt = by_key(response.json())["bambu_kdf_salt"]
    assert (salt["secret"], salt["set"], salt["value"]) == (True, True, None)
    assert client.get(url, headers=bearer(token)).json() == {"kdf_salt": SALT}
    assert SALT not in user.get("/api/v1/settings/scanners").text.upper()
    assert SALT not in caplog.text.upper()


def test_a_bad_salt_is_refused_without_repeating_it(client: TestClient) -> None:
    response = client.put(
        "/api/v1/settings/scanners",
        json={"values": {"bambu_kdf_salt": "not-hex-secret"}},
        headers=admin(),
    )
    assert response.status_code == 422
    assert "not-hex-secret" not in response.text


@pytest.mark.parametrize("group", ["general", "scanners"])
def test_only_admins_see_these_groups(app: FastAPI, client: TestClient, group: str) -> None:
    editor = signed_in(app, Role.EDITOR)
    assert editor.get(f"/api/v1/settings/{group}").status_code == 403
    assert client.get(f"/api/v1/settings/{group}").status_code == 401
