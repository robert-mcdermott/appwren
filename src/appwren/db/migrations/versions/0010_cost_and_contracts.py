"""What applications cost: cost lines, the funding sources that pay, and the contracts
behind them (CST-03, CST-04).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("FND", "CON")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "funding_source",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
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
            "status IN ('active', 'retired')", name=op.f("ck_funding_source_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_funding_source_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_funding_source")),
        sa.UniqueConstraint("ref", name=op.f("uq_funding_source_ref")),
    )
    op.create_table(
        "contract",
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=120), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("notice_days", sa.Integer(), nullable=True),
        sa.Column("auto_renews", sa.Boolean(), nullable=True),
        sa.Column("annual_value", sa.Integer(), nullable=True),
        sa.Column("licenses", sa.Integer(), nullable=True),
        sa.Column("data_agreement", sa.String(length=40), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_contract_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_contract_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["account.id"], name=op.f("fk_contract_owner_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendor.id"], name=op.f("fk_contract_vendor_id_vendor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract")),
        sa.UniqueConstraint("ref", name=op.f("uq_contract_ref")),
    )
    with op.batch_alter_table("contract", schema=None) as batch_op:
        batch_op.create_index("ix_contract_ends_on", ["ends_on"], unique=False)
        batch_op.create_index("ix_contract_vendor_id", ["vendor_id"], unique=False)

    op.create_table(
        "contract_application",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("licenses_used", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_contract_application_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contract.id"],
            name=op.f("fk_contract_application_contract_id_contract"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_application")),
        sa.UniqueConstraint(
            "contract_id",
            "application_id",
            name=op.f("uq_contract_application_contract_id_application_id"),
        ),
    )
    with op.batch_alter_table("contract_application", schema=None) as batch_op:
        batch_op.create_index(
            "ix_contract_application_application_id", ["application_id"], unique=False
        )

    op.create_table(
        "cost_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("funding_source_id", sa.Integer(), nullable=True),
        sa.Column("contract_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_cost_line_amount")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_cost_line_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contract.id"], name=op.f("fk_cost_line_contract_id_contract")
        ),
        sa.ForeignKeyConstraint(
            ["funding_source_id"],
            ["funding_source.id"],
            name=op.f("fk_cost_line_funding_source_id_funding_source"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cost_line")),
    )
    with op.batch_alter_table("cost_line", schema=None) as batch_op:
        batch_op.create_index("ix_cost_line_application_id", ["application_id"], unique=False)
        batch_op.create_index("ix_cost_line_funding_source_id", ["funding_source_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("cost_line", schema=None) as batch_op:
        batch_op.drop_index("ix_cost_line_funding_source_id")
        batch_op.drop_index("ix_cost_line_application_id")

    op.drop_table("cost_line")
    with op.batch_alter_table("contract_application", schema=None) as batch_op:
        batch_op.drop_index("ix_contract_application_application_id")

    op.drop_table("contract_application")
    with op.batch_alter_table("contract", schema=None) as batch_op:
        batch_op.drop_index("ix_contract_vendor_id")
        batch_op.drop_index("ix_contract_ends_on")

    op.drop_table("contract")
    op.drop_table("funding_source")
