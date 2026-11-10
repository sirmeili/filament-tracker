"""The read endpoints behind the web app's pages: inventory, products, spools, activity
and review."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, Spool
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

WHITE = {"color_rgba": "FFFFFFFF"}
PETG = {
    "material_id": "GFG00",
    "filament_type": "PETG",
    "detailed_filament_type": "PETG Basic",
    "color_rgba": "FF0000FF",
}


@pytest.fixture
def viewer(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.VIEWER)


def _stock(client: TestClient, token: str) -> dict[str, SyntheticTag]:
    """Black PLA: 2 sealed, 1 open, 1 empty. White PLA: 1 sealed. Red PETG: 1 open."""
    tags = {f"black{n}": SyntheticTag() for n in range(4)}
    tags["white"] = SyntheticTag(**WHITE)
    tags["red"] = SyntheticTag(**PETG)
    for tag in tags.values():
        scan(client, token, tag, "received")
    scan(client, token, tags["black2"], "opened")
    scan(client, token, tags["black3"], "opened")
    scan(client, token, tags["black3"], "empty")
    scan(client, token, tags["red"], "opened")
    return tags


def _threshold(db: Session, name: str, value: int) -> None:
    product = db.query(Product).filter(Product.display_name == name).one()
    product.low_stock_threshold = value
    db.commit()


# --- Inventory and products ----------------------------------------------------------------


def test_inventory_counts_spools_per_product(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    _stock(client, token)

    cards = viewer.get("/api/v1/inventory").json()

    assert [c["product"]["display_name"] for c in cards] == [
        "PETG Basic #FF0000",
        "PLA Basic #000000",
        "PLA Basic #FFFFFF",
    ]
    black = cards[1]
    assert black["counts"] == {"sealed": 2, "open": 1, "empty": 1, "unknown": 0}
    assert black["product"]["color_rgba"] == "000000FF"
    assert black["product"]["material_id"] == "GFA00"
    assert black["low_stock"] is False


def test_low_stock_is_sealed_at_or_below_the_threshold(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    _stock(client, token)
    _threshold(db, "PLA Basic #000000", 2)  # 2 sealed: low
    _threshold(db, "PLA Basic #FFFFFF", 0)  # off
    _threshold(db, "PETG Basic #FF0000", 1)  # 0 sealed: low

    cards = viewer.get("/api/v1/inventory", params={"sort": "low_stock"}).json()

    assert [(c["product"]["display_name"], c["low_stock"]) for c in cards] == [
        ("PETG Basic #FF0000", True),
        ("PLA Basic #000000", True),
        ("PLA Basic #FFFFFF", False),
    ]


def _remaining(db: Session, spool_id: int, pct: int | None) -> None:
    db.get(Spool, spool_id).remaining_pct = pct
    db.commit()


def test_inventory_lists_open_spools_with_their_remaining_pct(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    tags = _stock(client, token)
    scan(client, token, tags["black0"], "opened")  # spool 1, opened after spool 3
    _remaining(db, 3, 15)  # black, at the default cutoff: nearly out
    _remaining(db, 1, None)  # not seen by the AMS
    _remaining(db, 6, 16)  # red PETG, above the cutoff

    cards = {c["product"]["display_name"]: c for c in viewer.get("/api/v1/inventory").json()}

    black = cards["PLA Basic #000000"]
    assert black["product"]["nearly_out_pct"] == 15
    assert black["open_spools"] == [
        {"id": 3, "remaining_pct": 15, "nearly_out": True},
        {"id": 1, "remaining_pct": None, "nearly_out": False},
    ]
    assert cards["PETG Basic #FF0000"]["open_spools"] == [
        {"id": 6, "remaining_pct": 16, "nearly_out": False}
    ]
    assert cards["PLA Basic #FFFFFF"]["open_spools"] == []


def test_the_nearly_out_cutoff_is_per_product(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    _stock(client, token)
    _remaining(db, 6, 30)
    db.query(Product).filter(Product.filament_type == "PETG").one().nearly_out_pct = 30
    db.commit()

    [card] = viewer.get("/api/v1/inventory", params={"type": "PETG"}).json()
    detail = viewer.get(f"/api/v1/products/{card['product']['id']}").json()

    assert card["open_spools"][0]["nearly_out"] is True
    assert detail["open_spools"] == card["open_spools"]


def test_inventory_filters_by_type(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    cards = viewer.get("/api/v1/inventory", params={"type": "petg"}).json()

    assert [c["product"]["filament_type"] for c in cards] == ["PETG"]


def test_inventory_lists_products_with_no_spools(
    client: TestClient, viewer: TestClient, db: Session
) -> None:
    db.add(
        Product(filament_type="TPU", color_rgba="00FF00FF", display_name="TPU", provisional=True)
    )
    db.commit()

    [card] = viewer.get("/api/v1/inventory").json()

    assert card["counts"] == {"sealed": 0, "open": 0, "empty": 0, "unknown": 0}
    assert card["product"]["provisional"] is True
    assert card["product"]["from_ams"] is False


def test_spools_with_every_event_undone_count_as_unknown(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    client.post(f"/api/v1/events/{received['event_id']}/revert", headers=admin())

    [card] = viewer.get("/api/v1/inventory").json()

    assert card["counts"]["unknown"] == 1


def test_home_assistant_reads_inventory_with_the_admin_token(client: TestClient) -> None:
    assert client.get("/api/v1/inventory", headers=admin()).status_code == 200


def test_inventory_rejects_an_unknown_sort(client: TestClient, viewer: TestClient) -> None:
    assert viewer.get("/api/v1/inventory", params={"sort": "price"}).status_code == 422


def test_products_list_and_detail(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    products = viewer.get("/api/v1/products").json()
    black = next(p for p in products if p["color_rgba"] == "000000FF")
    detail = viewer.get(f"/api/v1/products/{black['id']}").json()

    assert len(products) == 3
    assert black["variant_id"] == "A00-K00"
    assert black["low_stock_threshold"] == 0
    assert detail["product"] == black
    assert detail["counts"]["sealed"] == 2
    assert viewer.get("/api/v1/products/999").status_code == 404


# --- Spools ----------------------------------------------------------------------------------


def _ids(response) -> list[int]:  # noqa: ANN001
    return [s["id"] for s in response.json()["items"]]


def test_spools_are_listed_newest_first(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    page = viewer.get("/api/v1/spools").json()

    assert page["total"] == 6
    assert [s["id"] for s in page["items"]] == [6, 5, 4, 3, 2, 1]
    first = page["items"][-1]
    assert first["state"] == "sealed"
    assert first["product"]["display_name"] == "PLA Basic #000000"
    assert first["placeholder"] is False
    assert first["received_at"] is not None


def test_spools_filter_by_state_and_product(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    _stock(client, token)

    assert _ids(viewer.get("/api/v1/spools", params={"state": "open"})) == [6, 3]
    assert _ids(viewer.get("/api/v1/spools", params={"state": ["open", "empty"]})) == [6, 4, 3]
    assert _ids(viewer.get("/api/v1/spools", params={"product_id": 2})) == [5]
    assert viewer.get("/api/v1/spools", params={"state": "lost"}).status_code == 422


def test_spools_filter_by_unknown_state(client: TestClient, token: str, viewer: TestClient) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    scan(client, token, SyntheticTag(), "received")
    client.post(f"/api/v1/events/{received['event_id']}/revert", headers=admin())

    response = viewer.get("/api/v1/spools", params={"state": ["unknown", "empty"]})

    assert _ids(response) == [1]
    assert response.json()["items"][0]["state"] == "unknown"


def test_spools_filter_by_location_and_search(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    _stock(client, token)
    db.get(Spool, 1).location = "Shelf A"
    db.get(Spool, 2).location = "shelf a"
    db.get(Spool, 5).notes = "for the 100% infill test"
    db.commit()

    assert _ids(viewer.get("/api/v1/spools", params={"location": "SHELF A "})) == [2, 1]
    assert _ids(viewer.get("/api/v1/spools", params={"q": "petg"})) == [6]
    assert _ids(viewer.get("/api/v1/spools", params={"q": "shelf"})) == [2, 1]
    assert _ids(viewer.get("/api/v1/spools", params={"q": "100%"})) == [5]
    assert _ids(viewer.get("/api/v1/spools", params={"q": "_"})) == []
    assert len(_ids(viewer.get("/api/v1/spools", params={"q": "  "}))) == 6


def test_spools_filter_by_type(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    assert _ids(viewer.get("/api/v1/spools", params={"type": " petg"})) == [6]
    assert _ids(viewer.get("/api/v1/spools", params={"type": "PLA", "state": "open"})) == [3]
    assert _ids(viewer.get("/api/v1/spools", params={"type": "ABS"})) == []
    assert viewer.get("/api/v1/spools", params={"type": "x" * 33}).status_code == 422


def test_spools_are_paged(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    page = viewer.get("/api/v1/spools", params={"limit": 2, "offset": 2}).json()

    assert [s["id"] for s in page["items"]] == [4, 3]
    assert (page["total"], page["limit"], page["offset"]) == (6, 2, 2)
    assert viewer.get("/api/v1/spools", params={"limit": 0}).status_code == 422
    assert viewer.get("/api/v1/spools", params={"limit": 201}).status_code == 422
    assert viewer.get("/api/v1/spools", params={"offset": -1}).status_code == 422


def test_spool_detail_has_tags_and_a_timeline(
    app: FastAPI, client: TestClient, token: str, viewer: TestClient
) -> None:
    tag = SyntheticTag()
    second_tag = SyntheticTag(tray_uid=tag.tray_uid, filler=tag.filler)
    received = scan(
        client, token, tag, "received", scanned_at=datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    )
    scan(client, token, second_tag, "opened", scanned_at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
    editor = signed_in(app, Role.EDITOR)
    undo = editor.post(f"/api/v1/events/{received['event_id']}/revert", headers=CSRF).json()

    detail = viewer.get("/api/v1/spools/1").json()

    assert detail["state"] == "open"
    assert detail["notes"] is None
    assert {t["uid"] for t in detail["tags"]} == {
        tag.tag_uid.hex().upper(),
        second_tag.tag_uid.hex().upper(),
    }
    assert detail["tags"][0]["decoded"]["material_id"] == "GFA00"
    assert detail["tags"][0]["decoder_version"] == 1
    assert "raw_blocks" not in str(detail)
    revert, opened, first = detail["events"]
    assert revert["type"] == "revert"
    assert revert["username"] == "editor-user"
    assert revert["source"] == "ui"
    assert revert["reverts"] == received["event_id"]
    assert revert["can_undo"] is False
    assert opened["type"] == "opened"
    assert opened["device_id"] == "scanner-1"
    assert opened["device_name"] == "Shelf"
    assert opened["username"] is None
    assert opened["can_undo"] is True
    assert first["id"] == received["event_id"]
    assert first["reverted_by"] == undo["revert_event_id"]
    assert first["can_undo"] is False
    assert first["product_name"] == "PLA Basic #000000"


def test_spool_detail_has_grams_left(
    client: TestClient, token: str, viewer: TestClient, db: Session
) -> None:
    scan(client, token, SyntheticTag(spool_weight_g=750), "opened")

    before = viewer.get("/api/v1/spools/1").json()
    _remaining(db, 1, 33)
    after = viewer.get("/api/v1/spools/1").json()

    assert (before["spool_weight_g"], before["grams_left"]) == (750, None)
    assert (after["spool_weight_g"], after["grams_left"], after["remaining_pct"]) == (750, 248, 33)


def test_a_spool_without_a_readable_weight_has_no_grams_left(
    client: TestClient, viewer: TestClient, db: Session
) -> None:
    product = Product(filament_type="TPU", color_rgba="00FF00FF", display_name="TPU")
    db.add(Spool(product=product, remaining_pct=50))
    db.commit()

    detail = viewer.get("/api/v1/spools/1").json()

    assert (detail["spool_weight_g"], detail["grams_left"]) == (None, None)


def test_unknown_spools_are_404(client: TestClient, viewer: TestClient) -> None:
    assert viewer.get("/api/v1/spools/42").status_code == 404


def test_placeholders_are_marked(client: TestClient, viewer: TestClient, db: Session) -> None:
    product = Product(filament_type="TPU", color_rgba="00FF00FF", display_name="TPU 95A")
    db.add(Spool(product=product))
    db.commit()

    [row] = viewer.get("/api/v1/spools").json()["items"]

    assert row["placeholder"] is True
    assert row["state"] == "unknown"


# --- Activity and review ---------------------------------------------------------------------


def test_activity_lists_every_event_newest_first(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    _stock(client, token)

    page = viewer.get("/api/v1/events", params={"limit": 3}).json()

    assert page["total"] == 10
    assert [e["type"] for e in page["items"]] == ["opened", "empty", "opened"]
    assert page["items"][0]["product_name"] == "PETG Basic #FF0000"
    assert page["items"][0]["color_rgba"] == "FF0000FF"


def test_activity_filters_by_source(
    app: FastAPI, client: TestClient, token: str, viewer: TestClient
) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    editor = signed_in(app, Role.EDITOR)
    editor.post(f"/api/v1/events/{received['event_id']}/revert", headers=CSRF)

    by_scanner = viewer.get("/api/v1/events", params={"source": "scanner"}).json()
    by_ui = viewer.get("/api/v1/events", params={"source": "ui"}).json()

    assert [e["type"] for e in by_scanner["items"]] == ["received"]
    assert [e["type"] for e in by_ui["items"]] == ["revert"]
    assert viewer.get("/api/v1/events", params={"source": "ams"}).json()["total"] == 0
    assert viewer.get("/api/v1/events", params={"source": "fax"}).status_code == 422


def test_activity_filters_by_spool(client: TestClient, token: str, viewer: TestClient) -> None:
    _stock(client, token)

    page = viewer.get("/api/v1/events", params={"spool_id": 4}).json()

    assert [e["type"] for e in page["items"]] == ["empty", "opened", "received"]
    assert {e["spool_id"] for e in page["items"]} == {4}


def test_review_lists_flagged_events_until_undone(
    client: TestClient, token: str, viewer: TestClient
) -> None:
    tag = SyntheticTag()
    flagged = scan(client, token, tag, "empty")  # empty on an unknown spool
    scan(client, token, SyntheticTag(), "received")

    review = viewer.get("/api/v1/review").json()
    assert [e["id"] for e in review["flagged_events"]] == [flagged["event_id"]]
    assert review["flagged_events"][0]["flagged"] is True
    assert review["likely_empty"] == []

    client.post(f"/api/v1/events/{flagged['event_id']}/revert", headers=admin())
    assert viewer.get("/api/v1/review").json()["flagged_events"] == []


def test_review_lists_unidentified_tags(client: TestClient, token: str, viewer: TestClient) -> None:
    unreadable = SyntheticTag()
    scan(client, token, unreadable, "received", read_ok=False, blocks=[])
    scan(client, token, SyntheticTag(), "received")

    [tag] = viewer.get("/api/v1/review").json()["unidentified_tags"]

    assert tag["uid"] == unreadable.tag_uid.hex().upper()
    assert tag["readable"] is False
    assert tag["decoded"] is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/inventory",
        "/api/v1/products",
        "/api/v1/products/1",
        "/api/v1/spools",
        "/api/v1/spools/1",
        "/api/v1/events",
        "/api/v1/review",
    ],
)
def test_reads_need_a_viewer_and_refuse_scanners(client: TestClient, token: str, path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_event_ids_are_uuids(client: TestClient, token: str, viewer: TestClient) -> None:
    scan(client, token, SyntheticTag(), "received")

    [event] = viewer.get("/api/v1/events").json()["items"]

    assert UUID(event["id"]).version == 4
