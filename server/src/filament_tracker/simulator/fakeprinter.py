"""ft-fakeprinter: play a Bambu printer on an MQTT broker, for testing the printer link.

A real printer is its own MQTT broker. Here a Mosquitto container stands in for the
broker (see server/fakeprinter/) and this command is the printer: it publishes report
messages from files to `device/{serial}/report`, and answers every `pushall` on
`device/{serial}/request` with the full report.

    ft-fakeprinter --serial FAKE01 --report pushall.json --then remain-delta.json

The access code is read from FT_ACCESS_CODE, never from the command line.
"""

import argparse
import asyncio
import json
import logging
import os
import ssl
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import aiomqtt

logger = logging.getLogger(__name__)

ACCESS_CODE_ENV = "FT_ACCESS_CODE"


def is_pushall(payload: object) -> bool:
    if isinstance(payload, bytes | bytearray):
        payload = bytes(payload).decode("utf-8", errors="replace")
    if not isinstance(payload, str):
        return False
    try:
        message = json.loads(payload)
    except ValueError:
        return False
    pushing = message.get("pushing") if isinstance(message, dict) else None
    return isinstance(pushing, dict) and pushing.get("command") == "pushall"


def _test_broker_tls() -> ssl.SSLContext:
    # The fake broker has a throwaway self-signed certificate; this is a test tool.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class FakePrinter:
    def __init__(
        self,
        serial: str,
        full_report: str,
        changes: Sequence[str] = (),
        *,
        interval: float = 5.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.serial = serial
        self.full_report = full_report
        self.changes = list(changes)
        self.interval = interval
        self._sleep = sleep

    @property
    def report_topic(self) -> str:
        return f"device/{self.serial}/report"

    @property
    def request_topic(self) -> str:
        return f"device/{self.serial}/request"

    async def play(self, client: Any) -> None:
        """Publish the full report, then each change, answering pushall throughout."""
        await client.subscribe(self.request_topic)
        await client.publish(self.report_topic, self.full_report)
        answering = asyncio.create_task(self._answer(client))
        try:
            for change in self.changes:
                await self._sleep(self.interval)
                await client.publish(self.report_topic, change)
                logger.info("published a change")
            await answering
        finally:
            answering.cancel()

    async def _answer(self, client: Any) -> None:
        async for message in client.messages:
            if is_pushall(message.payload):
                await client.publish(self.report_topic, self.full_report)
                logger.info("answered pushall")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ft-fakeprinter", description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--report", type=Path, required=True, help="the full report (JSON)")
    parser.add_argument("--then", type=Path, nargs="*", default=[], help="changes to send")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between changes")
    return parser


def _read_json(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    json.loads(text)  # fail early on a broken file
    return text


async def _run(args: argparse.Namespace, access_code: str) -> None:
    printer = FakePrinter(
        args.serial,
        _read_json(args.report),
        [_read_json(p) for p in args.then],
        interval=args.interval,
    )
    async with aiomqtt.Client(
        hostname=args.host,
        port=args.port,
        username="bblp",
        password=access_code,
        tls_context=_test_broker_tls(),
        tls_insecure=True,
    ) as client:
        logger.info("playing printer %s on %s:%s", args.serial, args.host, args.port)
        await printer.play(client)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    access_code = os.environ.get(ACCESS_CODE_ENV)
    if not access_code:
        print(f"Set {ACCESS_CODE_ENV} to the broker's access code.", file=sys.stderr)
        return 2
    try:
        files = [args.report, *args.then]
        for path in files:
            _read_json(path)
    except (OSError, ValueError) as error:
        print(f"Cannot read a report file: {error}", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        asyncio.run(_run(args, access_code), loop_factory=asyncio.SelectorEventLoop)
    except KeyboardInterrupt:
        return 0
    except aiomqtt.MqttError as error:
        print(f"Cannot reach the broker: {error}", file=sys.stderr)
        return 1
    return 0
