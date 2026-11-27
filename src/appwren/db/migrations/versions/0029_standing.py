"""Standing of records elsewhere (INT-07)

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.add_column(sa.Column("standing", sa.String(length=80), nullable=True))
        batch_op.add_column(
            sa.Column(
                "standing_read_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(sa.Column("standing_error", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.drop_column("standing_error")
        batch_op.drop_column("standing_read_at")
        batch_op.drop_column("standing")
