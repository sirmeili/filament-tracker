"""The image end to end, in the Compose test stack (Testing in docs/SPEC.md): first-start
setup, the scan simulator driving Received, Opened and Empty, Home Assistant entities
updating on the broker, a backup, and a restart that keeps the data.

Runs only when FT_COMPOSE_STACK is set (CI's image job sets it), with the image named by
ROLLCALL_IMAGE (default `rollcall:test`); build it first with `docker build -t rollcall:test .`
from the repository root. Docker must be running.
"""

import asyncio
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import aiomqtt
import httpx
import pytest

from filament_tracker.ha.entities import TOTALS_TOPIC
from filament_tracker.simulator.cli import main as ft_sim

pytestmark = pytest.mark.skipif(
    not os.environ.get("FT_COMPOSE_STACK"), reason="set FT_COMPOSE_STACK to run the image"
)

COMPOSE_FILE = Path(__file__).parents[3] / "deploy" / "test" / "compose.yaml"
PORT = int(os.environ.get("TEST_PORT", "18000"))
BROKER_PORT = int(os.environ.get("TEST_BROKER_PORT", "21883"))
SERVER = f"http://127.0.0.1:{PORT}"
API = f"{SERVER}/api/v1"
ADMIN = {"Authorization": "Bearer compose-test-admin-token-0123456789"}
CSRF = {"X-Requested-With": "filament-tracker"}
PASSWORD = "correct horse battery"  # noqa: S105 - test value
CODE = re.compile(r"setup code: ([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})")


def compose(*args: str, check: bool = True) -> str:
    result = subprocess.run(  # noqa: S603 - fixed arguments
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],  # noqa: S607 - docker on PATH
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"docker compose {args[0]} failed:\n{result.stderr[-2000:]}")
    return result.stdout + result.stderr


def logs() -> str:
    return compose("logs", "--no-color", "rollcall")


@pytest.fixture(scope="module")
def stack() -> Iterator[None]:
    compose("down", "--volumes", check=False)
    compose("up", "--detach", "--wait", "--wait-timeout", "120")
    try:
        yield
    finally:
        compose("down", "--volumes", check=False)


def totals(done: Callable[[dict], bool]) -> dict:
    """The retained totals Home Assistant would read, once `done` holds (or after 15 s)."""

    async def read() -> dict:
        latest: dict = {}
        async with aiomqtt.Client("127.0.0.1", BROKER_PORT, timeout=10) as client:
            await client.subscribe(TOTALS_TOPIC)
            try:
                async with asyncio.timeout(15):
                    async for message in client.messages:
                        latest = json.loads(bytes(message.payload).decode())  # type: ignore[arg-type]
                        if done(latest):
                            break
            except TimeoutError:
                pass
        return latest

    loop = asyncio.SelectorEventLoop()  # aiomqtt needs a selector loop on Windows
    try:
        return loop.run_until_complete(read())
    finally:
        loop.close()


def test_the_image_end_to_end(stack: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    http = httpx.Client(timeout=10)

    # Health, and the setup code in the log.
    health = http.get(f"{API}/health").json()
    assert health["status"] == "ok"
    codes = CODE.findall(logs())
    assert len(codes) == 1
    assert http.get(f"{API}/setup").json()["open"] is True

    # First-start setup creates the Admin and signs them in.
    body = {"code": codes[0], "username": "frank", "password": PASSWORD}
    made = http.post(f"{API}/setup", json=body, headers=CSRF)
    assert made.status_code == 201, made.text
    assert made.json()["time_zone"] == "America/Chicago"
    assert http.get(f"{API}/auth/me").json()["username"] == "frank"
    assert http.get(f"{API}/setup").json()["open"] is False

    # A scanner, and the simulator driving one spool through its life.
    device = http.post(
        f"{API}/devices", json={"id": "compose-sim", "name": "Compose test"}, headers=ADMIN
    )
    assert device.status_code == 201, device.text
    monkeypatch.setenv("FT_TOKEN", device.json()["token"])
    monkeypatch.setenv("FT_DEVICE_ID", "compose-sim")
    dump = tmp_path / "spool.bin"
    assert ft_sim(["generate", str(dump)]) == 0

    expected = [
        ("received", {"spools": 1, "sealed": 1, "open": 0}),
        ("opened", {"spools": 1, "sealed": 0, "open": 1}),
        ("empty", {"sealed": 0, "open": 0}),
    ]
    for action, counts in expected:
        assert ft_sim(["scan", str(dump), "--action", action, "--server", SERVER]) == 0

        def matches(latest: dict, counts: dict = counts) -> bool:
            return all(latest.get(key) == value for key, value in counts.items())

        assert matches(totals(matches)), f"Home Assistant totals after {action}"

    # A backup on demand lands in the backup volume.
    out = compose("exec", "-T", "rollcall", "ft-admin", "backup")
    assert "backup written: /backups/filament-" in out

    # A restart keeps the data and does not reopen setup.
    compose("restart", "rollcall")
    compose("up", "--detach", "--wait", "--wait-timeout", "120")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if http.get(f"{API}/health").status_code == 200:
                break
        except httpx.TransportError:
            pass
        time.sleep(1)
    assert len(CODE.findall(logs())) == 1  # only the first start's
    assert http.get(f"{API}/setup").json()["open"] is False
    spools = http.get(f"{API}/spools", headers=ADMIN).json()
    assert spools["total"] == 1
    assert spools["items"][0]["state"] == "empty"
