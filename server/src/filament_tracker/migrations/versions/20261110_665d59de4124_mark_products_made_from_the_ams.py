"""mark products made from the AMS

Revision ID: 665d59de4124
Revises: 92998d06ecab
Create Date: 2026-11-10 16:21:27.043478
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "665d59de4124"
down_revision: str | None = "92998d06ecab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A plain ADD COLUMN: batch mode would copy and drop the product table, which SQLite
    # refuses while spools refer to it (foreign keys are on).
    op.add_column(
        "product",
        sa.Column("from_ams", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    # Provisional products already made from the AMS: a hand-made product only has
    # placeholder spools (no tray UID) until a tag is scanned, which makes it a real product,
    # so a provisional product with a spool the AMS recorded came from the AMS.
    op.execute(
        """
        UPDATE product SET from_ams = 1
        WHERE provisional = 1 AND id IN (
            SELECT spool.product_id FROM spool
            JOIN event ON event.spool_id = spool.id
            WHERE event.source = 'ams' AND spool.tray_uid IS NOT NULL
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.drop_column("from_ams")
