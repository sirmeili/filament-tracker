"""Sign-in, sign-out, the current user and password changes."""

from datetime import timedelta

from api_helpers import (
    CSRF,
    INTERNET_CLIENT,
    PASSWORD,
    admin,
    browser,
    login,
    make_user,
    signed_in,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User, UserSession
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role

NEW_PASSWORD = "a brand new passphrase"  # noqa: S105 - test value


def test_login_sets_a_strict_session_cookie_and_returns_the_user(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    make_user(app, "Alice", Role.EDITOR)

    response = login(client, "ALICE")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "username": "alice", "role": "editor"}
    cookie = response.headers["set-cookie"].lower()
    for attribute in ("ft_session=", "httponly", "secure", "samesite=strict", "path=/"):
        assert attribute in cookie
    assert f"max-age={30 * 24 * 3600}" in cookie
    stored = db.scalars(select(UserSession)).one()
    assert response.cookies["ft_session"] not in stored.token_hash
    assert len(stored.token_hash) == 64
    assert db.get(User, 1).last_login_at is not None


def test_me_returns_the_signed_in_user(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER)

    assert viewer.get("/api/v1/auth/me").json()["role"] == "viewer"


def test_me_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=admin()).status_code == 403


def test_wrong_password_and_unknown_user_look_the_same(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)

    wrong = login(client, "alice", "not the password")
    unknown = login(client, "nobody", "not the password")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "invalid username or password"}
    assert "set-cookie" not in wrong.headers


def test_disabled_users_cannot_sign_in(app: FastAPI, client: TestClient, db: Session) -> None:
    make_user(app, "alice", Role.VIEWER)
    db.get(User, 1).disabled_at = utcnow()
    db.commit()

    assert login(client, "alice").status_code == 401


def test_login_needs_the_csrf_header(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)

    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 403


def test_login_works_from_the_internet(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)

    assert login(browser(app, INTERNET_CLIENT), "alice").status_code == 200


def test_logout_ends_the_session(app: FastAPI, client: TestClient, db: Session) -> None:
    viewer = signed_in(app, Role.VIEWER)

    response = viewer.post("/api/v1/auth/logout", headers=CSRF)

    assert response.status_code == 204
    assert 'ft_session=""' in response.headers["set-cookie"]
    assert db.scalars(select(UserSession)).all() == []
    assert viewer.get("/api/v1/auth/me").status_code == 401


def test_logout_without_a_session_still_succeeds(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204


def test_logout_needs_the_csrf_header(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER)

    assert viewer.post("/api/v1/auth/logout").status_code == 403
    assert viewer.get("/api/v1/auth/me").status_code == 200


def test_expired_sessions_are_refused_and_removed(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    viewer = signed_in(app, Role.VIEWER)
    db.scalars(select(UserSession)).one().expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    assert viewer.get("/api/v1/auth/me").status_code == 401
    db.expire_all()
    assert db.scalars(select(UserSession)).all() == []


def test_a_forged_cookie_is_refused(client: TestClient) -> None:
    client.cookies.set("ft_session", "made-up-value", domain="testserver")

    assert client.get("/api/v1/auth/me").status_code == 401


def test_change_password_keeps_this_session_and_ends_others(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    here = signed_in(app, Role.VIEWER, username="alice")
    elsewhere = browser(app)
    login(elsewhere, "alice")

    response = here.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=CSRF,
    )

    assert response.status_code == 204
    assert here.get("/api/v1/auth/me").status_code == 200
    assert elsewhere.get("/api/v1/auth/me").status_code == 401
    assert login(browser(app), "alice", PASSWORD).status_code == 401
    assert login(browser(app), "alice", NEW_PASSWORD).status_code == 200


def test_change_password_checks_the_current_one(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER)

    response = viewer.post(
        "/api/v1/auth/password",
        json={"current_password": "wrong password!", "new_password": NEW_PASSWORD},
        headers=CSRF,
    )

    assert response.status_code == 403


def test_change_password_enforces_the_rules(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER)

    response = viewer.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=CSRF,
    )

    assert response.status_code == 422
    assert "12" in response.json()["detail"]


def test_tokens_cannot_change_a_password(client: TestClient) -> None:
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}

    assert client.post("/api/v1/auth/password", json=body, headers=admin()).status_code == 403


def test_repeated_failures_are_throttled_per_username(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)
    for _ in range(5):
        assert login(client, "alice", "wrong password!").status_code == 401

    blocked = login(client, "alice")

    assert blocked.status_code == 429
    assert login(client, "someone-else", "wrong password!").status_code == 401


def test_repeated_failures_are_throttled_per_address(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)
    for n in range(20):
        login(client, f"user{n}", "wrong password!")

    assert login(client, "alice").status_code == 429
    assert login(browser(app, INTERNET_CLIENT), "alice").status_code == 200


def test_a_success_clears_the_username_count(app: FastAPI, client: TestClient) -> None:
    make_user(app, "alice", Role.VIEWER)
    for _ in range(4):
        login(client, "alice", "wrong password!")
    assert login(client, "alice").status_code == 200

    for _ in range(4):
        login(client, "alice", "wrong password!")
    assert login(client, "alice").status_code == 200


def test_wrong_current_passwords_are_throttled(app: FastAPI, client: TestClient) -> None:
    viewer = signed_in(app, Role.VIEWER)
    body = {"current_password": "wrong password!", "new_password": NEW_PASSWORD}
    for _ in range(5):
        viewer.post("/api/v1/auth/password", json=body, headers=CSRF)

    body["current_password"] = PASSWORD
    assert viewer.post("/api/v1/auth/password", json=body, headers=CSRF).status_code == 429
