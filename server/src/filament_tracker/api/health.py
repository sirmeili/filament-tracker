from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def get_health(request: Request) -> dict[str, Any]:
    """Liveness, and whether the Home Assistant MQTT link is off, connected or not."""
    publisher = getattr(request.app.state, "home_assistant", None)
    mqtt = publisher.status.value if publisher is not None else "off"
    return {"status": "ok", "home_assistant": {"mqtt": mqtt}}
