"""Push keys: a secret for one push source, kept only as a hash (SIG-06).

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_key",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("created_by_name", sa.String(length=200), nullable=True),
        sa.Column("last_used_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_name", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_key")),
        sa.UniqueConstraint("digest", name=op.f("uq_push_key_digest")),
    )


def downgrade() -> None:
    op.drop_table("push_key")
