"""Tasks: what is to be done about a record, for whom, by when, raised by a contract's
notice date, a release's end of support, a grant's end, or an owner leaving (CUR-06).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("raised_on", sa.Date(), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("closed_by_name", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('open', 'done', 'dismissed')", name=op.f("ck_task_status")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_task_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_task_application_id_application"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
        sa.UniqueConstraint("key", name=op.f("uq_task_key")),
    )
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.create_index("ix_task_account_id", ["account_id", "status"], unique=False)
        batch_op.create_index("ix_task_status", ["status", "due_on"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("task", schema=None) as batch_op:
        batch_op.drop_index("ix_task_status")
        batch_op.drop_index("ix_task_account_id")

    op.drop_table("task")
