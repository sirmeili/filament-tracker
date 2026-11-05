import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from filament_tracker.config import Settings
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.main import create_app
from filament_tracker.simulator.cli import main
from filament_tracker.simulator.client import Response

ADMIN = "sim-admin-token-0123456789abcdef"
SERVER = "http://testserver"


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=db_url, admin_token=ADMIN, _env_file=None))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/devices",
        json={"id": "simulator", "name": "Simulator"},
        headers={"Authorization": f"Bearer {ADMIN}"},
    )
    return response.json()["token"]


@pytest.fixture
def transport(client: TestClient):
    def send(url: str, body: dict[str, Any], headers: dict[str, str]) -> Response:
        response = client.post(url, json=body, headers=headers)
        return response.status_code, response.json()

    return send


def _sim(transport, token: str, *args: str) -> int:
    return main(["scan", *args, "--server", SERVER, "--token", token], transport)


def _tag_file(path: Path, **fields: Any) -> Path:
    path.write_bytes(SyntheticTag(**fields).image())
    return path


def test_a_spool_lifecycle_through_the_simulator(
    tmp_path: Path, token: str, transport, capsys: pytest.CaptureFixture[str]
) -> None:
    tag = _tag_file(tmp_path / "black.bin")

    for action in ("lookup", "received", "opened", "empty"):
        assert _sim(transport, token, str(tag), "--action", action) == 0

    lines = capsys.readouterr().out.splitlines()
    assert "ok | PLA Basic #000000 | new spool | unknown" in lines[0]
    assert "suggested: received" in lines[0]
    assert "| spool 1 | sealed |" in lines[1]
    assert "| open |" in lines[2]
    assert "| empty |" in lines[3]


def test_several_dumps_in_one_command(tmp_path: Path, token: str, transport, capsys) -> None:
    files = [str(_tag_file(tmp_path / f"roll{n}.bin")) for n in range(3)]

    assert _sim(transport, token, *files, "--action", "received") == 0

    out = capsys.readouterr().out
    assert out.count("| sealed |") == 3
    assert all(f"spool {n} |" in out for n in (1, 2, 3))


def test_wildcards_are_expanded(tmp_path: Path, token: str, transport, capsys) -> None:
    for n in range(2):
        _tag_file(tmp_path / f"roll{n}.bin")

    assert _sim(transport, token, str(tmp_path / "*.bin")) == 0

    assert len(capsys.readouterr().out.splitlines()) == 2


def test_a_wildcard_that_matches_nothing_says_so(
    tmp_path: Path, token: str, transport, capsys
) -> None:
    assert _sim(transport, token, str(tmp_path / "*.zip")) == 1

    assert "*.zip: no files match" in capsys.readouterr().err


def test_json_output_and_retries(tmp_path: Path, token: str, transport, capsys) -> None:
    tag = str(_tag_file(tmp_path / "t.bin"))
    event_id = str(uuid4())

    _sim(transport, token, tag, "--action", "opened", "--event-id", event_id, "--json")
    first = capsys.readouterr().out
    _sim(transport, token, tag, "--action", "opened", "--event-id", event_id, "--json")
    second = capsys.readouterr().out

    assert json.loads(first)["feedback"] == "ok_created"
    assert second == first


def test_scan_time_is_sent(tmp_path: Path, token: str, transport, capsys) -> None:
    tag = str(_tag_file(tmp_path / "t.bin"))

    _sim(
        transport, token, tag, "--action", "received", "--at", "2026-10-01T09:00:00+00:00", "--json"
    )

    assert json.loads(capsys.readouterr().out)["spool"]["received_at"].startswith("2026-10-01")


def test_tag_uids_in_file_names_are_masked(tmp_path: Path, token: str, transport, capsys) -> None:
    tag = SyntheticTag()
    uid = tag.tag_uid.hex().upper()
    path = tmp_path / f"{uid}-PLA_Basic-Black.bin"
    path.write_bytes(tag.image())
    (tmp_path / f"{uid}-broken.bin").write_bytes(b"short")

    _sim(transport, token, str(path), str(tmp_path / f"{uid}-broken.bin"))

    captured = capsys.readouterr()
    assert uid not in captured.out + captured.err
    assert "********-PLA_Basic-Black.bin" in captured.out


def test_server_errors_are_reported(tmp_path: Path, transport, capsys) -> None:
    tag = str(_tag_file(tmp_path / "t.bin"))

    assert _sim(transport, "ftd_wrong", tag) == 1

    assert "HTTP 401" in capsys.readouterr().err


def test_bad_files_are_reported_and_others_still_sent(
    tmp_path: Path, token: str, transport, capsys
) -> None:
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"nope")
    good = _tag_file(tmp_path / "good.bin")

    assert _sim(transport, token, str(bad), str(good)) == 1

    captured = capsys.readouterr()
    assert "bad.bin: must be a 1024-byte tag image" in captured.err
    assert "good.bin: ok" in captured.out


def test_unreachable_server(tmp_path: Path, token: str, capsys) -> None:
    def refuse(url: str, body: dict[str, Any], headers: dict[str, str]) -> Response:
        raise ConnectionRefusedError("refused")

    assert _sim(refuse, token, str(_tag_file(tmp_path / "t.bin"))) == 1
    assert "cannot reach the server" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ([], "device token is needed"),
        (["--token", "t", "--at", "2026-10-01T09:00:00"], "needs a timezone"),
        (["b.bin", "--token", "t", "--event-id", str(uuid4())], "only be used with one dump"),
    ],
)
def test_option_errors(
    monkeypatch: pytest.MonkeyPatch, capsys, extra: list[str], message: str
) -> None:
    monkeypatch.delenv("FT_TOKEN", raising=False)

    assert main(["scan", "a.bin", *extra]) == 2
    assert message in capsys.readouterr().err


def test_token_and_server_can_come_from_the_environment(
    tmp_path: Path, token: str, transport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FT_TOKEN", token)
    monkeypatch.setenv("FT_SERVER", SERVER)

    assert main(["scan", str(_tag_file(tmp_path / "t.bin"))], transport) == 0


# --- generate --------------------------------------------------------------------------


def test_generate_writes_a_tag_with_the_chosen_product(
    tmp_path: Path, token: str, transport, capsys
) -> None:
    out = tmp_path / "white.bin"

    assert main(["generate", str(out), "--color", "ffffffff", "--detailed-type", "PLA Matte"]) == 0
    assert len(out.read_bytes()) == 1024
    _sim(transport, token, str(out))

    assert "PLA Matte #FFFFFF" in capsys.readouterr().out


def test_generate_will_not_overwrite_without_force(tmp_path: Path, capsys) -> None:
    out = tmp_path / "t.bin"
    out.write_bytes(b"keep")

    assert main(["generate", str(out)]) == 2
    assert out.read_bytes() == b"keep"
    assert main(["generate", str(out), "--force"]) == 0
    assert len(out.read_bytes()) == 1024


def test_generate_rejects_values_that_do_not_fit(tmp_path: Path, capsys) -> None:
    assert main(["generate", str(tmp_path / "t.bin"), "--variant-id", "MUCH-TOO-LONG"]) == 2
    assert "cannot generate" in capsys.readouterr().err
