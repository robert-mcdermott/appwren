"""Leadership reports (RPT-05)

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("RPT",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("content", appwren.db.types.JsonType, nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("made_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("made_by", sa.Integer(), nullable=True),
        sa.Column("made_by_name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["made_by"], ["account.id"], name=op.f("fk_report_made_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report")),
        sa.UniqueConstraint("ref", name=op.f("uq_report_ref")),
    )


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    op.drop_table("report")
