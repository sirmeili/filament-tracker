"""The General and Scanners settings groups: saved values take effect at once."""

import logging
from typing import Any

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
    login,
    make_user,
    register,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

SALT = "00112233445566778899AABBCCDDEEFF"  # made up; the real constant is never in the repo
# A made-up Cloudflare Access service token, in Cloudflare's format.
ACCESS_ID = "0123456789abcdef0123456789abcdef.access"
ACCESS_SECRET = "f" * 24 + "0123456789abcdef" * 2 + "e" * 8


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
    assert client.get(url, headers=bearer(token)).json() == {"kdf_salt": SALT, "access": None}
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


def _save_scanners(client: TestClient, values: dict[str, str]) -> Any:
    return client.put("/api/v1/settings/scanners", json={"values": values}, headers=admin())


def test_an_access_token_saved_in_the_app_goes_to_devices_and_never_shows_its_secret(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    token = register(client)
    url = "/api/v1/devices/provisioning"

    response = _save_scanners(
        client,
        {
            "bambu_kdf_salt": SALT,
            "cf_access_client_id": ACCESS_ID,
            "cf_access_client_secret": ACCESS_SECRET,
        },
    )

    assert response.status_code == 200
    settings = by_key(response.json())
    assert settings["cf_access_client_id"]["value"] == ACCESS_ID
    secret = settings["cf_access_client_secret"]
    assert (secret["secret"], secret["set"], secret["value"]) == (True, True, None)
    assert ACCESS_SECRET not in response.text
    assert ACCESS_SECRET not in client.get("/api/v1/settings/scanners", headers=admin()).text
    provisioning = client.get(url, headers=bearer(token))
    assert provisioning.json()["access"] == {
        "client_id": ACCESS_ID,
        "client_secret": ACCESS_SECRET,
    }
    assert provisioning.headers["cache-control"] == "no-store"
    assert ACCESS_SECRET not in caplog.text


def test_half_an_access_token_is_not_handed_out(client: TestClient) -> None:
    token = register(client)
    url = "/api/v1/devices/provisioning"
    assert _save_scanners(client, {"bambu_kdf_salt": SALT}).status_code == 200
    assert client.get(url, headers=bearer(token)).json()["access"] is None

    assert _save_scanners(client, {"cf_access_client_id": ACCESS_ID}).status_code == 200
    assert client.get(url, headers=bearer(token)).json()["access"] is None

    _save_scanners(client, {"cf_access_client_id": "", "cf_access_client_secret": ACCESS_SECRET})
    assert client.get(url, headers=bearer(token)).json()["access"] is None


def test_the_access_token_is_only_for_lan_devices(app: FastAPI, client: TestClient) -> None:
    token = register(client)
    _save_scanners(
        client,
        {
            "bambu_kdf_salt": SALT,
            "cf_access_client_id": ACCESS_ID,
            "cf_access_client_secret": ACCESS_SECRET,
        },
    )
    url = "/api/v1/devices/provisioning"
    user = signed_in(app, Role.ADMIN)

    assert client.get(url).status_code == 401
    assert client.get(url, headers=admin()).status_code == 403
    assert user.get(url).status_code == 401
    with browser(app, INTERNET_CLIENT) as outside:
        response = outside.get(url, headers=bearer(token))
    assert response.status_code == 403
    assert ACCESS_SECRET not in response.text


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("cf_access_client_id", "0123456789abcdef0123456789abcdef"),
        ("cf_access_client_id", "short.access"),
        ("cf_access_client_id", "0123456789abcdef0123456789abcdef.access extra"),
        ("cf_access_client_secret", "too-short-secret"),
        ("cf_access_client_secret", "x" * 40 + "!"),
    ],
)
def test_bad_access_token_parts_are_refused_without_repeating_them(
    client: TestClient, key: str, value: str
) -> None:
    response = _save_scanners(client, {key: value})

    assert response.status_code == 422
    assert set(response.json()["detail"]["problems"]) == {key}
    assert value not in response.text


def test_an_access_token_can_come_from_env(db_url: str) -> None:
    settings = Settings(
        database_url=db_url,
        admin_token=ADMIN_TOKEN,
        bambu_kdf_salt=SecretStr(SALT),
        cf_access_client_id=ACCESS_ID,
        cf_access_client_secret=SecretStr(ACCESS_SECRET),
        _env_file=None,
    )
    with TestClient(create_app(settings), base_url=BASE_URL, client=LAN_CLIENT) as client:
        token = register(client)
        body = client.get("/api/v1/devices/provisioning", headers=bearer(token)).json()
        listed = by_key(client.get("/api/v1/settings/scanners", headers=admin()).json())

    assert body["access"] == {"client_id": ACCESS_ID, "client_secret": ACCESS_SECRET}
    assert listed["cf_access_client_secret"]["source"] == "env"
    assert listed["cf_access_client_secret"]["value"] is None


@pytest.mark.parametrize("group", ["general", "scanners"])
def test_only_admins_see_these_groups(app: FastAPI, client: TestClient, group: str) -> None:
    editor = signed_in(app, Role.EDITOR)
    assert editor.get(f"/api/v1/settings/{group}").status_code == 403
    assert client.get(f"/api/v1/settings/{group}").status_code == 401
