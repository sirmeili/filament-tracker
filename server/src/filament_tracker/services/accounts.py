"""User accounts and browser sessions (Users and roles in docs/SPEC.md)."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from filament_tracker.db.models import User, UserSession
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role

MIN_PASSWORD = 12
MAX_PASSWORD = 256
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

_hasher = PasswordHasher()  # Argon2id with the library's current recommended parameters
# Verified against when a username does not exist, so both paths take the same time.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


class AccountError(ValueError):
    """A request about accounts that cannot be carried out."""


class UsernameTaken(AccountError):
    """Another account already has this username."""


def normalize_username(username: str) -> str:
    name = username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(name):
        raise AccountError(
            "usernames are 3 to 32 characters: letters, digits, '.', '_' or '-', "
            "starting with a letter or digit"
        )
    return name


def check_password_rules(password: str) -> None:
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise AccountError(f"passwords must be {MIN_PASSWORD} to {MAX_PASSWORD} characters")


def hash_password(password: str) -> str:
    check_password_rules(password)
    return _hasher.hash(password)


def create_user(session: Session, username: str, password: str, role: Role) -> User:
    name = normalize_username(username)
    if session.scalar(select(User).where(User.username == name)) is not None:
        raise UsernameTaken("that username is taken")
    user = User(username=name, password_hash=hash_password(password), role=role)
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, username: str, password: str) -> User | None:
    """The active user with this username and password, or None. Timing does not
    reveal whether the username exists."""
    user = session.scalar(select(User).where(User.username == username.strip().lower()))
    stored = user.password_hash if user is not None else _DUMMY_HASH
    try:
        _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return None
    if user is None or user.disabled_at is not None:
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    return user


def set_password(
    session: Session, user: User, password: str, *, keep: UserSession | None = None
) -> None:
    """Change a password and end the user's sessions, except `keep`."""
    user.password_hash = hash_password(password)
    user.password_changed_at = utcnow()
    end_sessions(session, user, keep=keep)


def end_sessions(session: Session, user: User, *, keep: UserSession | None = None) -> None:
    query = delete(UserSession).where(UserSession.user_id == user.id)
    if keep is not None:
        query = query.where(UserSession.id != keep.id)
    session.execute(query)
    session.expire(user, ["sessions"])


def count_active_admins(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.ADMIN, User.disabled_at.is_(None))
        )
        or 0
    )


# --- Sessions ----------------------------------------------------------------------------

SESSION_TOUCH_INTERVAL = timedelta(minutes=5)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(session: Session, user: User, days: int, now: datetime) -> str:
    """Create a session and return the cookie value (never stored)."""
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            token_hash=hash_session_token(token),
            user=user,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=days),
        )
    )
    user.last_login_at = now
    return token


def find_session(session: Session, token: str, now: datetime) -> UserSession | None:
    """The live session for a cookie value; expired ones are deleted."""
    found = session.scalar(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    if found is None:
        return None
    if found.expires_at <= now or found.user.disabled_at is not None:
        session.delete(found)
        session.commit()
        return None
    if now - found.last_seen_at >= SESSION_TOUCH_INTERVAL:
        found.last_seen_at = now
        session.commit()
    return found
