"""Hosting platforms, and the deployments of applications and their components on them
(LND-05).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("HST", "DEP")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "hosting_platform",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('active', 'retired')", name=op.f("ck_hosting_platform_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_hosting_platform_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendor.id"], name=op.f("fk_hosting_platform_vendor_id_vendor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hosting_platform")),
        sa.UniqueConstraint("ref", name=op.f("uq_hosting_platform_ref")),
    )
    op.create_table(
        "deployment",
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=True),
        sa.Column("environment", sa.String(length=40), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=300), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_deployment_status")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_deployment_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["component.id"], name=op.f("fk_deployment_component_id_component")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_deployment_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"],
            ["hosting_platform.id"],
            name=op.f("fk_deployment_platform_id_hosting_platform"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deployment")),
        sa.UniqueConstraint("ref", name=op.f("uq_deployment_ref")),
    )
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.create_index("ix_deployment_application_id", ["application_id"], unique=False)
        batch_op.create_index("ix_deployment_platform_id", ["platform_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index("ix_deployment_platform_id")
        batch_op.drop_index("ix_deployment_application_id")

    op.drop_table("deployment")
    op.drop_table("hosting_platform")
