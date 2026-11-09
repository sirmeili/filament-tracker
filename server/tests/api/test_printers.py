"""The printer link as the API shows it: printers and their slots on the Devices page, the
AMS slot on spools, and dismissing "Likely empty" suggestions."""

from datetime import timedelta

import pytest
from api_helpers import CSRF, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.db.models import Printer
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.printer.link import LinkState, LinkStatus
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

BLACK = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
GRAY = "0F1E2D3C4B5A69788796A5B4C3D2E1F0"


@pytest.fixture
def admin(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.ADMIN)


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR)


def add_printer(
    db: Session, *, seen_minutes_ago: float | None = 1, pin: str | None = "ab" * 32
) -> Printer:
    printer = Printer(
        name="P1S",
        serial="01P00A1",
        host="192.168.1.40",
        port=8883,
        cert_sha256=pin,
        last_report_at=utcnow() - timedelta(minutes=seen_minutes_ago)
        if seen_minutes_ago is not None
        else None,
    )
    db.add(printer)
    ingest(
        db,
        printer,
        [
            TrayReport(0, 0, BLACK, "GFA00", "PLA", "PLA Basic", "000000FF", 85),
            TrayReport(0, 1),
            TrayReport(0, 2, None, None, "PETG", None, "FF6A13FF", None),
            TrayReport(0, 3, GRAY, "GFG02", "PETG", "PETG HF", "515151FF", 0),
        ],
        utcnow(),
    )
    db.commit()
    return printer


class FakeManager:
    def __init__(self, statuses: dict[int, LinkStatus]) -> None:
        self._statuses = statuses

    def status(self, printer_id: int) -> LinkStatus | None:
        return self._statuses.get(printer_id)


def test_printers_show_status_pin_and_slots(app: FastAPI, admin: TestClient, db: Session) -> None:
    printer = add_printer(db)
    app.state.printers = FakeManager(
        {printer.id: LinkStatus(LinkState.PIN_MISMATCH, utcnow(), "cd" * 32)}
    )

    [body] = admin.get("/api/v1/printers").json()

    assert body["name"] == "P1S"
    assert (body["host"], body["port"], body["configured"]) == ("192.168.1.40", 8883, True)
    assert (body["connection"], body["online"]) == ("pin_mismatch", True)
    assert (body["pinned_sha256"], body["presented_sha256"]) == ("ab" * 32, "cd" * 32)
    slots = body["slots"]
    assert [s["tray_index"] for s in slots] == [0, 1, 2, 3]
    assert slots[0]["spool"]["product"]["display_name"] == "PLA Basic #000000"
    assert slots[0]["spool"]["state"] == "open"
    assert slots[0]["remaining_pct"] == 85
    assert slots[1]["spool"] is None and slots[1]["filament_type"] is None
    assert slots[2]["spool"] is None and slots[2]["filament_type"] == "PETG"
    assert (body["serial"], body["access_code_set"], body["access_code_unreadable"]) == (
        "01P00A1",
        False,
        False,
    )


@pytest.mark.parametrize(("minutes", "online"), [(4.9, True), (5.1, False), (None, False)])
def test_a_printer_is_online_when_it_reported_in_the_last_five_minutes(
    admin: TestClient, db: Session, minutes: float | None, online: bool
) -> None:
    add_printer(db, seen_minutes_ago=minutes)

    [body] = admin.get("/api/v1/printers").json()

    assert body["online"] is online
    assert (body["configured"], body["connection"]) == (False, "not_configured")


def test_unpinning_forgets_the_certificate(admin: TestClient, db: Session) -> None:
    printer = add_printer(db)

    response = admin.post(f"/api/v1/printers/{printer.id}/unpin", headers=CSRF)

    assert response.status_code == 200
    assert response.json()["pinned_sha256"] is None
    db.expire_all()
    assert db.get(Printer, printer.id).cert_sha256 is None
    assert admin.post("/api/v1/printers/999/unpin", headers=CSRF).status_code == 404


def test_spools_show_their_ams_slot(admin: TestClient, db: Session) -> None:
    add_printer(db)

    rows = admin.get("/api/v1/spools").json()["items"]
    slots = {r["product"]["display_name"]: r["ams_slot"] for r in rows}
    assert slots["PLA Basic #000000"]["tray_index"] == 0
    assert slots["PETG HF #515151"] == {
        "printer_id": slots["PETG HF #515151"]["printer_id"],
        "printer_name": "P1S",
        "ams_index": 0,
        "tray_index": 3,
    }
    spool_id = next(r["id"] for r in rows if r["ams_slot"]["tray_index"] == 0)
    assert admin.get(f"/api/v1/spools/{spool_id}").json()["ams_slot"]["printer_name"] == "P1S"


def test_an_unloaded_spool_has_no_slot(admin: TestClient, db: Session) -> None:
    printer = add_printer(db)
    ingest(db, printer, [TrayReport(0, 0)], utcnow())
    db.commit()

    rows = admin.get("/api/v1/spools").json()["items"]

    assert [r["ams_slot"] for r in rows] == [None, None]


def test_dismissing_a_likely_empty_spool_and_bringing_it_back(
    editor: TestClient, db: Session
) -> None:
    add_printer(db)
    [likely] = editor.get("/api/v1/review").json()["likely_empty"]
    path = f"/api/v1/review/spools/{likely['id']}"

    assert editor.post(f"{path}/dismiss", headers=CSRF).status_code == 204
    assert editor.get("/api/v1/review").json()["likely_empty"] == []
    assert editor.post(f"{path}/dismiss", headers=CSRF).status_code == 204  # twice is fine

    assert editor.post(f"{path}/restore", headers=CSRF).status_code == 204
    assert len(editor.get("/api/v1/review").json()["likely_empty"]) == 1
    assert editor.post(f"{path}/restore", headers=CSRF).status_code == 409


def test_only_likely_empty_spools_can_be_dismissed(editor: TestClient, db: Session) -> None:
    add_printer(db)
    rows = editor.get("/api/v1/spools").json()["items"]
    not_empty = next(r["id"] for r in rows if r["remaining_pct"] == 85)

    response = editor.post(f"/api/v1/review/spools/{not_empty}/dismiss", headers=CSRF)

    assert response.status_code == 409
    assert editor.post("/api/v1/review/spools/999/dismiss", headers=CSRF).status_code == 404
    assert editor.post("/api/v1/review/spools/999/restore", headers=CSRF).status_code == 404
