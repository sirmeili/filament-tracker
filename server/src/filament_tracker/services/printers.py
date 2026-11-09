"""Printers saved in the app (docs/SPEC.md, Settings and first start).

Each printer's access code is sealed with the settings key, bound to the printer's id, and
opened only to connect to it. PRINTERS in `.env` seeds each of its printers once, the first
time the server sees its serial; after that the app's copy is the one in use.
"""

import logging

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.app_settings.crypto import SecretBox, Unreadable
from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer, SeededPrinter

logger = logging.getLogger(__name__)


def _name(printer_id: int) -> str:
    """The associated data for a printer's access code: a sealed code moved to another
    printer's row cannot be opened."""
    return f"printer:{printer_id}:access_code"


def seal_access_code(box: SecretBox, printer: Printer, code: str) -> None:
    printer.access_code = box.seal(_name(printer.id), code)


def access_code(box: SecretBox, printer: Printer) -> SecretStr | None:
    """The plain access code, or None if not set or not readable with this key."""
    if not printer.access_code:
        return None
    try:
        return SecretStr(box.open(_name(printer.id), printer.access_code))
    except Unreadable:
        return None


def access_code_unreadable(box: SecretBox, printer: Printer) -> bool:
    return bool(printer.access_code) and access_code(box, printer) is None


def printer_config(box: SecretBox, printer: Printer) -> PrinterConfig | None:
    """What the link needs to connect, or None without a usable access code."""
    code = access_code(box, printer)
    if code is None:
        return None
    try:
        return PrinterConfig(
            name=printer.name,
            host=printer.host,
            port=printer.port,
            serial=printer.serial,
            access_code=code,
        )
    except ValidationError:
        logger.warning("printer %s: saved values are not usable; not connecting", printer.id)
        return None


def seed_printers(session: Session, box: SecretBox, configs: list[PrinterConfig]) -> int:
    """Add each printer in PRINTERS whose serial has not been seeded before. A printer
    already in the database (from before printers were edited in the app) takes the
    `.env` values. Returns how many were seeded."""
    seeded = set(session.scalars(select(SeededPrinter.serial)))
    count = 0
    for config in configs:
        if config.serial in seeded:
            continue
        printer = session.scalar(select(Printer).where(Printer.serial == config.serial))
        if printer is None:
            printer = Printer(serial=config.serial)
            session.add(printer)
        printer.name = config.name
        printer.host = config.host
        printer.port = config.port
        session.flush()
        seal_access_code(box, printer, config.access_code.get_secret_value())
        session.add(SeededPrinter(serial=config.serial))
        count += 1
    session.commit()
    if count:
        logger.info("added %d printer(s) from PRINTERS", count)
    return count
