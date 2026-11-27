"""Portfolio reviews and their agendas (PLN-01)

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("REV",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "review",
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("chair_id", sa.Integer(), nullable=True),
        sa.Column("tiers", appwren.db.types.JsonType, nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("opened_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("closed_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("closed_by_name", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("tags", appwren.db.types.JsonType, nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("state IN ('planned', 'open', 'closed')", name=op.f("ck_review_state")),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_review_status")),
        sa.ForeignKeyConstraint(
            ["chair_id"], ["account.id"], name=op.f("fk_review_chair_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_review_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review")),
        sa.UniqueConstraint("ref", name=op.f("uq_review_ref")),
    )
    with op.batch_alter_table("review", schema=None) as batch_op:
        batch_op.create_index("ix_review_held_on", ["held_on"], unique=False)

    op.create_table(
        "review_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("recommendation", sa.String(length=24), nullable=True),
        sa.Column("disposition", sa.String(length=24), nullable=True),
        sa.Column("taken_decision_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "reason IN ('mismatch', 'review_due', 'undecided', 'added')",
            name=op.f("ck_review_item_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_review_item_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_review_item_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["taken_decision_id"],
            ["decision.id"],
            name=op.f("fk_review_item_taken_decision_id_decision"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_item")),
        sa.UniqueConstraint(
            "review_id", "application_id", name=op.f("uq_review_item_review_id_application_id")
        ),
    )
    with op.batch_alter_table("review_item", schema=None) as batch_op:
        batch_op.create_index("ix_review_item_review_id", ["review_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("review_item", schema=None) as batch_op:
        batch_op.drop_index("ix_review_item_review_id")

    op.drop_table("review_item")
    with op.batch_alter_table("review", schema=None) as batch_op:
        batch_op.drop_index("ix_review_held_on")

    op.drop_table("review")
