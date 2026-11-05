"""Shared request dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request; the route commits what it changes."""
    with request.app.state.session_factory() as session:
        yield session
