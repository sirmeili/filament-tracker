"""Resolving Review items: accept a flagged event, dismiss an unidentified tag, and bring
either back."""

import pytest
from api_helpers import CSRF, admin, scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient

from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role


@pytest.fixture
def editor(app: FastAPI, client: TestClient) -> TestClient:
    return signed_in(app, Role.EDITOR)


def _flagged(client: TestClient, token: str) -> str:
    return scan(client, token, SyntheticTag(), "empty")["event_id"]  # empty on an unknown spool


def test_accepting_a_flagged_event_takes_it_out_of_review(
    client: TestClient, token: str, editor: TestClient
) -> None:
    event_id = _flagged(client, token)

    response = editor.post(f"/api/v1/review/events/{event_id}/accept", headers=CSRF)

    assert response.status_code == 200
    accepted = response.json()
    assert accepted["reviewed_by"] == "editor-user"
    assert accepted["reviewed_at"] is not None
    assert accepted["flagged"] is True
    assert editor.get("/api/v1/review").json()["flagged_events"] == []
    timeline = editor.get(f"/api/v1/spools/{accepted['spool_id']}").json()["events"]
    assert timeline[0]["reviewed_by"] == "editor-user"


def test_accepting_twice_keeps_the_first_review(
    app: FastAPI, client: TestClient, token: str, editor: TestClient
) -> None:
    event_id = _flagged(client, token)
    first = editor.post(f"/api/v1/review/events/{event_id}/accept", headers=CSRF).json()

    again = client.post(f"/api/v1/review/events/{event_id}/accept", headers=admin())

    assert again.status_code == 200
    assert again.json()["reviewed_at"] == first["reviewed_at"]
    assert again.json()["reviewed_by"] == "editor-user"


def test_the_admin_token_can_accept(client: TestClient, token: str) -> None:
    event_id = _flagged(client, token)

    accepted = client.post(f"/api/v1/review/events/{event_id}/accept", headers=admin()).json()

    assert accepted["reviewed_by"] is None
    assert accepted["reviewed_at"] is not None


def test_only_flagged_events_still_in_effect_can_be_accepted(
    client: TestClient, token: str, editor: TestClient
) -> None:
    normal = scan(client, token, SyntheticTag(), "received")["event_id"]
    undone = _flagged(client, token)
    client.post(f"/api/v1/events/{undone}/revert", headers=admin())

    for event_id in (normal, undone):
        response = editor.post(f"/api/v1/review/events/{event_id}/accept", headers=CSRF)
        assert response.status_code == 409
    missing = "00000000-0000-4000-8000-000000000000"
    assert editor.post(f"/api/v1/review/events/{missing}/accept", headers=CSRF).status_code == 404


def test_dismissing_an_unidentified_tag(client: TestClient, token: str, editor: TestClient) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received", read_ok=False, blocks=[])
    uid = tag.tag_uid.hex()  # lower case is accepted

    assert editor.post(f"/api/v1/review/tags/{uid}/dismiss", headers=CSRF).status_code == 204
    assert editor.get("/api/v1/review").json()["unidentified_tags"] == []
    assert editor.post(f"/api/v1/review/tags/{uid}/dismiss", headers=CSRF).status_code == 204


def test_only_unidentified_tags_can_be_dismissed(
    client: TestClient, token: str, editor: TestClient
) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")
    uid = tag.tag_uid.hex().upper()

    assert editor.post(f"/api/v1/review/tags/{uid}/dismiss", headers=CSRF).status_code == 409
    assert editor.post("/api/v1/review/tags/DEADBEEF/dismiss", headers=CSRF).status_code == 404


def test_viewers_cannot_resolve_review_items(app: FastAPI, client: TestClient, token: str) -> None:
    viewer = signed_in(app, Role.VIEWER)
    event_id = _flagged(client, token)

    assert viewer.post(f"/api/v1/review/events/{event_id}/accept", headers=CSRF).status_code == 403
    assert viewer.post("/api/v1/review/tags/DEADBEEF/dismiss", headers=CSRF).status_code == 403


# --- Bring back ------------------------------------------------------------------------------


def test_bringing_back_an_accepted_event(
    client: TestClient, token: str, editor: TestClient
) -> None:
    event_id = _flagged(client, token)
    editor.post(f"/api/v1/review/events/{event_id}/accept", headers=CSRF)

    response = editor.post(f"/api/v1/review/events/{event_id}/unaccept", headers=CSRF)

    assert response.status_code == 200
    assert (response.json()["reviewed_at"], response.json()["reviewed_by"]) == (None, None)
    [back] = editor.get("/api/v1/review").json()["flagged_events"]
    assert back["id"] == event_id
    # Bringing back an event that is already in Review changes nothing.
    assert (
        editor.post(f"/api/v1/review/events/{event_id}/unaccept", headers=CSRF).status_code == 200
    )


def test_only_flagged_events_still_in_effect_can_be_brought_back(
    client: TestClient, token: str, editor: TestClient
) -> None:
    normal = scan(client, token, SyntheticTag(), "received")["event_id"]
    undone = _flagged(client, token)
    editor.post(f"/api/v1/review/events/{undone}/accept", headers=CSRF)
    client.post(f"/api/v1/events/{undone}/revert", headers=admin())

    for event_id in (normal, undone):
        response = editor.post(f"/api/v1/review/events/{event_id}/unaccept", headers=CSRF)
        assert response.status_code == 409
    missing = "00000000-0000-4000-8000-000000000000"
    assert editor.post(f"/api/v1/review/events/{missing}/unaccept", headers=CSRF).status_code == 404


def test_bringing_back_a_dismissed_tag(client: TestClient, token: str, editor: TestClient) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received", read_ok=False, blocks=[])
    uid = tag.tag_uid.hex().upper()
    editor.post(f"/api/v1/review/tags/{uid}/dismiss", headers=CSRF)

    assert (
        editor.post(f"/api/v1/review/tags/{uid.lower()}/restore", headers=CSRF).status_code == 204
    )
    [back] = editor.get("/api/v1/review").json()["unidentified_tags"]
    assert back["uid"] == uid
    assert editor.post(f"/api/v1/review/tags/{uid}/restore", headers=CSRF).status_code == 204


def test_only_unidentified_tags_can_be_brought_back(
    client: TestClient, token: str, editor: TestClient
) -> None:
    tag = SyntheticTag()
    scan(client, token, tag, "received")

    uid = tag.tag_uid.hex().upper()
    assert editor.post(f"/api/v1/review/tags/{uid}/restore", headers=CSRF).status_code == 409
    assert editor.post("/api/v1/review/tags/DEADBEEF/restore", headers=CSRF).status_code == 404


def test_viewers_cannot_bring_items_back(app: FastAPI, client: TestClient, token: str) -> None:
    viewer = signed_in(app, Role.VIEWER)
    event_id = _flagged(client, token)

    assert (
        viewer.post(f"/api/v1/review/events/{event_id}/unaccept", headers=CSRF).status_code == 403
    )
    assert viewer.post("/api/v1/review/tags/DEADBEEF/restore", headers=CSRF).status_code == 403
