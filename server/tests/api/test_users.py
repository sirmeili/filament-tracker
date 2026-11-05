"""Managing accounts: Admin only, and there is always an active Admin."""

from api_helpers import CSRF, PASSWORD, admin, browser, login, make_user, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import UserSession
from filament_tracker.domain.enums import Role

NEW = {"username": "Bob", "password": "bobs long password", "role": "viewer"}


def test_admins_create_and_list_users(app: FastAPI, client: TestClient) -> None:
    boss = signed_in(app, Role.ADMIN, username="boss")

    created = boss.post("/api/v1/users", json=NEW, headers=CSRF)

    assert created.status_code == 201
    assert created.json()["username"] == "bob"
    assert created.json()["disabled"] is False
    assert "password" not in created.text and "hash" not in created.text
    names = [u["username"] for u in boss.get("/api/v1/users").json()]
    assert names == ["bob", "boss"]
    assert login(browser(app), "bob", NEW["password"]).status_code == 200


def test_the_admin_token_can_manage_users(client: TestClient) -> None:
    assert client.post("/api/v1/users", json=NEW, headers=admin()).status_code == 201
    assert len(client.get("/api/v1/users", headers=admin()).json()) == 1


def test_usernames_are_unique_regardless_of_case(client: TestClient) -> None:
    client.post("/api/v1/users", json=NEW, headers=admin())

    again = client.post("/api/v1/users", json={**NEW, "username": "BOB"}, headers=admin())

    assert again.status_code == 409


def test_new_users_must_follow_the_rules(client: TestClient) -> None:
    for bad in ({"password": "short"}, {"username": "no spaces allowed"}, {"username": "x"}):
        response = client.post("/api/v1/users", json={**NEW, **bad}, headers=admin())
        assert response.status_code == 422, bad
    assert (
        client.post("/api/v1/users", json={**NEW, "role": "owner"}, headers=admin()).status_code
        == 422
    )


def test_changing_a_role(app: FastAPI, client: TestClient) -> None:
    user_id = make_user(app, "bob", Role.VIEWER)

    response = client.patch(f"/api/v1/users/{user_id}", json={"role": "editor"}, headers=admin())

    assert response.json()["role"] == "editor"


def test_disabling_signs_the_user_out_and_enabling_lets_them_back(
    app: FastAPI, client: TestClient, db: Session
) -> None:
    bob = signed_in(app, Role.EDITOR, username="bob")

    response = client.patch("/api/v1/users/1", json={"disabled": True}, headers=admin())

    assert response.json()["disabled"] is True
    assert bob.get("/api/v1/auth/me").status_code == 401
    assert db.scalars(select(UserSession)).all() == []
    assert login(browser(app), "bob").status_code == 401

    client.patch("/api/v1/users/1", json={"disabled": False}, headers=admin())
    assert login(browser(app), "bob").status_code == 200


def test_resetting_a_password_signs_the_user_out(app: FastAPI, client: TestClient) -> None:
    bob = signed_in(app, Role.EDITOR, username="bob")

    response = client.patch(
        "/api/v1/users/1", json={"password": "a fresh password"}, headers=admin()
    )

    assert response.status_code == 200
    assert bob.get("/api/v1/auth/me").status_code == 401
    assert login(browser(app), "bob", PASSWORD).status_code == 401
    assert login(browser(app), "bob", "a fresh password").status_code == 200


def test_a_reset_password_must_follow_the_rules(app: FastAPI, client: TestClient) -> None:
    make_user(app, "bob", Role.EDITOR)

    response = client.patch("/api/v1/users/1", json={"password": "short"}, headers=admin())

    assert response.status_code == 422


def test_the_last_active_admin_cannot_be_demoted_or_disabled(
    app: FastAPI, client: TestClient
) -> None:
    boss = signed_in(app, Role.ADMIN, username="boss")

    for change in ({"role": "editor"}, {"disabled": True}):
        response = boss.patch("/api/v1/users/1", json=change, headers=CSRF)
        assert response.status_code == 409, change

    make_user(app, "second", Role.ADMIN)
    assert boss.patch("/api/v1/users/1", json={"role": "editor"}, headers=CSRF).status_code == 200


def test_a_disabled_admin_does_not_count(app: FastAPI, client: TestClient) -> None:
    make_user(app, "boss", Role.ADMIN)
    make_user(app, "other", Role.ADMIN)
    client.patch("/api/v1/users/2", json={"disabled": True}, headers=admin())

    assert (
        client.patch("/api/v1/users/1", json={"disabled": True}, headers=admin()).status_code == 409
    )


def test_unknown_users_are_404(client: TestClient) -> None:
    assert (
        client.patch("/api/v1/users/99", json={"role": "viewer"}, headers=admin()).status_code
        == 404
    )


def test_only_admins_manage_users(app: FastAPI, client: TestClient) -> None:
    for role in (Role.VIEWER, Role.EDITOR):
        user = signed_in(app, role)
        assert user.get("/api/v1/users").status_code == 403
        assert user.post("/api/v1/users", json=NEW, headers=CSRF).status_code == 403
        assert (
            user.patch("/api/v1/users/1", json={"role": "admin"}, headers=CSRF).status_code == 403
        )
