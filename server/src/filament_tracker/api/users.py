"""Manage web app accounts (Admin role or the admin token).

There is always at least one active Admin: the last one cannot be demoted or disabled.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from filament_tracker.api.account_schemas import UserCreate, UserOut, UserUpdate
from filament_tracker.auth import Admin, DbSession
from filament_tracker.db.models import User
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import (
    AccountError,
    UsernameTaken,
    count_active_admins,
    create_user,
    end_sessions,
    set_password,
)

router = APIRouter(tags=["users"])


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        disabled=user.disabled_at is not None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _invalid(exc: AccountError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.get("/users", response_model=list[UserOut])
def list_users(_: Admin, session: DbSession) -> list[UserOut]:
    return [user_out(u) for u in session.scalars(select(User).order_by(User.username))]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_user(body: UserCreate, _: Admin, session: DbSession) -> UserOut:
    try:
        user = create_user(session, body.username, body.password, body.role)
    except UsernameTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AccountError as exc:
        raise _invalid(exc) from exc
    session.commit()
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, _: Admin, session: DbSession) -> UserOut:
    """Change role, disable or enable, or reset the password. Disabling or a password
    reset signs the user out everywhere."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")
    was_active_admin = user.role == Role.ADMIN and user.disabled_at is None
    loses_admin = (body.role is not None and body.role != Role.ADMIN) or body.disabled is True
    if was_active_admin and loses_admin and count_active_admins(session) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot remove the last active admin")
    try:
        if body.password is not None:
            set_password(session, user, body.password)
    except AccountError as exc:
        raise _invalid(exc) from exc
    if body.role is not None:
        user.role = body.role
    if body.disabled is True and user.disabled_at is None:
        user.disabled_at = utcnow()
        end_sessions(session, user)
    elif body.disabled is False:
        user.disabled_at = None
    session.commit()
    return user_out(user)
