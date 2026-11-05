from datetime import timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User, UserSession
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import (
    SESSION_TOUCH_INTERVAL,
    AccountError,
    UsernameTaken,
    authenticate,
    count_active_admins,
    create_user,
    end_sessions,
    find_session,
    hash_session_token,
    normalize_username,
    set_password,
    start_session,
)

PASSWORD = "correct horse battery"  # noqa: S105 - test value


@pytest.mark.parametrize(
    ("raw", "expected"), [(" Alice ", "alice"), ("a.b_c-d", "a.b_c-d"), ("x" * 32, "x" * 32)]
)
def test_usernames_are_normalized(raw: str, expected: str) -> None:
    assert normalize_username(raw) == expected


@pytest.mark.parametrize("raw", ["ab", "x" * 33, "_alice", "al ice", "alice!", "ålice"])
def test_bad_usernames_are_refused(raw: str) -> None:
    with pytest.raises(AccountError):
        normalize_username(raw)


@pytest.mark.parametrize("password", ["x" * 11, "x" * 257])
def test_password_length_is_enforced(session: Session, password: str) -> None:
    with pytest.raises(AccountError, match="12 to 256"):
        create_user(session, "alice", password, Role.VIEWER)


def test_passwords_are_stored_as_argon2id(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)

    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_usernames_are_unique_regardless_of_case(session: Session) -> None:
    create_user(session, "alice", PASSWORD, Role.VIEWER)

    with pytest.raises(UsernameTaken):
        create_user(session, "ALICE", PASSWORD, Role.VIEWER)


def test_authenticate(session: Session) -> None:
    create_user(session, "alice", PASSWORD, Role.VIEWER)

    assert authenticate(session, " Alice", PASSWORD) is not None
    assert authenticate(session, "alice", "wrong password") is None
    assert authenticate(session, "nobody", PASSWORD) is None


def test_disabled_users_do_not_authenticate(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    user.disabled_at = utcnow()

    assert authenticate(session, "alice", PASSWORD) is None


def test_a_corrupt_hash_does_not_authenticate(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    user.password_hash = "not a hash"  # noqa: S105 - deliberately corrupt

    assert authenticate(session, "alice", PASSWORD) is None


def test_old_hash_parameters_are_upgraded_on_sign_in(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    user.password_hash = PasswordHasher(time_cost=1, memory_cost=8192).hash(PASSWORD)
    old = user.password_hash

    assert authenticate(session, "alice", PASSWORD) is user
    assert user.password_hash != old
    assert authenticate(session, "alice", PASSWORD) is user


def test_set_password_ends_other_sessions(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    now = utcnow()
    start_session(session, user, 30, now)
    start_session(session, user, 30, now)
    session.flush()
    keep = session.scalars(select(UserSession)).first()
    before = user.password_changed_at

    set_password(session, user, "another long password", keep=keep)

    assert session.scalars(select(UserSession)).all() == [keep]
    assert user.password_changed_at >= before
    assert authenticate(session, "alice", "another long password") is user


def test_end_sessions_without_keep_ends_all(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    start_session(session, user, 30, utcnow())
    session.flush()

    end_sessions(session, user)

    assert user.sessions == []


def test_count_active_admins(session: Session) -> None:
    assert count_active_admins(session) == 0
    create_user(session, "boss", PASSWORD, Role.ADMIN)
    create_user(session, "eddie", PASSWORD, Role.EDITOR)
    create_user(session, "old", PASSWORD, Role.ADMIN).disabled_at = utcnow()
    session.flush()

    assert count_active_admins(session) == 1


def test_sessions_store_only_a_hash(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    now = utcnow()

    token = start_session(session, user, 30, now)
    session.flush()

    stored = session.scalars(select(UserSession)).one()
    assert stored.token_hash == hash_session_token(token)
    assert stored.expires_at == now + timedelta(days=30)
    assert user.last_login_at == now
    assert find_session(session, token, now) is stored
    assert find_session(session, "unknown", now) is None


def test_expired_sessions_are_deleted(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    now = utcnow()
    token = start_session(session, user, 1, now)
    session.commit()

    assert find_session(session, token, now + timedelta(days=1)) is None
    assert session.scalars(select(UserSession)).all() == []


def test_sessions_of_disabled_users_are_deleted(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    now = utcnow()
    token = start_session(session, user, 30, now)
    user.disabled_at = now
    session.commit()

    assert find_session(session, token, now) is None
    assert session.scalars(select(User)).one().sessions == []


def test_last_seen_is_updated_at_most_every_few_minutes(session: Session) -> None:
    user = create_user(session, "alice", PASSWORD, Role.VIEWER)
    now = utcnow()
    token = start_session(session, user, 30, now)
    session.commit()

    soon = now + timedelta(minutes=1)
    assert find_session(session, token, soon).last_seen_at == now
    later = now + SESSION_TOUCH_INTERVAL
    assert find_session(session, token, later).last_seen_at == later
