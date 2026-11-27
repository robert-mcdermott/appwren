"""Personal tokens and suggestions (INT-05)

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suggestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=60), nullable=False),
        sa.Column("proposed", appwren.db.types.JsonType, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("proposed_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_suggestion_application_id_application"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suggestion")),
    )
    with op.batch_alter_table("suggestion", schema=None) as batch_op:
        batch_op.create_index(
            "ix_suggestion_application", ["application_id", "status"], unique=False
        )

    with op.batch_alter_table("api_token", schema=None) as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_api_token_account_id_account"), "account", ["account_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("api_token", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_api_token_account_id_account"), type_="foreignkey")
        batch_op.drop_column("account_id")

    with op.batch_alter_table("suggestion", schema=None) as batch_op:
        batch_op.drop_index("ix_suggestion_application")

    op.drop_table("suggestion")
