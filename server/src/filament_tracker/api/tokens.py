"""Machine tokens for Home Assistant and scripts (Admin role), made on the Settings page.

Each token has a name and a role, is returned once when made and is stored only as a hash.
Revoking one refuses it at once; it stays listed, with when it was last used.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from filament_tracker.api.schemas import Strict
from filament_tracker.auth import Admin, DbSession, Principal, hash_token, new_machine_token
from filament_tracker.db.models import MachineToken
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tokens"])

TokenName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TokenCreate(Strict):
    name: TokenName
    role: Role


class TokenOut(BaseModel):
    id: int
    name: str
    role: Role
    created_at: datetime
    created_by: str | None = Field(description="The username of the admin who made it")
    last_used_at: datetime | None
    revoked: bool


class TokenCreated(TokenOut):
    token: str = Field(description="Shown once; only a hash is stored.")


def _out(token: MachineToken) -> TokenOut:
    return TokenOut(
        id=token.id,
        name=token.name,
        role=token.role,
        created_at=token.created_at,
        created_by=token.creator.username if token.creator else None,
        last_used_at=token.last_used_at,
        revoked=token.revoked_at is not None,
    )


def _who(caller: Principal) -> str:
    return f"user {caller.user.id}" if caller.user is not None else "a token"


@router.get("/tokens", response_model=list[TokenOut])
def list_tokens(_: Admin, session: DbSession) -> list[TokenOut]:
    """Tokens in use first, then revoked ones; newest first within each."""
    tokens = session.scalars(
        select(MachineToken).order_by(MachineToken.revoked_at.is_not(None), MachineToken.id.desc())
    )
    return [_out(token) for token in tokens]


@router.post("/tokens", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(body: TokenCreate, caller: Admin, session: DbSession) -> TokenCreated:
    """Make a token. It is returned once and only its hash is stored."""
    plain = new_machine_token()
    token = MachineToken(
        name=body.name,
        role=body.role,
        token_hash=hash_token(plain),
        created_by=caller.user.id if caller.user is not None else None,
    )
    session.add(token)
    session.commit()
    logger.info("machine token %s (%s) made by %s", token.id, token.role.value, _who(caller))
    return TokenCreated(**_out(token).model_dump(), token=plain)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, caller: Admin, session: DbSession) -> Response:
    """Revoke a token; it is refused from then on. It stays listed."""
    token = session.get(MachineToken, token_id)
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such token")
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        session.commit()
        logger.info("machine token %s revoked by %s", token.id, _who(caller))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
