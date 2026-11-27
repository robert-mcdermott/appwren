"""Retirement plans (DEC-07)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("planned_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("steps", appwren.db.types.JsonType, nullable=False),
        sa.Column("started_by_name", sa.String(length=200), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("completed_by_name", sa.String(length=200), nullable=True),
        sa.Column("savings", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_retirement_application_id_application"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retirement")),
        sa.UniqueConstraint("application_id", name=op.f("uq_retirement_application_id")),
    )


def downgrade() -> None:
    op.drop_table("retirement")
