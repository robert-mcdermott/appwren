"""Campaigns: the owners of the applications in a unit asked to confirm or to assess by a
date, with each application an item (CUR-05).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "CMG", "value": 0}])
    op.create_table(
        "campaign",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("tiers", appwren.db.types.JsonType, nullable=False),
        sa.Column("stages", appwren.db.types.JsonType, nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("started_by", sa.Integer(), nullable=True),
        sa.Column("started_by_name", sa.String(length=200), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("created_at", appwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('confirm', 'assess')", name=op.f("ck_campaign_kind")),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')", name=op.f("ck_campaign_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_campaign_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign")),
        sa.UniqueConstraint("ref", name=op.f("uq_campaign_ref")),
    )
    op.create_table(
        "campaign_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("done_on", sa.Date(), nullable=True),
        sa.Column("done_by_name", sa.String(length=200), nullable=True),
        sa.Column("excuse", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'done', 'excused')", name=op.f("ck_campaign_item_status")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_campaign_item_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_campaign_item_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaign.id"], name=op.f("fk_campaign_item_campaign_id_campaign")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_item")),
        sa.UniqueConstraint(
            "campaign_id",
            "application_id",
            name=op.f("uq_campaign_item_campaign_id_application_id"),
        ),
    )
    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.create_index("ix_campaign_item_account_id", ["account_id", "status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.drop_index("ix_campaign_item_account_id")

    op.drop_table("campaign_item")
    op.drop_table("campaign")
    op.execute("DELETE FROM counter WHERE prefix = 'CMG'")
