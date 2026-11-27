"""Scenarios (PLN-04)

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("SCN",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "scenario",
        sa.Column("initiative_id", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_scenario_status")),
        sa.ForeignKeyConstraint(
            ["initiative_id"], ["initiative.id"], name=op.f("fk_scenario_initiative_id_initiative")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_scenario_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario")),
        sa.UniqueConstraint("ref", name=op.f("uq_scenario_ref")),
    )
    op.create_table(
        "scenario_change",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("into_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('retire', 'consolidate', 'replace')", name=op.f("ck_scenario_change_action")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_scenario_change_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["into_id"], ["application.id"], name=op.f("fk_scenario_change_into_id_application")
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenario.id"],
            name=op.f("fk_scenario_change_scenario_id_scenario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_change")),
        sa.UniqueConstraint(
            "scenario_id",
            "application_id",
            name=op.f("uq_scenario_change_scenario_id_application_id"),
        ),
    )
    with op.batch_alter_table("scenario_change", schema=None) as batch_op:
        batch_op.create_index("ix_scenario_change_application_id", ["application_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("scenario_change", schema=None) as batch_op:
        batch_op.drop_index("ix_scenario_change_application_id")

    op.drop_table("scenario_change")
    op.drop_table("scenario")
