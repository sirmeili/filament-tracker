"""Validation errors that never repeat what was sent.

FastAPI's default 422 answer includes each rejected value, which may be a password, an
access code or a token. This one keeps only where the problem is and what is wrong.
"""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _problem(error: dict[str, Any]) -> dict[str, Any]:
    return {"type": error.get("type"), "loc": list(error.get("loc", ())), "msg": error.get("msg")}


async def validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - registered for this type
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": [_problem(error) for error in exc.errors()]},
    )
