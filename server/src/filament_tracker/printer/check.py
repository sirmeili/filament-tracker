"""ft-printer check: connect to a real printer once and show what its AMS reports.

    ft-printer check --dump C:\\tag-dumps\\roll1.bin --save captures\\p1s.jsonl

It reads the printer from PRINTERS (in `.env`), pins the certificate it finds for this
connection only (the database is not touched), asks for a full report, and prints each
slot. With `--dump`, it says whether each tag's tray UID or tag UID is what a slot reports,
without printing either. `--save` writes the messages with every identifier replaced.

Run it while the server is stopped if the printer is near its MQTT connection limit.
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import secrets
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiomqtt

from filament_tracker.config import PrinterConfig, Settings
from filament_tracker.decoder.decode import DecodeError, decode
from filament_tracker.printer.link import MAX_PAYLOAD, PUSHALL, USERNAME
from filament_tracker.printer.report import AmsView, TrayReport, slot_name
from filament_tracker.printer.tls import fetch_fingerprint, pinned_context
from filament_tracker.simulator.dumps import DumpError, load_dump

# A saved capture keeps only these parts of a report; the rest (print jobs, network,
# camera, firmware) is dropped.
KEPT_SECTIONS = ("command", "ams", "vt_tray")
# Fields in the kept parts that identify a tag or a device. Their values never leave this
# tool unredacted.
SENSITIVE_KEYS = frozenset(
    {"tray_uuid", "tag_uid", "chip_id", "ams_id", "xcam_info", "sn", "serial", "dev_id"}
)
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


@dataclass(frozen=True)
class TagIds:
    label: str
    tag_uid: str
    tray_uid: str


@dataclass
class Capture:
    """Messages from one connection, and the raw fields of each tray as last reported."""

    messages: list[Any] = field(default_factory=list)
    view: AmsView = field(default_factory=AmsView)
    raw: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)

    def add(self, payload: object) -> None:
        if isinstance(payload, bytes | bytearray):
            payload = bytes(payload[: MAX_PAYLOAD + 1]).decode("utf-8", errors="replace")
        if not isinstance(payload, str) or len(payload) > MAX_PAYLOAD:
            return
        try:
            message = json.loads(payload)
        except ValueError:
            return
        self.messages.append(message)
        self.view.apply(message)
        self._merge_raw(message)

    def _merge_raw(self, message: Any) -> None:
        ams = message.get("print", {}).get("ams") if isinstance(message, dict) else None
        units = ams.get("ams") if isinstance(ams, dict) else None
        for unit in units if isinstance(units, list) else []:
            trays = unit.get("tray") if isinstance(unit, dict) else None
            for tray in trays if isinstance(trays, list) else []:
                if not isinstance(tray, dict):
                    continue
                ams_id, tray_id = str(unit.get("id", "")), str(tray.get("id", ""))
                if ams_id.isdigit() and tray_id.isdigit():
                    self.raw.setdefault((int(ams_id), int(tray_id)), {}).update(tray)


def load_tags(paths: Sequence[Path]) -> list[TagIds]:
    """Read each dump, labelled by its position and product, never by its file name."""
    tags: list[TagIds] = []
    for number, path in enumerate(paths, start=1):
        dump = load_dump(path)
        record = decode(dump.blocks)
        label = f"tag {number} ({record.detailed_filament_type}, {record.color_rgba})"
        tags.append(TagIds(label, record.tag_uid, record.tray_uid))
    return tags


def _id_state(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "missing"
    if not value.strip("0"):
        return "all zeros"
    return f"{len(value)} hex digits"


def describe(capture: Capture, tags: Sequence[TagIds]) -> list[str]:
    """What each slot reports and which tags match it. Identifiers are never printed."""
    lines: list[str] = []
    trays: list[TrayReport] = capture.view.trays()
    if not trays:
        return ["No AMS in the report."]
    for tray in trays:
        raw = capture.raw.get((tray.ams_index, tray.tray_index), {})
        where = slot_name(tray.ams_index, tray.tray_index)
        if not tray.loaded:
            lines.append(f"{where}: empty")
            continue
        lines.append(
            f"{where}: {tray.filament_type or '?'} / {tray.sub_brand or '-'} / "
            f"material {tray.material_id or '-'} / color {tray.color_rgba or '-'} / "
            f"remain {raw.get('remain', '-')} -> {_pct(tray.remaining_pct)}"
        )
        lines.append(
            f"    tray_uuid: {_id_state(raw.get('tray_uuid'))}; "
            f"tag_uid: {_id_state(raw.get('tag_uid'))}"
        )
        for tag in tags:
            tray_uuid = str(raw.get("tray_uuid", "")).upper()
            tag_uid = str(raw.get("tag_uid", "")).upper()
            if tray_uuid == tag.tray_uid:
                lines.append(f"    {tag.label}: tray_uuid equals the tag's tray UID")
            if tag_uid == tag.tag_uid:
                lines.append(f"    {tag.label}: tag_uid equals the tag's UID")
    for tag in tags:
        if not any(
            str(r.get("tray_uuid", "")).upper() == tag.tray_uid
            or str(r.get("tag_uid", "")).upper() == tag.tag_uid
            for r in capture.raw.values()
        ):
            lines.append(f"{tag.label}: matches no slot")
    return lines


def _pct(value: int | None) -> str:
    return "unknown" if value is None else f"{value}%"


def redact(value: Any, serial: str, key: bytes) -> Any:
    """Replace identifiers with keyed hashes: equal values stay equal within one capture,
    but nothing can be matched against anything outside it."""

    def token(text: str) -> str:
        return "redacted-" + hmac.new(key, text.encode(), hashlib.sha256).hexdigest()[:12]

    if isinstance(value, dict):
        return {
            k: token(str(v))
            if k in SENSITIVE_KEYS and v not in ("", None)
            else redact(v, serial, key)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, serial, key) for v in value]
    if isinstance(value, str):
        value = value.replace(serial, "SERIAL") if serial else value
        return IPV4.sub("192.0.2.0", value)
    return value


def save(capture: Capture, path: Path, serial: str) -> None:
    key = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for message in capture.messages:
            kept = keep(message)
            if kept is not None:
                out.write(json.dumps(redact(kept, serial, key)) + "\n")


def keep(message: Any) -> dict[str, Any] | None:
    """Only the AMS parts of a report message, or None if it has none."""
    report = message.get("print") if isinstance(message, dict) else None
    if not isinstance(report, dict):
        return None
    kept = {k: report[k] for k in KEPT_SECTIONS if k in report}
    return {"print": kept} if set(kept) - {"command"} else None


ClientFactory = Callable[..., Any]


async def collect(
    config: PrinterConfig,
    seconds: float,
    *,
    client_factory: ClientFactory = aiomqtt.Client,
    fetch: Callable[[str, int], str] = fetch_fingerprint,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[str, Capture]:
    """Pin the certificate, connect, send pushall and record reports for `seconds`."""
    pin = await asyncio.to_thread(fetch, config.host, config.port)
    capture = Capture()
    client = client_factory(
        hostname=config.host,
        port=config.port,
        username=USERNAME,
        password=config.access_code.get_secret_value(),
        identifier=f"filament-tracker-check-{secrets.token_hex(4)}",
        tls_context=pinned_context(pin),
        tls_insecure=True,
        keepalive=60,
        timeout=10,
    )
    async with client:
        await client.subscribe(f"device/{config.serial}/report")
        await client.publish(f"device/{config.serial}/request", json.dumps(PUSHALL))
        deadline = clock() + seconds

        async def read() -> None:
            async for message in client.messages:
                capture.add(message.payload)
                if clock() >= deadline:
                    return

        try:
            await asyncio.wait_for(read(), timeout=seconds)
        except TimeoutError:
            pass
    return pin, capture


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ft-printer", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="show what the AMS reports")
    check.add_argument("--name", help="the printer's name in PRINTERS (default: the first)")
    check.add_argument("--dump", type=Path, nargs="*", default=[], help="tag dumps to match")
    check.add_argument("--save", type=Path, help="write the redacted messages (JSON lines)")
    check.add_argument("--seconds", type=float, default=15.0, help="how long to listen")
    return parser


def _printer(settings: Settings, name: str | None) -> PrinterConfig | None:
    for printer in settings.printers:
        if name is None or printer.name == name:
            return printer
    return None


def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    args = _parser().parse_args(argv)
    config = _printer(settings or Settings(), args.name)
    if config is None:
        print("No such printer in PRINTERS (set it in server/.env).", file=sys.stderr)
        return 2
    try:
        tags = load_tags(args.dump)
    except (DumpError, DecodeError, OSError) as error:
        print(f"Cannot read a dump: {error}", file=sys.stderr)
        return 2
    try:
        pin, capture = asyncio.run(
            collect(config, args.seconds), loop_factory=asyncio.SelectorEventLoop
        )
    except (aiomqtt.MqttError, OSError) as error:
        print(f"Cannot connect to {config.name}: {error}", file=sys.stderr)
        return 1
    print(f"{config.name}: certificate {pin[:16]}..., {len(capture.messages)} messages")
    for line in describe(capture, tags):
        print(line)
    if args.save:
        save(capture, args.save, config.serial)
        print(f"Saved the redacted messages to {args.save}")
    return 0
