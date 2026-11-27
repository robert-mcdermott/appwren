"""Saved views of a list (CUR-08), and owners contesting one factor of a score with the
portfolio team's answer (SCR-13).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_view",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("query", sa.String(length=1000), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_saved_view_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_view")),
        sa.UniqueConstraint(
            "account_id", "path", "name", name=op.f("uq_saved_view_account_id_path_name")
        ),
    )
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.create_index("ix_saved_view_path", ["path"], unique=False)

    op.create_table(
        "score_contest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(length=40), nullable=False),
        sa.Column("factor", sa.String(length=60), nullable=False),
        sa.Column("factor_label", sa.String(length=200), nullable=False),
        sa.Column("level_shown", sa.Integer(), nullable=True),
        sa.Column("level_claimed", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("raised_by", sa.Integer(), nullable=True),
        sa.Column("raised_by_name", sa.String(length=200), nullable=False),
        sa.Column("raised_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_by_name", sa.String(length=200), nullable=True),
        sa.Column("answered_on", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'accepted', 'answered')", name=op.f("ck_score_contest_status")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_score_contest_application_id_application"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_contest")),
    )
    with op.batch_alter_table("score_contest", schema=None) as batch_op:
        batch_op.create_index(
            "ix_score_contest_application_id", ["application_id", "status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("score_contest", schema=None) as batch_op:
        batch_op.drop_index("ix_score_contest_application_id")

    op.drop_table("score_contest")
    with op.batch_alter_table("saved_view", schema=None) as batch_op:
        batch_op.drop_index("ix_saved_view_path")

    op.drop_table("saved_view")
