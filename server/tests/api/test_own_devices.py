"""A signed-in user's own phone (Phone scanner, Pairing and Users and roles in docs/SPEC.md):
set up after signing in at home, its scans are the user's and follow the user's role."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from api_helpers import (
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
    scan_body,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_devices import salted_app

from filament_tracker.api.devices import MAX_OWN_DEVICES
from filament_tracker.auth import REFUSED_HEADER, TOKEN_PREFIX, hash_token
from filament_tracker.db.models import Device, Event, User
from filament_tracker.db.types import utcnow
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role

MINE = "/api/v1/devices/mine"


def set_up(phone: TestClient, name: str = "Pixel 9") -> dict[str, Any]:
    response = phone.post(MINE, json={"name": name}, headers=CSRF)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_signed_in_user_sets_up_their_phone_and_gets_a_token_once(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    phone = signed_in(app, Role.VIEWER, username="bob")

    body = set_up(phone, "  Pixel 9  ")

    assert body["id"].startswith("phone-")
    assert body["name"] == "Pixel 9"
    assert body["owner"] == "bob"
    assert body["token"].startswith(TOKEN_PREFIX)
    device = db.get(Device, body["id"])
    assert device is not None and device.user is not None
    assert device.user.username == "bob"
    assert device.token_hash == hash_token(body["token"])
    listed = client.get("/api/v1/devices", headers=admin()).json()
    assert [(d["id"], d["owner"]) for d in listed] == [(body["id"], "bob")]
    assert all("token" not in d for d in listed)


def test_shared_scanners_belong_to_no_one(client: TestClient, token: str) -> None:
    listed = client.get("/api/v1/devices", headers=admin()).json()
    assert [d["owner"] for d in listed] == [None]


def test_setting_up_a_phone_needs_a_signed_in_user(client: TestClient, token: str) -> None:
    assert client.post(MINE, json={"name": "x"}, headers=CSRF).status_code == 401
    # A token is not a person: neither a scanner nor the admin token owns a phone.
    assert client.post(MINE, json={"name": "x"}, headers=bearer(token)).status_code == 403
    assert client.post(MINE, json={"name": "x"}, headers=admin()).status_code == 403


def test_setting_up_a_phone_needs_the_write_header(app: FastAPI, client: TestClient) -> None:
    phone = signed_in(app, Role.EDITOR)
    assert phone.post(MINE, json={"name": "Pixel"}).status_code == 403


def test_a_phone_is_set_up_only_on_the_home_network(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    away = signed_in(app, Role.EDITOR, client=INTERNET_CLIENT)

    response = away.post(MINE, json={"name": "Pixel"}, headers=CSRF)

    assert response.status_code == 403
    assert response.headers[REFUSED_HEADER] == "local-network-only"
    assert db.scalars(select(Device)).all() == []


def test_bad_names_are_refused(app: FastAPI, client: TestClient) -> None:
    phone = signed_in(app, Role.EDITOR)
    for name in ("", "   ", "x" * 61, "Pixel\n9", "Pixel\x009"):
        assert phone.post(MINE, json={"name": name}, headers=CSRF).status_code == 422
    assert phone.post(MINE, json={"name": "P", "id": "mine"}, headers=CSRF).status_code == 422


def test_one_user_may_have_a_few_phones_at_once(app: FastAPI, client: TestClient) -> None:
    phone = signed_in(app, Role.EDITOR)
    first = set_up(phone)
    for _ in range(MAX_OWN_DEVICES - 1):
        set_up(phone)

    refused = phone.post(MINE, json={"name": "One more"}, headers=CSRF)
    assert refused.status_code == 409
    assert "unlink one first" in refused.json()["detail"]

    # Unlinking one frees its place; another user has places of their own.
    assert client.post("/api/v1/devices/unlink", headers=bearer(first["token"])).status_code == 204
    set_up(phone)
    set_up(signed_in(app, Role.VIEWER))


def test_an_editors_phone_records_scans_as_the_editor(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    phone = set_up(signed_in(app, Role.EDITOR, username="ann"))
    body = scan_body(SyntheticTag(), "received", device_id=phone["id"])

    response = client.post("/api/v1/scans", json=body, headers=bearer(phone["token"]))

    assert response.status_code == 200, response.text
    event = db.scalar(select(Event))
    assert event is not None and event.user is not None
    assert (event.device_id, event.user.username) == (phone["id"], "ann")
    activity = client.get("/api/v1/events", headers=admin()).json()
    entry = activity["items"][0] if isinstance(activity, dict) else activity[0]
    assert (entry["username"], entry["device_name"]) == ("ann", "Pixel 9")

    undo = client.post(f"/api/v1/events/{body['event_id']}/revert", headers=bearer(phone["token"]))
    assert undo.status_code == 200, undo.text
    revert = db.get(Event, UUID(undo.json()["revert_event_id"]))
    assert revert is not None and revert.user_id == event.user_id


def test_a_viewers_phone_looks_spools_up_but_records_nothing(
    app: FastAPI, client: TestClient, db: Session, token: str
) -> None:
    phone = set_up(signed_in(app, Role.VIEWER))
    tag = SyntheticTag()
    headers = bearer(phone["token"])

    lookup = client.post(
        "/api/v1/scans", json=scan_body(tag, "lookup", device_id=phone["id"]), headers=headers
    )
    assert lookup.status_code == 200
    # Nothing to record: only Cancel for a spool the server does not know yet.
    assert lookup.json()["actions"] == [None, None, "cancel"]
    assert lookup.json()["suggested"] is None

    for action in ("received", "opened", "empty"):
        refused = client.post(
            "/api/v1/scans", json=scan_body(tag, action, device_id=phone["id"]), headers=headers
        )
        assert refused.status_code == 403
        assert "look spools up but not record" in refused.json()["detail"]
    assert db.scalars(select(Event)).all() == []

    # Heartbeats and provisioning still work; undo does not, even of a shared scanner's.
    beat = {"fw_version": "app", "queue_length": 0}
    assert client.post("/api/v1/devices/heartbeat", json=beat, headers=headers).status_code == 204
    shared = scan_body(tag, "received")
    assert client.post("/api/v1/scans", json=shared, headers=bearer(token)).status_code == 200
    undo = client.post(f"/api/v1/events/{shared['event_id']}/revert", headers=headers)
    assert undo.status_code == 403

    # Once the spool is known, Info shows it.
    known = client.post(
        "/api/v1/scans", json=scan_body(tag, "lookup", device_id=phone["id"]), headers=headers
    )
    assert known.json()["actions"] == ["info", None, "cancel"]
    assert known.json()["spool"] is not None


def test_a_role_change_applies_to_the_phone_at_once(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    phone = set_up(signed_in(app, Role.EDITOR, username="cat"))
    user = db.scalar(select(User).where(User.username == "cat"))
    assert user is not None
    user.role = Role.VIEWER
    db.commit()

    body = scan_body(SyntheticTag(), "opened", device_id=phone["id"])
    response = client.post("/api/v1/scans", json=body, headers=bearer(phone["token"]))

    assert response.status_code == 403


def test_a_disabled_users_phone_is_refused(app: FastAPI, client: TestClient, db: Session) -> None:
    phone = set_up(signed_in(app, Role.EDITOR, username="dan"))
    user = db.scalar(select(User).where(User.username == "dan"))
    assert user is not None
    user.disabled_at = utcnow()
    db.commit()

    body = scan_body(SyntheticTag(), "lookup", device_id=phone["id"])
    response = client.post("/api/v1/scans", json=body, headers=bearer(phone["token"]))

    assert response.status_code == 401


def test_provisioning_tells_a_phone_whether_it_records(db_url: str) -> None:
    app = salted_app(db_url)
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        viewer = set_up(signed_in(app, Role.VIEWER))
        editor = set_up(signed_in(app, Role.EDITOR))
        shared = register(client)
        url = "/api/v1/devices/provisioning"

        assert client.get(url, headers=bearer(viewer["token"])).json()["records"] is False
        assert client.get(url, headers=bearer(editor["token"])).json()["records"] is True
        assert client.get(url, headers=bearer(shared)).json()["records"] is True


# --- Sessions in use stay alive ---------------------------------------------------------


def _expire_in(app: FastAPI, days: float) -> None:
    from filament_tracker.db.models import UserSession

    with app.state.session_factory() as session:
        for found in session.scalars(select(UserSession)):
            found.expires_at = utcnow() + timedelta(days=days)
        session.commit()


def _expiry(app: FastAPI) -> timedelta:
    from filament_tracker.db.models import UserSession

    with app.state.session_factory() as session:
        found = session.scalars(select(UserSession)).one()
        return found.expires_at - utcnow()


def test_a_session_in_use_is_renewed_when_half_its_time_is_gone(
    app: FastAPI, client: TestClient
) -> None:
    make_user(app, "eve", Role.VIEWER)
    web = browser(app)
    assert login(web, "eve").status_code == 200
    days = app.state.settings_store.session_days()

    fresh = web.get("/api/v1/auth/me")
    assert fresh.status_code == 200
    assert "set-cookie" not in fresh.headers  # plenty of time left: nothing changes

    _expire_in(app, days / 2 - 1)
    renewed = web.get("/api/v1/auth/me")

    assert renewed.status_code == 200
    cookie = renewed.headers["set-cookie"]
    assert cookie.startswith("ft_session=")
    assert f"Max-Age={days * 24 * 3600}" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Secure" in cookie
    assert _expiry(app) > timedelta(days=days - 1)
    # The renewed cookie keeps working, and the next request has nothing to renew.
    again = web.get("/api/v1/auth/me")
    assert again.status_code == 200 and "set-cookie" not in again.headers


def test_signing_out_is_not_undone_by_a_renewal(app: FastAPI, client: TestClient) -> None:
    make_user(app, "fay", Role.VIEWER)
    web = browser(app)
    assert login(web, "fay").status_code == 200
    _expire_in(app, 1)

    out = web.post("/api/v1/auth/logout", headers=CSRF)

    assert out.status_code == 204
    assert 'ft_session=""' in out.headers["set-cookie"] or "Max-Age=0" in out.headers["set-cookie"]
    assert web.get("/api/v1/auth/me").status_code == 401


def test_an_expired_session_is_not_renewed(app: FastAPI, client: TestClient) -> None:
    make_user(app, "gus", Role.VIEWER)
    web = browser(app)
    assert login(web, "gus").status_code == 200
    _expire_in(app, -1)

    response = web.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
