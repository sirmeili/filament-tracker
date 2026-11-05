"""Who is calling, and what they may do (Users and roles, Security in docs/SPEC.md).

Three kinds of caller:

- A web app user, signed in with the `ft_session` cookie. Their role decides what they
  may do. Requests that change something must also send `X-Requested-With:
  filament-tracker`, which a page on another site cannot add.
- A scanner, with a device token: random, shown once at registration, stored only as a
  SHA-256 hash and refused once revoked.
- Home Assistant or a script, with `ADMIN_TOKEN`; it acts as an Admin. If no admin token
  is configured, it is refused.

Bearer tokens (device and admin) are accepted only from `TRUSTED_NETWORKS`.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.config import Settings
from filament_tracker.db.models import Device, User, UserSession
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.net import is_trusted
from filament_tracker.services.accounts import find_session

TOKEN_PREFIX = "ftd_"  # noqa: S105 - a public marker on device tokens, not a secret
SESSION_COOKIE = "ft_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "filament-tracker"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
DbSession = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class Principal:
    """The caller: a signed-in user, a scanner, or the admin token (neither)."""

    user: User | None = None
    session: UserSession | None = None
    device: Device | None = None

    @property
    def role(self) -> Role | None:
        """The caller's role; scanners have none."""
        if self.user is not None:
            return self.user.role
        return None if self.device is not None else Role.ADMIN


def new_device_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def unauthorized(detail: str = "Not signed in or invalid token") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def forbidden(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def check_csrf(request: Request) -> None:
    """Refuse a state-changing cookie request that lacks the app's header."""
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise forbidden(f"missing {CSRF_HEADER} header")


def _is_admin_token(settings: Settings, token: str) -> bool:
    if settings.admin_token is None:
        return False
    expected = settings.admin_token.get_secret_value()
    return bool(expected) and hmac.compare_digest(token.encode(), expected.encode())


def _device_for(session: Session, token: str) -> Device | None:
    if not token.startswith(TOKEN_PREFIX):
        return None
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    if device is None or device.revoked_at is not None:
        return None
    return device


def _from_bearer(request: Request, session: Session, token: str) -> Principal:
    settings = settings_of(request)
    if not is_trusted(request, settings):
        raise forbidden("tokens are accepted only from the local network")
    if _is_admin_token(settings, token):
        return Principal()
    device = _device_for(session, token)
    if device is None:
        raise unauthorized()
    return Principal(device=device)


def current_session(request: Request, session: Session) -> UserSession | None:
    """The live session for the request's cookie, if any."""
    token = request.cookies.get(SESSION_COOKIE)
    return find_session(session, token, utcnow()) if token else None


def get_principal(request: Request, credentials: Credentials, session: DbSession) -> Principal:
    if credentials is not None:
        return _from_bearer(request, session, credentials.credentials)
    user_session = current_session(request, session)
    if user_session is None:
        raise unauthorized()
    check_csrf(request)
    return Principal(user=user_session.user, session=user_session)


AnyPrincipal = Annotated[Principal, Depends(get_principal)]


def require_role(needed: Role, *, allow_device: bool = False) -> Callable[..., Principal]:
    """A dependency that admits callers whose role allows `needed`, and scanners if
    `allow_device` is set (the route then decides what a scanner may touch)."""

    def dependency(principal: AnyPrincipal) -> Principal:
        if principal.device is not None:
            if allow_device:
                return principal
            raise forbidden("scanners cannot use this endpoint")
        role = principal.role
        if role is None or not role.allows(needed):
            raise forbidden(f"requires the {needed.value} role")
        return principal

    return dependency


def require_user(principal: AnyPrincipal) -> Principal:
    """A signed-in web app user (not a token)."""
    if principal.user is None:
        raise forbidden("only signed-in users can use this endpoint")
    return principal


def require_device(request: Request, credentials: Credentials, session: DbSession) -> Device:
    if credentials is None:
        raise unauthorized()
    principal = _from_bearer(request, session, credentials.credentials)
    if principal.device is None:
        raise forbidden("only scanners can use this endpoint")
    return principal.device


Viewer = Annotated[Principal, Depends(require_role(Role.VIEWER))]
Editor = Annotated[Principal, Depends(require_role(Role.EDITOR))]
Admin = Annotated[Principal, Depends(require_role(Role.ADMIN))]
EditorOrScanner = Annotated[Principal, Depends(require_role(Role.EDITOR, allow_device=True))]
SignedInUser = Annotated[Principal, Depends(require_user)]
ScannerDevice = Annotated[Device, Depends(require_device)]
