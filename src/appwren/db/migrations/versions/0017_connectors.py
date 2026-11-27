"""Connectors an administrator switches on, their runs, and the values they supply with their
source and any override (SIG-01, SIG-02).

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("settings", appwren.db.types.JsonType, nullable=False),
        sa.Column("credential_env", sa.String(length=80), nullable=True),
        sa.Column("every_hours", sa.Integer(), nullable=False),
        sa.Column("next_run_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_summary", sa.String(length=300), nullable=True),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector")),
        sa.UniqueConstraint("key", name=op.f("uq_connector_key")),
    )
    op.create_table(
        "connector_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("started_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("finished_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("counts", appwren.db.types.JsonType, nullable=False),
        sa.Column("unmatched", appwren.db.types.JsonType, nullable=False),
        sa.Column("error", sa.String(length=600), nullable=True),
        sa.CheckConstraint("status IN ('ok', 'failed')", name=op.f("ck_connector_run_status")),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connector.id"],
            name=op.f("fk_connector_run_connector_id_connector"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_run")),
    )
    with op.batch_alter_table("connector_run", schema=None) as batch_op:
        batch_op.create_index("ix_connector_run_connector_id", ["connector_id", "id"], unique=False)

    op.create_table(
        "fact_value",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=60), nullable=False),
        sa.Column("value", appwren.db.types.JsonType, nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("read_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("overridden", sa.Boolean(), nullable=False),
        sa.Column("override_value", appwren.db.types.JsonType, nullable=True),
        sa.Column("override_reason", sa.String(length=500), nullable=True),
        sa.Column("override_by_name", sa.String(length=200), nullable=True),
        sa.Column("override_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_value")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "field",
            name=op.f("uq_fact_value_record_type_record_id_field"),
        ),
    )
    with op.batch_alter_table("fact_value", schema=None) as batch_op:
        batch_op.create_index("ix_fact_value_record", ["record_type", "record_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("fact_value", schema=None) as batch_op:
        batch_op.drop_index("ix_fact_value_record")

    op.drop_table("fact_value")
    with op.batch_alter_table("connector_run", schema=None) as batch_op:
        batch_op.drop_index("ix_connector_run_connector_id")

    op.drop_table("connector_run")
    op.drop_table("connector")
