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
    low_stock_threshold: int


@dataclass(frozen=True)
class Snapshot:
    products: tuple[ProductState, ...]
    total_sealed: int
    total_open: int
    in_review: int

    @property
    def total_spools(self) -> int:
        """Spools still in hand: sealed and open, not used up."""
        return self.total_sealed + self.total_open

    @property
    def low_stock(self) -> tuple[ProductState, ...]:
        return tuple(p for p in self.products if p.low_stock)


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
            low_stock_threshold=item.product.low_stock_threshold,
        )
        for item in queries.inventory(session)
    )
    # The same total as the Review page's badge.
    in_review = (
        len(queries.flagged_events(session))
        + len(queries.unidentified_tags(session))
        + len(queries.likely_empty(session))
    )
    return Snapshot(
        products,
        total_sealed=sum(p.sealed for p in products),
        total_open=sum(p.open for p in products),
        in_review=in_review,
    )
