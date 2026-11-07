import logging
from typing import Any

import pytest
from api_helpers import ADMIN_TOKEN, CSRF, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from filament_tracker.api import settings as settings_api
from filament_tracker.config import Settings
from filament_tracker.domain.enums import Role
from filament_tracker.ha.check import CheckResult
from filament_tracker.main import create_app

URL = "/api/v1/settings/home-assistant"
TOKEN = "ha-token-value-1234"  # noqa: S105 - test value


def by_key(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in body["settings"]}


@pytest.fixture
def env_app(db_url: str) -> FastAPI:
    """The server with Home Assistant set in .env."""
    return create_app(
        Settings(
            database_url=db_url,
            admin_token=ADMIN_TOKEN,
            ha_url="http://ha.local:8123",
            ha_token=SecretStr(TOKEN),
            _env_file=None,
        )
    )


def test_reads_the_group_without_secrets(env_app: FastAPI) -> None:
    with TestClient(env_app, base_url="https://testserver", client=("192.168.1.20", 1)) as client:
        response = client.get(URL, headers=admin())

    assert response.status_code == 200
    assert TOKEN not in response.text
    settings = by_key(response.json())
    assert response.json()["group"] == "home-assistant"
    assert settings["ha_url"] == {
        "key": "ha_url",
        "value": "http://ha.local:8123",
        "secret": False,
        "set": True,
        "source": "env",
        "has_env": True,
        "unreadable": False,
    }
    assert settings["ha_token"]["value"] is None
    assert settings["ha_token"]["set"] is True
    assert settings["mqtt_url"]["source"] == "default"


def test_saving_applies_at_once_and_never_returns_the_secret(
    app: FastAPI, client: TestClient
) -> None:
    user = signed_in(app, Role.ADMIN)
    assert app.state.home_assistant.sender.rest is None

    response = user.put(
        URL,
        json={"values": {"ha_url": "http://ha.local:8123", "ha_token": TOKEN}},
        headers=CSRF,
    )

    assert response.status_code == 200
    assert TOKEN not in response.text
    settings = by_key(response.json())
    assert settings["ha_url"]["source"] == "app"
    assert settings["ha_token"]["set"] is True
    rest = app.state.home_assistant.sender.rest
    assert rest is not None and rest.url == "http://ha.local:8123"
    assert client.get("/api/v1/health").json()["home_assistant"]["events"] == "ready"


def test_nothing_changed_does_not_restart(app: FastAPI, client: TestClient) -> None:
    sender = app.state.home_assistant.sender
    response = client.put(URL, json={"values": {"ha_token": ""}}, headers=admin())
    assert response.status_code == 200
    assert app.state.home_assistant.sender is sender


def test_clear_and_use_the_env_value(env_app: FastAPI) -> None:
    with TestClient(env_app, base_url="https://testserver", client=("192.168.1.20", 1)) as client:
        cleared = client.put(URL, json={"clear": ["ha_token"]}, headers=admin())
        token = by_key(cleared.json())["ha_token"]
        assert (token["set"], token["source"]) == (False, "app")
        assert env_app.state.home_assistant.sender.rest is None

        assert client.delete(f"{URL}/ha_token", headers=admin()).status_code == 204
        back = by_key(client.get(URL, headers=admin()).json())["ha_token"]
        assert back["source"] == "env" and back["set"] is True
        assert env_app.state.home_assistant.sender.rest is not None

        # Nothing saved any more: still fine.
        assert client.delete(f"{URL}/ha_token", headers=admin()).status_code == 204


def test_refused_values_name_the_setting_not_the_value(client: TestClient) -> None:
    response = client.put(
        URL, json={"values": {"mqtt_url": "mqtt://u:hunter2@broker"}}, headers=admin()
    )
    assert response.status_code == 422
    assert "hunter2" not in response.text
    assert "mqtt_url" in response.json()["detail"]["problems"]


@pytest.mark.parametrize(
    "body",
    [
        {"values": {"admin_token": "x"}},
        {"clear": ["admin_token"]},
        {"values": {"ha_url": "http://ha"}, "extra": 1},
        {"values": {"ha_token": "x" * 5000}},
    ],
)
def test_only_this_groups_settings_are_accepted(client: TestClient, body: dict[str, Any]) -> None:
    assert client.put(URL, json=body, headers=admin()).status_code == 422


def test_unknown_groups_and_keys(client: TestClient) -> None:
    assert client.get("/api/v1/settings/nope", headers=admin()).status_code == 404
    assert client.put("/api/v1/settings/nope", json={}, headers=admin()).status_code == 404
    assert client.delete(f"{URL}/admin_token", headers=admin()).status_code == 404


def test_the_test_uses_entered_values_and_reports_categories(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def broker(config: Any) -> CheckResult:
        seen["broker"] = config
        return CheckResult.REFUSED

    def rest(config: Any) -> CheckResult:
        seen["rest"] = config
        return CheckResult.OK

    monkeypatch.setattr(settings_api, "check_broker", broker)
    monkeypatch.setattr(settings_api, "check_rest", rest)

    response = client.post(
        f"{URL}/test",
        json={
            "values": {
                "mqtt_url": "mqtt://broker:1883",
                "ha_url": "http://ha:8123",
                "ha_token": TOKEN,
            }
        },
        headers=admin(),
    )

    assert response.status_code == 200
    assert response.json() == {"mqtt": "refused", "events": "ok"}
    assert seen["broker"].host == "broker"
    assert seen["rest"].url == "http://ha:8123"
    # Nothing was saved.
    assert by_key(client.get(URL, headers=admin()).json())["ha_url"]["set"] is False


def test_the_test_with_nothing_set_tries_nothing(client: TestClient) -> None:
    response = client.post(f"{URL}/test", json={}, headers=admin())
    assert response.json() == {"mqtt": "off", "events": "off"}


def test_the_test_can_leave_out_a_saved_secret(env_app: FastAPI) -> None:
    with TestClient(env_app, base_url="https://testserver", client=("192.168.1.20", 1)) as client:
        response = client.post(f"{URL}/test", json={"clear": ["ha_token"]}, headers=admin())
        assert response.json()["events"] == "off"
        bad = client.post(f"{URL}/test", json={"clear": ["admin_token"]}, headers=admin())
        assert bad.status_code == 422
        bad = client.post(f"{URL}/test", json={"values": {"ha_url": "ftp://x"}}, headers=admin())
        assert bad.status_code == 422


def test_changes_are_logged_without_values(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    user = signed_in(app, Role.ADMIN)
    user.put(URL, json={"values": {"ha_token": TOKEN}}, headers=CSRF)
    assert "ha_token" in caplog.text
    assert TOKEN not in caplog.text


def test_settings_are_lan_only_for_the_admin_token(app: FastAPI) -> None:
    with TestClient(app, base_url="https://testserver", client=("203.0.113.7", 1)) as outside:
        assert outside.get(URL, headers=admin()).status_code in (401, 403)
