"""Request and response bodies for sign-in, the current user and user management."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from filament_tracker.api.schemas import Strict
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import MAX_PASSWORD

# Length limits here only stop absurd input; the password rules are checked by the service
# so they give one clear message.
Username = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Password = Annotated[str, StringConstraints(min_length=1, max_length=MAX_PASSWORD)]


class LoginRequest(Strict):
    username: Username
    password: Password


class PasswordChange(Strict):
    current_password: Password
    new_password: Password


class Me(BaseModel):
    id: int
    username: str
    role: Role


class UserOut(Me):
    disabled: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(Strict):
    username: Username
    password: Password
    role: Role


class UserUpdate(Strict):
    role: Role | None = None
    disabled: bool | None = None
    password: Password | None = None
