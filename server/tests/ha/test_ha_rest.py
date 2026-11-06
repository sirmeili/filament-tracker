import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from filament_tracker.config import Settings
from filament_tracker.ha.rest import HaRest, HaRestError, Problem, ha_rest, parse_ha_url

TOKEN = SecretStr("ha-long-lived-token")


class Recorder(BaseHTTPRequestHandler):
    """A tiny Home Assistant: answers by path, and records what it was sent."""

    seen: list[dict[str, Any]] = []
    answers: dict[str, tuple[int, bytes, dict[str, str]]] = {}

    def _answer(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        Recorder.seen.append(
            {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "body": self.rfile.read(length) if length else b"",
            }
        )
        status, body, headers = Recorder.answers.get(self.path, (404, b"", {}))
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _answer

    def log_message(self, *args: object) -> None:
        return None


@pytest.fixture
def server() -> Iterator[str]:
    Recorder.seen = []
    Recorder.answers = {}
    httpd = HTTPServer(("127.0.0.1", 0), Recorder)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_fires_an_event_with_the_token(server: str) -> None:
    Recorder.answers["/api/events/filament_tracker_low_stock"] = (
        200,
        b'{"message": "Event filament_tracker_low_stock fired."}',
        {},
    )

    HaRest(server + "/", TOKEN).fire("filament_tracker_low_stock", {"product": "Black PLA"})

    [request] = Recorder.seen
    assert request["method"] == "POST"
    assert request["path"] == "/api/events/filament_tracker_low_stock"
    assert request["auth"] == f"Bearer {TOKEN.get_secret_value()}"
    assert json.loads(request["body"]) == {"product": "Black PLA"}


def test_check_reads_the_api_root(server: str) -> None:
    Recorder.answers["/api/"] = (200, b'{"message": "API running."}', {})
    HaRest(server, TOKEN).check()
    assert Recorder.seen[0]["method"] == "GET" and Recorder.seen[0]["path"] == "/api/"


def test_a_success_that_is_not_json_still_counts(server: str) -> None:
    Recorder.answers["/api/events/x"] = (200, b"ok", {})
    HaRest(server, TOKEN).fire("x", {})


@pytest.mark.parametrize(
    ("status", "problem"),
    [(401, Problem.REFUSED), (403, Problem.REFUSED), (500, Problem.ERROR), (404, Problem.ERROR)],
)
def test_errors_name_the_problem_not_the_token(server: str, status: int, problem: Problem) -> None:
    Recorder.answers["/api/"] = (status, b"", {})

    with pytest.raises(HaRestError) as error:
        HaRest(server, TOKEN).check()

    assert error.value.problem is problem and error.value.status == status
    assert TOKEN.get_secret_value() not in str(error.value)


def test_redirects_are_not_followed(server: str) -> None:
    # A redirect elsewhere would carry the token; it is an error instead.
    Recorder.answers["/api/"] = (302, b"", {"Location": server + "/stolen"})

    with pytest.raises(HaRestError) as error:
        HaRest(server, TOKEN).check()

    assert error.value.status == 302
    assert [r["path"] for r in Recorder.seen] == ["/api/"]


def test_an_address_that_does_not_answer() -> None:
    with pytest.raises(HaRestError) as error:
        HaRest("http://127.0.0.1:1", TOKEN).check()
    assert error.value.problem is Problem.UNREACHABLE
    assert str(error.value) == "unreachable"


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("ftp://ha", "http:// or https://"),
        ("homeassistant.local:8123", "http:// or https://"),
        ("http://me:secret@ha", "HA_TOKEN"),
        ("http://", "needs a host"),
        ("http://ha?x=1", r"\? or #"),
        ("http://ha:99999", "must look like"),
    ],
)
def test_bad_addresses_are_refused_without_repeating_them(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        parse_ha_url(url)
    assert "secret" not in str(error.value)


def test_addresses_lose_their_trailing_slash() -> None:
    assert parse_ha_url("http://homeassistant.local:8123/") == "http://homeassistant.local:8123"
    assert HaRest("https://ha.example.com/", TOKEN).url == "https://ha.example.com"
    with pytest.raises(ValueError):
        HaRest("file:///etc/passwd", TOKEN)


def test_needs_both_the_address_and_the_token() -> None:
    assert ha_rest(SimpleNamespace(ha_url=None, ha_token=TOKEN)) is None
    assert ha_rest(SimpleNamespace(ha_url="http://ha", ha_token=None)) is None
    rest = ha_rest(SimpleNamespace(ha_url="http://ha", ha_token=TOKEN))
    assert rest is not None and rest.url == "http://ha"


def test_settings_read_home_assistant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HA_URL", " http://homeassistant.local:8123/ ")
    monkeypatch.setenv("HA_TOKEN", f" {TOKEN.get_secret_value()} ")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.ha_url == "http://homeassistant.local:8123"
    assert settings.ha_token == TOKEN
    assert TOKEN.get_secret_value() not in repr(settings)


def test_blank_settings_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HA_URL", " ")
    monkeypatch.setenv("HA_TOKEN", " ")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.ha_url is None and settings.ha_token is None


def test_a_bad_address_setting_is_refused_without_echoing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HA_URL", "http://me:hunter2@ha")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "hunter2" not in str(error.value)
