"""422 answers say where and what is wrong, never the value sent, which may be a secret."""

from api_helpers import ADMIN_TOKEN, BASE_URL, CSRF, LAN_CLIENT, admin, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from filament_tracker.api.account_schemas import MAX_PASSWORD
from filament_tracker.config import PrinterConfig, Settings
from filament_tracker.domain.enums import Role
from filament_tracker.main import create_app

SECRET = "s3cret-value-"  # noqa: S105 - test value


def test_a_too_long_password_is_not_repeated(client: TestClient) -> None:
    password = SECRET * (MAX_PASSWORD // len(SECRET) + 1)
    response = client.post(
        "/api/v1/auth/login", json={"username": "a", "password": password}, headers=CSRF
    )
    assert response.status_code == 422
    assert SECRET not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert set(error) == {"type", "loc", "msg"}


def test_a_wrongly_typed_secret_is_not_repeated(app: FastAPI, client: TestClient) -> None:
    user = signed_in(app, Role.ADMIN)
    response = user.put(
        "/api/v1/settings/home-assistant", json={"values": {"ha_token": [SECRET]}}, headers=CSRF
    )
    assert response.status_code == 422
    assert SECRET not in response.text


def test_printers_in_env_are_added_at_start(db_url: str) -> None:
    # Port 1 on this machine refuses at once, so the real link fails fast in the background.
    seeded = PrinterConfig(
        name="Env P1S", host="127.0.0.1", port=1, serial="ENV1", access_code=SecretStr(SECRET)
    )
    settings = Settings(
        database_url=db_url, admin_token=ADMIN_TOKEN, printers=[seeded], _env_file=None
    )
    with TestClient(create_app(settings), base_url=BASE_URL, client=LAN_CLIENT) as client:
        [printer] = client.get("/api/v1/printers", headers=admin()).json()
    assert (printer["name"], printer["serial"], printer["access_code_set"]) == (
        "Env P1S",
        "ENV1",
        True,
    )
    assert printer["configured"] is True
    assert SECRET not in str(printer)
