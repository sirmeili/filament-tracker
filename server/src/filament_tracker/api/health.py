from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def get_health(request: Request) -> dict[str, Any]:
    """Liveness, and the state of the Home Assistant links: MQTT (off, connecting,
    connected or disconnected) and events (off, ready or failing)."""
    state = request.app.state
    publisher = getattr(state, "home_assistant", None)
    sender = getattr(state, "ha_events", None)
    return {
        "status": "ok",
        "home_assistant": {
            "mqtt": publisher.status.value if publisher is not None else "off",
            "events": sender.status.value if sender is not None else "off",
        },
    }
