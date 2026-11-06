"""What the API shows of AMS data: a tag scan wins over the AMS's guess at the product,
and Review lists spools the AMS reports at 0%."""

from datetime import UTC, datetime

import pytest
from api_helpers import scan, signed_in
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_tracker.db.models import Printer, Product, Spool
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.domain.enums import Role
from filament_tracker.printer.report import TrayReport
from filament_tracker.services.ams import ingest

UID = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def _from_ams(db: Session, *trays: TrayReport) -> None:
    printer = Printer(name="P1S", serial="01P00A000000001", host="192.168.1.40")
    db.add(printer)
    ingest(db, printer, list(trays), T0)
    db.commit()


def _product_exists(db: Session, product_id: int) -> bool:
    db.expire_all()
    return db.scalar(select(Product.id).where(Product.id == product_id)) is not None


def _spool(db: Session) -> Spool:
    db.expire_all()
    spool = db.scalar(select(Spool).where(Spool.tray_uid == UID))
    assert spool is not None
    return spool


def test_a_scanned_tag_moves_the_spool_and_removes_the_provisional_product(
    client: TestClient, token: str, db: Session
) -> None:
    _from_ams(db, TrayReport(0, 0, UID, "GFA00", "PLA", "PLA Basic", "000000FF", 60))
    guess = _spool(db).product
    assert guess.provisional
    guess_id = guess.id

    result = scan(client, token, SyntheticTag(tray_uid=bytes.fromhex(UID)), "opened")

    spool = _spool(db)
    assert result["feedback"] == "already_in_state"
    assert result["spool"]["id"] == spool.id
    assert not spool.product.provisional
    assert spool.product.variant_id == "A00-K00"
    assert not _product_exists(db, guess_id)


def test_only_the_scanned_spools_provisional_product_is_removed(
    client: TestClient, token: str, db: Session
) -> None:
    other = "0F1E2D3C4B5A69788796A5B4C3D2E1F0"
    _from_ams(
        db,
        TrayReport(0, 0, UID, None, "PLA", None, "000000FF", 60),
        TrayReport(0, 1, other, None, "PLA", None, "000000FF", 60),
    )
    # Neither tray has a material ID, so each got its own provisional product.
    guess = _spool(db).product.id

    scan(client, token, SyntheticTag(tray_uid=bytes.fromhex(UID)), "opened")

    assert not _product_exists(db, guess)
    assert db.scalar(select(Spool).where(Spool.tray_uid == other)).product.provisional


def test_a_tag_wins_over_a_matched_real_product(
    client: TestClient, token: str, db: Session
) -> None:
    real = Product(
        material_id="GFA00",
        variant_id="A00-K99",
        filament_type="PLA",
        color_rgba="000000FF",
        display_name="Some other black",
    )
    db.add(real)
    db.commit()
    _from_ams(db, TrayReport(0, 0, UID, "GFA00", "PLA", None, "000000FF", 60))
    assert _spool(db).product.id == real.id

    scan(client, token, SyntheticTag(tray_uid=bytes.fromhex(UID)), "opened")

    assert _spool(db).product.variant_id == "A00-K00"
    assert _product_exists(db, real.id)


@pytest.mark.parametrize("remaining", [0, 5])
def test_review_lists_spools_the_ams_reports_at_zero(
    app: FastAPI, db: Session, remaining: int
) -> None:
    _from_ams(db, TrayReport(0, 0, UID, "GFA00", "PLA", None, "000000FF", remaining))
    viewer = signed_in(app, Role.VIEWER)

    likely = viewer.get("/api/v1/review").json()["likely_empty"]

    if remaining:
        assert likely == []
    else:
        assert [(s["id"], s["remaining_pct"], s["state"]) for s in likely] == [
            (_spool(db).id, 0, "open")
        ]
