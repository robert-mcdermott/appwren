"""Attestation: the people who keep an application confirm that its record is right (CUR-03).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attestation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("attested_by", sa.Integer(), nullable=True),
        sa.Column("attested_by_name", sa.String(length=200), nullable=False),
        sa.Column("attested_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_attestation_application_id_application"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attestation")),
    )
    with op.batch_alter_table("attestation", schema=None) as batch_op:
        batch_op.create_index(
            "ix_attestation_application_id", ["application_id", "attested_on"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("attestation", schema=None) as batch_op:
        batch_op.drop_index("ix_attestation_application_id")

    op.drop_table("attestation")
