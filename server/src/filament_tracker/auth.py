"""Bearer-token authentication (Security requirements in docs/SPEC.md).

Scanners use device tokens: random, shown once at registration, stored only as a SHA-256
hash and refused once revoked. The web UI and Home Assistant use the admin token from
settings. If no admin token is configured, every admin request is refused.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.api.deps import get_session
from filament_tracker.config import Settings
from filament_tracker.db.models import Device

TOKEN_PREFIX = "ftd_"  # noqa: S105 - a public marker on device tokens, not a secret

_bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


@dataclass(frozen=True)
class Caller:
    """Who made a request: the admin, or a registered scanner."""

    device: Device | None = None

    @property
    def is_admin(self) -> bool:
        return self.device is None


def new_device_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_admin(request: Request, token: str) -> bool:
    settings: Settings = request.app.state.settings
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


def require_admin(request: Request, credentials: Credentials) -> Caller:
    if credentials is None or not _is_admin(request, credentials.credentials):
        raise _unauthorized()
    return Caller()


def require_device(
    credentials: Credentials, session: Annotated[Session, Depends(get_session)]
) -> Device:
    device = _device_for(session, credentials.credentials) if credentials else None
    if device is None:
        raise _unauthorized()
    return device


def require_admin_or_device(
    request: Request,
    credentials: Credentials,
    session: Annotated[Session, Depends(get_session)],
) -> Caller:
    if credentials is None:
        raise _unauthorized()
    if _is_admin(request, credentials.credentials):
        return Caller()
    device = _device_for(session, credentials.credentials)
    if device is None:
        raise _unauthorized()
    return Caller(device)


AdminCaller = Annotated[Caller, Depends(require_admin)]
ScannerDevice = Annotated[Device, Depends(require_device)]
AnyCaller = Annotated[Caller, Depends(require_admin_or_device)]
