"""Decisions: a disposition for an application by a named person, with the snapshot it was
made against; and the copies on the application that lists filter by (DEC-01 to DEC-05).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("DEC",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(length=24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("target_on", sa.Date(), nullable=True),
        sa.Column("review_on", sa.Date(), nullable=False),
        sa.Column("successor_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("recommendation", sa.String(length=24), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=False),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_decision_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["score_snapshot.id"],
            name=op.f("fk_decision_snapshot_id_score_snapshot"),
        ),
        sa.ForeignKeyConstraint(
            ["successor_id"], ["application.id"], name=op.f("fk_decision_successor_id_application")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision")),
        sa.UniqueConstraint("ref", name=op.f("uq_decision_ref")),
    )
    with op.batch_alter_table("decision", schema=None) as batch_op:
        batch_op.create_index("ix_decision_application_id", ["application_id"], unique=False)

    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.add_column(sa.Column("disposition", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("review_on", sa.Date(), nullable=True))


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.drop_column("review_on")
        batch_op.drop_column("disposition")

    with op.batch_alter_table("decision", schema=None) as batch_op:
        batch_op.drop_index("ix_decision_application_id")

    op.drop_table("decision")
