"""The standard-library HTTP client, against a tiny local server."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from filament_tracker.simulator.client import http_transport


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        auth = self.headers.get("Authorization", "")
        if self.path == "/broken":
            self._reply(500, b"not json")
        elif auth != "Bearer good":
            self._reply(401, json.dumps({"detail": "Missing or invalid token"}).encode())
        else:
            self._reply(
                200, json.dumps({"echo": body, "type": self.headers["Content-Type"]}).encode()
            )

    def _reply(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_posts_json_and_returns_the_reply(server: str) -> None:
    status, body = http_transport(f"{server}/scan", {"a": 1}, {"Authorization": "Bearer good"})

    assert status == 200
    assert body == {"echo": {"a": 1}, "type": "application/json"}


def test_http_errors_return_status_and_detail(server: str) -> None:
    status, body = http_transport(f"{server}/scan", {}, {"Authorization": "Bearer bad"})

    assert status == 401
    assert body["detail"] == "Missing or invalid token"


def test_non_json_error_bodies_are_tolerated(server: str) -> None:
    status, body = http_transport(f"{server}/broken", {}, {})

    assert (status, body) == (500, {})


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "localhost:8000"])
def test_only_http_urls_are_allowed(url: str) -> None:
    with pytest.raises(ValueError, match="http"):
        http_transport(url, {}, {})
