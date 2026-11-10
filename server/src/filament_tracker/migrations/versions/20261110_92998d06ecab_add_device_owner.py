"""add device owner

Revision ID: 92998d06ecab
Revises: 56ae381470da
Create Date: 2026-11-10 12:34:14.203880
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "92998d06ecab"
down_revision: str | None = "56ae381470da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("device", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_device_user_id"), ["user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_device_user_id_user"), "user", ["user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("device", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_device_user_id_user"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_device_user_id"))
        batch_op.drop_column("user_id")
