from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import bearer, post_scan, register, scan, scan_body
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Device, Event, Product, Spool, Tag
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import EventSource, EventType
from filament_tracker.services.events import append_event

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
T1 = T0 + timedelta(days=1)


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# --- Lookup ----------------------------------------------------------------------------


def test_lookup_of_an_unknown_tag_offers_new_and_writes_nothing(
    client: TestClient, token: str, db: Session
) -> None:
    result = scan(client, token, SyntheticTag(), "lookup")

    assert result["feedback"] == "ok"
    assert result["state"] == "unknown"
    assert result["actions"] == ["received", "opened", "empty"]
    assert result["suggested"] == "received"
    assert result["spool"] is None
    assert result["event_id"] is None
    assert result["product"]["id"] is None
    assert result["product"]["display_name"] == "PLA Basic #000000"
    assert result["product"]["color_rgba"] == "000000FF"
    assert (_count(db, Product), _count(db, Spool), _count(db, Tag), _count(db, Event)) == (
        0,
        0,
        0,
        0,
    )


def test_lookup_of_a_known_spool_shows_its_state_and_menu(client: TestClient, token: str) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")

    result = scan(client, token, tag, "lookup")

    assert result["state"] == "sealed"
    assert result["actions"] == ["opened", "empty", "cancel"]
    assert result["suggested"] == "opened"
    assert result["product"]["id"] is not None
    assert result["spool"]["state"] == "sealed"


def test_an_empty_spool_offers_info_and_cancel(client: TestClient, token: str) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "opened")
    scan(client, token, tag, "empty")

    result = scan(client, token, tag, "lookup")

    assert result["actions"] == ["info", None, "cancel"]
    assert result["suggested"] == "info"


# --- Actions ---------------------------------------------------------------------------


def test_received_creates_product_spool_and_tag(
    client: TestClient, token: str, db: Session
) -> None:
    tag = SyntheticTag()
    body = scan_body(tag, "received", scanned_at=T0)

    result = post_scan(client, token, body)

    assert result["feedback"] == "ok"
    assert result["state"] == "sealed"
    assert result["event_id"] == body["event_id"]
    assert result["spool"]["received_at"] == T0.isoformat().replace("+00:00", "Z")
    spool = db.scalars(select(Spool)).one()
    assert spool.tray_uid == tag.tray_uid.hex().upper()
    assert spool.product.material_id == "GFA00"
    assert spool.product.provisional is False
    stored_tag = db.scalars(select(Tag)).one()
    assert stored_tag.uid == tag.tag_uid.hex().upper()
    assert stored_tag.spool_id == spool.id
    assert stored_tag.raw_blocks == tag.data_blocks()
    assert stored_tag.decoded_json is not None
    assert stored_tag.decoded_json["tray_uid"] == spool.tray_uid
    assert stored_tag.decoder_version == 1
    event = db.scalars(select(Event)).one()
    assert event.source is EventSource.SCANNER
    assert event.device_id == "scanner-1"
    assert event.occurred_at == T0


def test_scans_update_the_device(client: TestClient, token: str, db: Session) -> None:
    scan(client, token, SyntheticTag(), "lookup", fw_version="0.2.0")

    device = db.get(Device, "scanner-1")
    assert device is not None
    assert device.fw_version == "0.2.0"
    assert device.last_seen_at is not None


def test_scanned_at_defaults_to_server_time(client: TestClient, token: str, db: Session) -> None:
    before = datetime.now(UTC)
    scan(client, token, SyntheticTag(), "received")

    event = db.scalars(select(Event)).one()
    assert before <= event.occurred_at <= datetime.now(UTC)


def test_full_lifecycle_feedback(client: TestClient, token: str) -> None:
    tag = SyntheticTag()

    assert scan(client, token, tag, "received")["feedback"] == "ok"
    assert scan(client, token, tag, "opened")["feedback"] == "ok"
    result = scan(client, token, tag, "empty")

    assert result["feedback"] == "ok"
    assert result["state"] == "empty"


def test_opened_on_an_unknown_spool_is_an_implicit_receive(client: TestClient, token: str) -> None:
    result = scan(client, token, SyntheticTag(), "opened")

    assert result["feedback"] == "ok_created"
    assert result["state"] == "open"


def test_empty_on_an_unknown_spool_is_flagged(client: TestClient, token: str, db: Session) -> None:
    result = scan(client, token, SyntheticTag(), "empty")

    assert result["feedback"] == "flagged"
    assert db.scalars(select(Event)).one().flagged


def test_repeating_an_action_reports_already_in_state(client: TestClient, token: str) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")

    assert scan(client, token, tag, "received")["feedback"] == "already_in_state"


def test_new_on_an_open_spool_is_flagged(client: TestClient, token: str) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "opened")

    result = scan(client, token, tag, "received")

    assert result["feedback"] == "flagged"
    assert result["state"] == "open"


def test_either_tag_of_a_spool_finds_the_same_spool(
    client: TestClient, token: str, db: Session
) -> None:
    first = SyntheticTag()
    second = SyntheticTag(tray_uid=first.tray_uid)
    scan(client, token, first, "received")

    lookup = scan(client, token, second, "lookup")
    opened = scan(client, token, second, "opened")

    assert lookup["state"] == "sealed"
    assert opened["spool"]["id"] == lookup["spool"]["id"]
    assert _count(db, Spool) == 1
    assert {t.spool_id for t in db.scalars(select(Tag))} == {lookup["spool"]["id"]}
    assert _count(db, Tag) == 2


def test_two_rolls_of_one_product_are_two_spools_of_one_product(
    client: TestClient, token: str, db: Session
) -> None:
    scan(client, token, SyntheticTag(), "received")
    scan(client, token, SyntheticTag(), "received")

    assert _count(db, Product) == 1
    assert _count(db, Spool) == 2


def test_a_queued_scan_takes_its_true_place(client: TestClient, token: str) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "opened", scanned_at=T1)

    result = scan(client, token, tag, "received", scanned_at=T0)

    assert result["feedback"] == "ok"
    assert result["state"] == "open"
    assert result["spool"]["received_at"].startswith("2026-11-01")


# --- Idempotency -----------------------------------------------------------------------


def test_a_retried_event_id_returns_the_original_answer(
    client: TestClient, token: str, db: Session
) -> None:
    tag = SyntheticTag()
    body = scan_body(tag, "opened")

    first = post_scan(client, token, body)
    second = post_scan(client, token, body)

    assert first["feedback"] == "ok_created"
    assert second == first
    assert _count(db, Event) == 1


def test_an_event_id_used_by_another_device_is_refused(client: TestClient, token: str) -> None:
    other = register(client, "scanner-2")
    body = scan_body(SyntheticTag(), "received")
    post_scan(client, token, body)

    response = client.post(
        "/api/v1/scans", json={**body, "device_id": "scanner-2"}, headers=bearer(other)
    )

    assert response.status_code == 409


# --- Unreadable tags -------------------------------------------------------------------


def test_a_failed_read_keeps_the_uid_only(client: TestClient, token: str, db: Session) -> None:
    result = scan(client, token, SyntheticTag(), "received", read_ok=False, blocks=[])

    assert result["feedback"] == "unreadable"
    assert result["actions"] == [None, None, None]
    tag = db.scalars(select(Tag)).one()
    assert tag.spool_id is None
    assert tag.raw_blocks is None
    assert (_count(db, Spool), _count(db, Event)) == (0, 0)


def test_a_tag_that_does_not_decode_is_kept_with_its_blocks(
    client: TestClient, token: str, db: Session
) -> None:
    blank = ["00" * 16] * 48
    body = scan_body(SyntheticTag(), "lookup", blocks=blank)

    assert post_scan(client, token, body)["feedback"] == "unreadable"
    assert db.scalars(select(Tag)).one().raw_blocks == ["00" * 16] * 48


def test_a_uid_that_disagrees_with_the_blocks_is_unreadable(client: TestClient, token: str) -> None:
    result = scan(client, token, SyntheticTag(), "received", tag_uid="DEADBEEF")

    assert result["feedback"] == "unreadable"


def test_a_failed_read_does_not_erase_a_known_tag(
    client: TestClient, token: str, db: Session
) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")

    scan(client, token, tag, "opened", read_ok=False, blocks=[])

    stored = db.scalars(select(Tag)).one()
    assert stored.spool_id is not None
    assert stored.raw_blocks == tag.data_blocks()


# --- Manual placeholders ---------------------------------------------------------------


def _placeholder(db: Session, product: Product, at: datetime) -> Spool:
    spool = Spool(tray_uid=None, product=product)
    db.add(spool)
    append_event(db, spool, EventType.RECEIVED, EventSource.UI, at)
    db.commit()
    return spool


def _black_pla(**overrides: object) -> Product:
    values: dict[str, object] = {
        "material_id": "GFA00",
        "variant_id": "A00-K00",
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "display_name": "Black PLA Basic",
    }
    values.update(overrides)
    return Product(**values)


def test_a_first_scan_links_to_the_oldest_placeholder(
    client: TestClient, token: str, db: Session
) -> None:
    product = _black_pla()
    newer = _placeholder(db, product, T1)
    older = _placeholder(db, product, T0)
    tag = SyntheticTag()

    lookup = scan(client, token, tag, "lookup")
    opened = scan(client, token, tag, "opened")

    assert lookup["placeholder"] is True
    assert lookup["spool"]["id"] == older.id
    assert lookup["state"] == "sealed"
    assert opened["feedback"] == "flagged"
    assert opened["spool"]["id"] == older.id
    assert opened["state"] == "open"
    db.expire_all()
    assert db.get(Spool, older.id).tray_uid == tag.tray_uid.hex().upper()  # type: ignore[union-attr]
    assert db.get(Spool, newer.id).tray_uid is None  # type: ignore[union-attr]


def test_a_placeholder_is_not_offered_for_a_known_spool(
    client: TestClient, token: str, db: Session
) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")
    product = db.scalars(select(Product)).one()
    _placeholder(db, product, T0)

    assert scan(client, token, tag, "lookup")["placeholder"] is False


def test_a_provisional_product_is_filled_in_by_its_first_tag(
    client: TestClient, token: str, db: Session
) -> None:
    product = _black_pla(
        material_id=None, variant_id=None, provisional=True, display_name="Black TPU"
    )
    placeholder = _placeholder(db, product, T0)

    lookup = scan(client, token, SyntheticTag(), "lookup")
    received = scan(client, token, SyntheticTag(), "received")

    assert lookup["placeholder"] is True
    assert received["spool"]["id"] == placeholder.id
    db.expire_all()
    stored = db.get(Product, product.id)
    assert stored is not None
    assert (stored.provisional, stored.material_id, stored.variant_id) == (
        False,
        "GFA00",
        "A00-K00",
    )
    assert stored.display_name == "Black TPU"
    assert _count(db, Product) == 1


def test_an_ambiguous_provisional_match_is_not_used(
    client: TestClient, token: str, db: Session
) -> None:
    for name in ("One", "Two"):
        _placeholder(
            db,
            _black_pla(material_id=None, variant_id=None, provisional=True, display_name=name),
            T0,
        )

    result = scan(client, token, SyntheticTag(), "lookup")

    assert result["placeholder"] is False
    assert result["state"] == "unknown"


# --- Validation and device checks ------------------------------------------------------


def test_device_id_must_match_the_token(client: TestClient, token: str) -> None:
    register(client, "scanner-2")
    body = scan_body(SyntheticTag(), "lookup", device_id="scanner-2")

    response = client.post("/api/v1/scans", json=body, headers=bearer(token))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"tag_uid": "XYZ"},
        {"tag_uid": "A1B2C3D4E5"},
        {"blocks": ["00" * 16] * 49},
        {"blocks": ["zz" * 16]},
        {"blocks": ["00" * 15]},
        {"action": "destroy"},
        {"event_id": "not-a-uuid"},
        {"device_id": "Bad Id!"},
        {"scanned_at": "2026-11-05T12:00:00"},
        {"fw_version": "x" * 33},
        {"unexpected": "field"},
    ],
)
def test_invalid_scans_are_rejected(
    client: TestClient, token: str, overrides: dict[str, object]
) -> None:
    body = {**scan_body(SyntheticTag(), "lookup"), **overrides}

    response = client.post("/api/v1/scans", json=body, headers=bearer(token))

    assert response.status_code == 422


def test_the_openapi_page_lists_the_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"/api/v1/scans", "/api/v1/devices", "/api/v1/events/{event_id}/revert"} <= set(paths)
