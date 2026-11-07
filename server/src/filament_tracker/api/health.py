from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def get_health(request: Request) -> dict[str, Any]:
    """Liveness, and the state of the Home Assistant links: MQTT (off, connecting,
    connected or disconnected) and events (off, ready or failing)."""
    link = getattr(request.app.state, "home_assistant", None)
    publisher = link.publisher if link is not None else None
    sender = link.sender if link is not None else None
    return {
        "status": "ok",
        "home_assistant": {
            "mqtt": publisher.status.value if publisher is not None else "off",
            "events": sender.status.value if sender is not None else "off",
        },
    }
