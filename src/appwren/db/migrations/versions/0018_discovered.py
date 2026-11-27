"""Applications a source knows that are not on record (SIG-05)

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovered",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("first_seen_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("record_ref", sa.String(length=24), nullable=True),
        sa.CheckConstraint(
            "status IN ('new', 'dismissed', 'added')", name=op.f("ck_discovered_status")
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connector.id"],
            name=op.f("fk_discovered_connector_id_connector"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovered")),
        sa.UniqueConstraint(
            "connector_id", "external_id", name=op.f("uq_discovered_connector_id_external_id")
        ),
    )
    with op.batch_alter_table("discovered", schema=None) as batch_op:
        batch_op.create_index("ix_discovered_status", ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("discovered", schema=None) as batch_op:
        batch_op.drop_index("ix_discovered_status")

    op.drop_table("discovered")
