"""Who uses it: everyone, or kinds of people across the organization (INV-08)

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_wide", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("audiences", appwren.db.types.JsonType, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.drop_column("audiences")
        batch_op.drop_column("org_wide")
