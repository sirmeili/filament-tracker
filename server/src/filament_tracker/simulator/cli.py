"""ft-sim: the command-line scan simulator.

    ft-sim generate black-pla.bin [--color 000000FF ...]
    ft-sim scan black-pla.bin --action received
    ft-sim scan C:\\tag-dumps\\*.zip --action lookup
    ft-sim check-salt C:\\tag-dumps\\*.zip

The server, token and device ID come from options or from the FT_SERVER, FT_TOKEN and
FT_DEVICE_ID environment variables. Output never includes tag or tray UIDs.
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from filament_tracker.app_settings.offline import open_store
from filament_tracker.config import Settings
from filament_tracker.decoder.keys import SECTORS, matching_keys
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.simulator.client import Transport, http_transport, post_scan, scan_payload
from filament_tracker.simulator.dumps import DumpError, load_dump, load_image

ACTIONS = ["lookup", "received", "opened", "empty"]
DEFAULT_SERVER = "http://localhost:8000"
# BambuTagScanner names files "<tag UID>-<type>-<color>.bin"; the UID is masked in output.
_UID_PREFIX = re.compile(r"^[0-9A-Fa-f]{8}(?=[-_.])")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ft-sim", description="RollCall scan simulator")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="send tag dumps to the server as scans")
    scan.add_argument("dumps", nargs="+", type=Path, help=".bin images or BambuTagScanner ZIPs")
    scan.add_argument("--action", choices=ACTIONS, default="lookup")
    scan.add_argument("--server", default=os.environ.get("FT_SERVER", DEFAULT_SERVER))
    scan.add_argument("--token", default=os.environ.get("FT_TOKEN"), help="or set FT_TOKEN")
    scan.add_argument("--device-id", default=os.environ.get("FT_DEVICE_ID", "simulator"))
    scan.add_argument(
        "--at", type=datetime.fromisoformat, help="scan time, e.g. 2026-11-01T09:00:00+00:00"
    )
    scan.add_argument("--event-id", type=UUID, help="reuse an event ID to test retries")
    scan.add_argument("--json", action="store_true", help="print the full server response")

    generate = commands.add_parser("generate", help="write a synthetic tag image")
    generate.add_argument("output", type=Path)
    generate.add_argument("--material-id", default="GFA00")
    generate.add_argument("--variant-id", default="A00-K00")
    generate.add_argument("--type", dest="filament_type", default="PLA")
    generate.add_argument("--detailed-type", default="PLA Basic")
    generate.add_argument("--color", default="000000FF", help="RGBA hex")
    generate.add_argument("--force", action="store_true", help="overwrite an existing file")

    salt = commands.add_parser(
        "check-salt", help="check BAMBU_KDF_SALT against the keys in saved dumps"
    )
    salt.add_argument("dumps", nargs="+", type=Path, help=".bin images or BambuTagScanner ZIPs")
    return parser


def main(
    argv: Sequence[str] | None = None,
    transport: Transport = http_transport,
    settings: Settings | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return _generate(args)
    if args.command == "check-salt":
        return _check_salt(args, settings or Settings())
    return _scan(args, transport)


def _check_salt(args: argparse.Namespace, settings: Settings) -> int:
    """Say whether the salt the server uses (saved in the app, else BAMBU_KDF_SALT in
    server/.env) reproduces each dump's keys. Prints no keys, UIDs or names."""
    store, _ = open_store(settings)
    current = store.current("bambu_kdf_salt")
    if current.value is None:
        if current.unreadable:
            print("The salt saved in the app can't be read without its key.", file=sys.stderr)
        else:
            print(
                "Set the salt first: Settings > Scanners, or BAMBU_KDF_SALT in server/.env.",
                file=sys.stderr,
            )
        return 2
    salt = bytes.fromhex(current.value)
    all_match = True
    for number, path in enumerate(_expand(args.dumps), start=1):
        try:
            _, image = load_image(path)
        except DumpError as exc:
            print(f"dump {number}: cannot read: {exc}", file=sys.stderr)
            all_match = False
            continue
        matched = matching_keys(image, salt)
        all_match = all_match and matched == SECTORS
        print(f"dump {number}: {matched} of {SECTORS} sector keys match")
    print("BAMBU_KDF_SALT is correct." if all_match else "BAMBU_KDF_SALT does not match.")
    return 0 if all_match else 1


def _generate(args: argparse.Namespace) -> int:
    if args.output.exists() and not args.force:
        print(f"{args.output} exists; use --force to overwrite", file=sys.stderr)
        return 2
    try:
        tag = SyntheticTag(
            material_id=args.material_id,
            variant_id=args.variant_id,
            filament_type=args.filament_type,
            detailed_filament_type=args.detailed_type,
            color_rgba=args.color.upper(),
        )
        image = tag.image()
    except ValueError as exc:
        print(f"cannot generate: {exc}", file=sys.stderr)
        return 2
    args.output.write_bytes(image)
    print(f"wrote {args.output} ({args.detailed_type} {args.color.upper()})")
    return 0


def _scan(args: argparse.Namespace, transport: Transport) -> int:
    if not args.token:
        print("a device token is needed: use --token or set FT_TOKEN", file=sys.stderr)
        return 2
    if args.at is not None and args.at.tzinfo is None:
        print("--at needs a timezone, e.g. 2026-11-01T09:00:00+00:00", file=sys.stderr)
        return 2
    if args.event_id is not None and len(args.dumps) > 1:
        print("--event-id can only be used with one dump", file=sys.stderr)
        return 2

    failures = 0
    for path in _expand(args.dumps):
        if _is_pattern(path) and not path.exists():
            print(f"{_label(path.name)}: no files match", file=sys.stderr)
            failures += 1
            continue
        try:
            dump = load_dump(path)
        except DumpError as exc:
            print(f"{_label(path.name)}: {exc}", file=sys.stderr)
            failures += 1
            continue
        payload = scan_payload(
            dump, args.action, args.device_id, event_id=args.event_id, scanned_at=args.at
        )
        try:
            status, body = post_scan(args.server, args.token, payload, transport)
        except (OSError, ValueError) as exc:
            print(f"{_label(dump.name)}: cannot reach the server: {exc}", file=sys.stderr)
            return 1
        if status != 200:
            print(f"{_label(dump.name)}: HTTP {status} {body.get('detail', '')}", file=sys.stderr)
            failures += 1
            continue
        print(json.dumps(body, indent=2) if args.json else _summary(_label(dump.name), body))
    return 1 if failures else 0


def _label(name: str) -> str:
    return _UID_PREFIX.sub("********", name)


def _is_pattern(path: Path) -> bool:
    return any(ch in path.name for ch in "*?[")


def _expand(paths: list[Path]) -> list[Path]:
    """Expand wildcards ourselves, because PowerShell passes them through unexpanded."""
    expanded: list[Path] = []
    for path in paths:
        if _is_pattern(path) and not path.exists():
            expanded.extend(sorted(path.parent.glob(path.name)) or [path])
        else:
            expanded.append(path)
    return expanded


def _summary(name: str, body: dict[str, Any]) -> str:
    product = body.get("product") or {}
    actions = " / ".join(a or "-" for a in body.get("actions", []))
    note = " (manual placeholder)" if body.get("placeholder") else ""
    spool = body.get("spool")
    spool_label = f"spool {spool['id']}" if spool else "new spool"
    return (
        f"{name}: {body['feedback']} | {product.get('display_name', 'unknown product')} | "
        f"{spool_label} | {body['state']}{note} | keys: {actions} | "
        f"suggested: {body.get('suggested') or '-'}"
    )
