from uuid import uuid4

from api_helpers import admin, bearer, register, scan
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Event
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import EventSource, EventType


def _revert(client: TestClient, event_id: str, headers: dict[str, str]):  # noqa: ANN202
    return client.post(f"/api/v1/events/{event_id}/revert", headers=headers)


def test_a_scanner_can_undo_its_own_scan(client: TestClient, token: str, db: Session) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")
    opened = scan(client, token, tag, "opened")

    response = _revert(client, opened["event_id"], bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["reverted_event_id"] == opened["event_id"]
    assert body["spool"]["state"] == "sealed"
    revert = db.scalars(select(Event).where(Event.type == EventType.REVERT)).one()
    assert revert.source is EventSource.SCANNER
    assert revert.device_id == "scanner-1"
    assert scan(client, token, tag, "lookup")["state"] == "sealed"


def test_the_admin_can_undo_any_event(client: TestClient, token: str, db: Session) -> None:
    received = scan(client, token, SyntheticTag(), "received")

    response = _revert(client, received["event_id"], admin())

    assert response.status_code == 200
    assert response.json()["spool"]["state"] == "unknown"
    revert = db.scalars(select(Event).where(Event.type == EventType.REVERT)).one()
    assert revert.source is EventSource.UI
    assert revert.device_id is None


def test_a_scanner_cannot_undo_another_scanners_event(client: TestClient, token: str) -> None:
    other = register(client, "scanner-2")
    received = scan(client, token, SyntheticTag(), "received")

    assert _revert(client, received["event_id"], bearer(other)).status_code == 403


def test_unknown_events_are_not_found(client: TestClient) -> None:
    assert _revert(client, str(uuid4()), admin()).status_code == 404


def test_an_event_cannot_be_undone_twice(client: TestClient, token: str) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    _revert(client, received["event_id"], admin())

    response = _revert(client, received["event_id"], admin())

    assert response.status_code == 409
    assert "already been undone" in response.json()["detail"]


def test_an_undo_cannot_be_undone(client: TestClient, token: str) -> None:
    received = scan(client, token, SyntheticTag(), "received")
    revert_id = _revert(client, received["event_id"], admin()).json()["revert_event_id"]

    assert _revert(client, revert_id, admin()).status_code == 409
