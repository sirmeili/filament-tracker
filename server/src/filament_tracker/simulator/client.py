"""Send scan events to the server, as a scanner would."""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from filament_tracker.simulator.dumps import Dump

Response = tuple[int, dict[str, Any]]
Transport = Callable[[str, dict[str, Any], dict[str, str]], Response]

FW_VERSION = "simulator"
TIMEOUT_S = 10


def scan_payload(
    dump: Dump,
    action: str,
    device_id: str,
    *,
    event_id: UUID | None = None,
    scanned_at: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": str(event_id or uuid4()),
        "device_id": device_id,
        "action": action,
        "tag_uid": dump.tag_uid,
        "blocks": dump.blocks,
        "read_ok": True,
        "fw_version": FW_VERSION,
    }
    if scanned_at is not None:
        payload["scanned_at"] = scanned_at.isoformat()
    return payload


def http_transport(url: str, body: dict[str, Any], headers: dict[str, str]) -> Response:
    """POST JSON with the standard library; return the status and the JSON body."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("the server URL must start with http:// or https://")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except ValueError:
            detail = {}
        return exc.code, detail


def post_scan(
    server: str, token: str, payload: dict[str, Any], transport: Transport = http_transport
) -> Response:
    url = server.rstrip("/") + "/api/v1/scans"
    return transport(url, payload, {"Authorization": f"Bearer {token}"})
