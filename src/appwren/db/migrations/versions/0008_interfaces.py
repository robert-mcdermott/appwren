"""Interfaces: data passing from one application to another, with how, how often, and of
which classes (LND-03).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("INT",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "interface",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("frequency", sa.String(length=40), nullable=True),
        sa.Column("data_classes", appwren.db.types.JsonType, nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_interface_status")),
        sa.CheckConstraint("source_id <> target_id", name=op.f("ck_interface_two_ends")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_interface_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["account.id"], name=op.f("fk_interface_owner_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["application.id"], name=op.f("fk_interface_source_id_application")
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["application.id"], name=op.f("fk_interface_target_id_application")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interface")),
        sa.UniqueConstraint("ref", name=op.f("uq_interface_ref")),
    )
    with op.batch_alter_table("interface", schema=None) as batch_op:
        batch_op.create_index("ix_interface_source_id", ["source_id"], unique=False)
        batch_op.create_index("ix_interface_target_id", ["target_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("interface", schema=None) as batch_op:
        batch_op.drop_index("ix_interface_target_id")
        batch_op.drop_index("ix_interface_source_id")

    op.drop_table("interface")
