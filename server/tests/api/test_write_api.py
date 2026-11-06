"""Changes from the web app: spool edits, manual actions and entry, products."""

from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event, Product, Spool
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import EventSource, Role


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR)


@pytest.fixture
def spool_id(client: TestClient, token: str) -> int:
    return scan(client, token, SyntheticTag(), "received")["spool"]["id"]


def _patch(client: TestClient, path: str, body: dict) -> dict:
    response = client.patch(path, json=body, headers=CSRF)
    assert response.status_code == 200, response.text
    return response.json()


# --- Spool edits -----------------------------------------------------------------------------


def test_editing_location_and_notes(editor: TestClient, spool_id: int) -> None:
    detail = _patch(editor, f"/api/v1/spools/{spool_id}", {"location": " Shelf A ", "notes": "x"})

    assert (detail["location"], detail["notes"]) == ("Shelf A", "x")
    assert detail["events"][0]["type"] == "received"


def test_only_fields_sent_change_and_blank_clears(editor: TestClient, spool_id: int) -> None:
    _patch(editor, f"/api/v1/spools/{spool_id}", {"location": "Shelf A", "notes": "keep"})

    detail = _patch(editor, f"/api/v1/spools/{spool_id}", {"location": ""})

    assert detail["location"] is None
    assert detail["notes"] == "keep"
    assert _patch(editor, f"/api/v1/spools/{spool_id}", {"notes": None})["notes"] is None


def test_spool_edits_are_validated(editor: TestClient, spool_id: int) -> None:
    path = f"/api/v1/spools/{spool_id}"
    for body in ({"location": "x" * 101}, {"notes": "x" * 2001}, {"state": "empty"}):
        assert editor.patch(path, json=body, headers=CSRF).status_code == 422, body
    assert editor.patch("/api/v1/spools/99", json={}, headers=CSRF).status_code == 404


def test_moving_several_spools(client: TestClient, token: str, editor: TestClient) -> None:
    ids = [scan(client, token, SyntheticTag(), "received")["spool"]["id"] for _ in range(3)]

    rows = _patch(editor, "/api/v1/spools", {"spool_ids": ids[:2], "location": "Dry box"})

    assert [(r["id"], r["location"]) for r in rows] == [(ids[0], "Dry box"), (ids[1], "Dry box")]
    assert editor.get(f"/api/v1/spools/{ids[2]}").json()["location"] is None


def test_moving_is_all_or_nothing(editor: TestClient, spool_id: int) -> None:
    response = editor.patch(
        "/api/v1/spools", json={"spool_ids": [spool_id, 98, 99], "location": "X"}, headers=CSRF
    )

    assert response.status_code == 404
    assert "98, 99" in response.json()["detail"]
    assert editor.get(f"/api/v1/spools/{spool_id}").json()["location"] is None


def test_moving_needs_at_least_one_spool(editor: TestClient) -> None:
    body = {"spool_ids": [], "location": "X"}

    assert editor.patch("/api/v1/spools", json=body, headers=CSRF).status_code == 422


# --- Manual actions --------------------------------------------------------------------------


def _act(client: TestClient, spool_id: int, action: str, **extra: str) -> dict:
    response = client.post(
        f"/api/v1/spools/{spool_id}/events", json={"action": action, **extra}, headers=CSRF
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_manual_action_records_who_did_it(editor: TestClient, spool_id: int, db: Session) -> None:
    result = _act(editor, spool_id, "opened")

    assert result["outcome"] == "applied"
    assert result["spool"]["state"] == "open"
    assert result["event"]["username"] == "editor-user"
    assert result["event"]["source"] == "ui"
    event = db.get(Event, db.query(Event.id).filter(Event.type == "opened").scalar())
    assert (event.source, event.user_id, event.device_id) == (EventSource.UI, 1, None)


def test_manual_actions_follow_the_state_rules(editor: TestClient, spool_id: int) -> None:
    assert _act(editor, spool_id, "received")["outcome"] == "already_in_state"
    assert _act(editor, spool_id, "empty")["outcome"] == "flagged"  # sealed straight to empty
    reopened = _act(editor, spool_id, "opened")  # a correction from the web app
    assert reopened["outcome"] == "applied"
    assert reopened["spool"]["emptied_at"] is None


def test_a_manual_action_can_be_backdated(editor: TestClient, spool_id: int) -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    result = _act(editor, spool_id, "opened", occurred_at=yesterday)

    assert result["event"]["occurred_at"].startswith(yesterday[:16])


def test_manual_actions_cannot_be_in_the_future(editor: TestClient, spool_id: int) -> None:
    later = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    path = f"/api/v1/spools/{spool_id}/events"

    response = editor.post(path, json={"action": "opened", "occurred_at": later}, headers=CSRF)

    assert response.status_code == 422


def test_manual_actions_are_validated(editor: TestClient, spool_id: int) -> None:
    path = f"/api/v1/spools/{spool_id}/events"
    for body in ({"action": "revert"}, {"action": "opened", "occurred_at": "2026-11-01T09:00"}):
        assert editor.post(path, json=body, headers=CSRF).status_code == 422, body
    missing = editor.post("/api/v1/spools/99/events", json={"action": "opened"}, headers=CSRF)
    assert missing.status_code == 404


def test_the_admin_token_records_actions_without_a_user(client: TestClient, spool_id: int) -> None:
    response = client.post(
        f"/api/v1/spools/{spool_id}/events", json={"action": "opened"}, headers=admin()
    )

    assert response.json()["event"]["username"] is None


# --- Manual entry ----------------------------------------------------------------------------

TPU = {"display_name": "TPU 95A HF Black", "filament_type": "TPU", "color_rgba": "000000ff"}


def _new_product(client: TestClient, **body: object) -> dict:
    response = client.post("/api/v1/products", json={**TPU, **body}, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def test_creating_a_provisional_product(editor: TestClient) -> None:
    product = _new_product(editor, low_stock_threshold=2)

    assert product["provisional"] is True
    assert product["color_rgba"] == "000000FF"
    assert (product["material_id"], product["variant_id"]) == (None, None)
    assert product["low_stock_threshold"] == 2
    assert product["nearly_out_pct"] == 15


@pytest.mark.parametrize(
    "bad",
    [
        {"color_rgba": "black"},
        {"display_name": " "},
        {"filament_type": ""},
        {"low_stock_threshold": -1},
        {"nearly_out_pct": 101},
        {"material_id": "GFA00"},
    ],
)
def test_new_products_are_validated(editor: TestClient, bad: dict) -> None:
    assert editor.post("/api/v1/products", json={**TPU, **bad}, headers=CSRF).status_code == 422


def test_adding_a_spool_by_hand(editor: TestClient) -> None:
    product = _new_product(editor)
    body = {"product_id": product["id"], "location": "Bin 3", "notes": "foil bag"}

    response = editor.post("/api/v1/spools", json=body, headers=CSRF)

    assert response.status_code == 201
    spool = response.json()
    assert spool["placeholder"] is True
    assert spool["state"] == "sealed"
    assert (spool["location"], spool["notes"]) == ("Bin 3", "foil bag")
    assert [e["type"] for e in spool["events"]] == ["received"]
    assert spool["events"][0]["username"] == "editor-user"


def test_a_hand_added_spool_can_be_backdated(editor: TestClient) -> None:
    product = _new_product(editor)
    when = "2026-10-20T12:00:00+00:00"

    spool = editor.post(
        "/api/v1/spools", json={"product_id": product["id"], "received_at": when}, headers=CSRF
    ).json()

    assert spool["received_at"].startswith("2026-10-20T12:00")


def test_adding_a_spool_needs_a_real_product(editor: TestClient) -> None:
    assert editor.post("/api/v1/spools", json={"product_id": 9}, headers=CSRF).status_code == 404


def test_the_first_scan_links_to_a_hand_added_spool(
    client: TestClient, token: str, editor: TestClient, db: Session
) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")  # the product now exists
    product_id = db.query(Product.id).scalar()
    placeholder = editor.post("/api/v1/spools", json={"product_id": product_id}, headers=CSRF)

    result = scan(client, token, SyntheticTag(), "opened")

    assert result["spool"]["id"] == placeholder.json()["id"]
    linked = db.get(Spool, placeholder.json()["id"])
    db.refresh(linked)
    assert linked.tray_uid is not None


# --- Products --------------------------------------------------------------------------------


def test_renaming_a_product_and_setting_its_threshold(
    client: TestClient, token: str, editor: TestClient
) -> None:
    scan(client, token, SyntheticTag(), "received")

    product = _patch(editor, "/api/v1/products/1", {"display_name": " Black PLA "})
    product = _patch(editor, "/api/v1/products/1", {"low_stock_threshold": 3})

    assert (product["display_name"], product["low_stock_threshold"]) == ("Black PLA", 3)
    assert editor.get("/api/v1/inventory").json()[0]["low_stock"] is True


def test_setting_a_products_nearly_out_pct(
    client: TestClient, token: str, editor: TestClient, db: Session
) -> None:
    scan(client, token, SyntheticTag(), "opened")
    db.get(Spool, 1).remaining_pct = 20
    db.commit()

    product = _patch(editor, "/api/v1/products/1", {"nearly_out_pct": 25})

    assert product["nearly_out_pct"] == 25
    assert editor.get("/api/v1/inventory").json()[0]["open_spools"][0]["nearly_out"] is True


def test_viewers_cannot_change_products(app: FastAPI, client: TestClient, token: str) -> None:
    scan(client, token, SyntheticTag(), "received")
    viewer = signed_in(app, Role.VIEWER)

    response = viewer.patch("/api/v1/products/1", json={"nearly_out_pct": 50}, headers=CSRF)

    assert response.status_code == 403


def test_product_edits_are_validated(client: TestClient, token: str, editor: TestClient) -> None:
    scan(client, token, SyntheticTag(), "received")
    for body in (
        {"display_name": None},
        {"low_stock_threshold": None},
        {"display_name": ""},
        {"low_stock_threshold": 1001},
        {"nearly_out_pct": None},
        {"nearly_out_pct": -1},
        {"nearly_out_pct": 101},
        {"nearly_out_pct": "lots"},
        {"color_rgba": "FFFFFFFF"},
    ):
        assert editor.patch("/api/v1/products/1", json=body, headers=CSRF).status_code == 422
    assert editor.patch("/api/v1/products/9", json={}, headers=CSRF).status_code == 404
