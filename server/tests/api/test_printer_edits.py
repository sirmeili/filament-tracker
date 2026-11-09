"""Adding, editing, testing and removing printers on the Devices page. The access code is
write-only: it never comes back in a response, an error or a log line."""

import logging
from typing import Any

import pytest
from api_helpers import CSRF, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.api import printers as printers_api
from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer, PrinterSlot
from filament_tracker.domain.enums import Role
from filament_tracker.printer.probe import PrinterCheck
from filament_tracker.services.printers import access_code

CODE = "code1234"  # test value
URL = "/api/v1/printers"
NEW = {"name": "P1S", "host": "192.168.1.40", "serial": "01P00A1", "access_code": CODE}


class RecordingManager:
    def __init__(self) -> None:
        self.reloaded: list[int] = []

    def reload(self, printer_id: int) -> None:
        self.reloaded.append(printer_id)

    def status(self, printer_id: int) -> None:
        return None


@pytest.fixture
def admin(app: FastAPI, client: TestClient) -> TestClient:
    app.state.printers = RecordingManager()
    return signed_in(app, Role.ADMIN)


def add(admin: TestClient, **changes: Any) -> dict[str, Any]:
    response = admin.post(URL, json=NEW | changes, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def test_adding_seals_the_code_and_connects(
    app: FastAPI, admin: TestClient, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    body = add(admin, name="  Garage P1S ", port=18883)

    assert (body["name"], body["port"], body["serial"]) == ("Garage P1S", 18883, "01P00A1")
    assert (body["access_code_set"], body["access_code_unreadable"]) == (True, False)
    assert body["pinned_sha256"] is None
    assert app.state.printers.reloaded == [body["id"]]
    printer = db.get_one(Printer, body["id"])
    assert printer.access_code is not None and CODE not in printer.access_code
    assert access_code(app.state.secret_box, printer).get_secret_value() == CODE  # type: ignore[union-attr]
    assert CODE not in admin.get(URL).text
    assert CODE not in caplog.text


def test_a_serial_is_used_once(admin: TestClient) -> None:
    first = add(admin)
    assert admin.post(URL, json=NEW, headers=CSRF).status_code == 409
    second = add(admin, serial="OTHER")
    response = admin.patch(f"{URL}/{second['id']}", json={"serial": "01P00A1"}, headers=CSRF)
    assert response.status_code == 409
    # A printer may keep its own serial.
    same = admin.patch(f"{URL}/{first['id']}", json={"serial": "01P00A1"}, headers=CSRF)
    assert same.status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"host": "http://printer"},
        {"host": "user@printer"},
        {"port": 0},
        {"port": 70000},
        {"serial": "has space"},
        {"access_code": ""},
        {"access_code": "x" * 65},
        {"extra": 1},
    ],
)
def test_bad_values_are_refused_without_repeating_them(
    admin: TestClient, changes: dict[str, Any]
) -> None:
    response = admin.post(URL, json=NEW | changes, headers=CSRF)

    assert response.status_code == 422
    assert CODE not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"type", "loc", "msg"}
    if "access_code" in changes and changes["access_code"]:
        assert changes["access_code"] not in response.text


def test_editing_keeps_the_pin_and_the_code_unless_given(
    app: FastAPI, admin: TestClient, db: Session
) -> None:
    body = add(admin)
    printer = db.get_one(Printer, body["id"])
    printer.cert_sha256 = "ab" * 32
    db.commit()
    sealed = printer.access_code

    response = admin.patch(
        f"{URL}/{body['id']}", json={"host": "proxy.lan", "port": 1883}, headers=CSRF
    )

    assert response.status_code == 200
    edited = response.json()
    assert (edited["host"], edited["port"], edited["pinned_sha256"]) == (
        "proxy.lan",
        1883,
        "ab" * 32,
    )
    db.expire_all()
    assert db.get_one(Printer, body["id"]).access_code == sealed

    admin.patch(f"{URL}/{body['id']}", json={"access_code": "newcode9"}, headers=CSRF)
    db.expire_all()
    printer = db.get_one(Printer, body["id"])
    assert access_code(app.state.secret_box, printer).get_secret_value() == "newcode9"  # type: ignore[union-attr]
    assert app.state.printers.reloaded == [body["id"]] * 3
    assert admin.patch(f"{URL}/999", json={}, headers=CSRF).status_code == 404


def test_removing_forgets_the_printer_and_its_slots(
    app: FastAPI, admin: TestClient, db: Session
) -> None:
    body = add(admin)
    db.add(PrinterSlot(printer_id=body["id"], ams_index=0, tray_index=0))
    db.commit()

    assert admin.delete(f"{URL}/{body['id']}", headers=CSRF).status_code == 204

    assert db.scalars(select(Printer)).all() == []
    assert db.scalars(select(PrinterSlot)).all() == []
    assert app.state.printers.reloaded[-1] == body["id"]
    assert admin.delete(f"{URL}/{body['id']}", headers=CSRF).status_code == 404


def test_test_uses_the_saved_or_entered_values(
    app: FastAPI, admin: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[PrinterConfig, str | None]] = []

    def check(config: PrinterConfig, pin: str | None) -> PrinterCheck:
        seen.append((config, pin))
        return PrinterCheck.REFUSED

    monkeypatch.setattr(printers_api, "check_printer", check)
    body = add(admin)
    url = f"{URL}/{body['id']}/test"

    response = admin.post(url, json={}, headers=CSRF)
    assert response.json() == {"result": "refused"}
    assert seen[-1][0].access_code.get_secret_value() == CODE
    assert seen[-1][1] is None

    db.get_one(Printer, body["id"]).cert_sha256 = "ab" * 32
    db.commit()
    admin.post(url, json={"host": "10.0.0.9", "port": 1883, "access_code": "typed99"}, headers=CSRF)
    config, pin = seen[-1]
    assert (config.host, config.port, config.access_code.get_secret_value()) == (
        "10.0.0.9",
        1883,
        "typed99",
    )
    assert pin == "ab" * 32
    # Nothing was saved by the test.
    db.expire_all()
    assert db.get_one(Printer, body["id"]).host == "192.168.1.40"
    assert admin.post(f"{URL}/999/test", json={}, headers=CSRF).status_code == 404


def test_test_without_an_access_code(admin: TestClient, db: Session) -> None:
    printer = Printer(name="Old", host="h", port=8883, serial="OLD")
    db.add(printer)
    db.commit()

    response = admin.post(f"{URL}/{printer.id}/test", json={}, headers=CSRF)

    assert response.status_code == 422
    assert response.json()["detail"]["problems"] == {"access_code": "enter the access code"}
    listed = {p["serial"]: p for p in admin.get(URL).json()}
    assert listed["OLD"]["access_code_set"] is False


def test_an_unreadable_code_is_reported(app: FastAPI, admin: TestClient, db: Session) -> None:
    body = add(admin)
    printer = db.get_one(Printer, body["id"])
    printer.access_code = "v1:not-sealed-with-this-key"
    db.commit()

    [listed] = admin.get(URL).json()

    assert (listed["access_code_set"], listed["access_code_unreadable"]) == (True, True)


def test_without_a_running_manager(app: FastAPI, client: TestClient) -> None:
    admin = signed_in(app, Role.ADMIN)
    app.state.printers = None
    response = admin.post(URL, json=NEW, headers=CSRF)
    assert response.status_code == 201
