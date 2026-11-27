"""Decisions recorded by the application's own accountable owner, where the program allows it
for teams too small for anyone else to decide.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("decision", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("self_recorded", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("decision", schema=None) as batch_op:
        batch_op.alter_column("self_recorded", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("decision", schema=None) as batch_op:
        batch_op.drop_column("self_recorded")
