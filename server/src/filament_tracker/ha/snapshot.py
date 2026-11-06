"""What Home Assistant shows, read from the database in one go."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from filament_tracker.domain.enums import SpoolState
from filament_tracker.services import queries


@dataclass(frozen=True)
class ProductState:
    id: int
    name: str
    filament_type: str
    color_rgba: str
    sealed: int
    open: int
    low_stock: bool


@dataclass(frozen=True)
class Snapshot:
    products: tuple[ProductState, ...]
    total_sealed: int
    in_review: int


def take_snapshot(session: Session) -> Snapshot:
    products = tuple(
        ProductState(
            id=item.product.id,
            name=item.product.display_name,
            filament_type=item.product.filament_type,
            color_rgba=item.product.color_rgba,
            sealed=item.counts.get(SpoolState.SEALED, 0),
            open=item.counts.get(SpoolState.OPEN, 0),
            low_stock=item.low_stock,
        )
        for item in queries.inventory(session)
    )
    # The same total as the Review page's badge.
    in_review = (
        len(queries.flagged_events(session))
        + len(queries.unidentified_tags(session))
        + len(queries.likely_empty(session))
    )
    return Snapshot(products, sum(p.sealed for p in products), in_review)
