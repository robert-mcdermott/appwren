"""Requests for something new (PLN-03)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("REQ",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    have = op.get_bind().execute(sa.text("SELECT prefix FROM counter WHERE prefix = 'REQ'")).first()
    if have is None:
        op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "request",
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
        sa.Column("users_expected", sa.Integer(), nullable=True),
        sa.Column("needed_by", sa.Date(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("outcome_reason", sa.Text(), nullable=True),
        sa.Column("outcome_by_name", sa.String(length=200), nullable=True),
        sa.Column("outcome_at", appwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
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
            "state IN ('submitted', 'evaluating', 'approved', 'met', 'declined')",
            name=op.f("ck_request_state"),
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_request_status")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_request_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["capability_id"], ["capability.id"], name=op.f("fk_request_capability_id_capability")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_request_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["account.id"], name=op.f("fk_request_requested_by_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request")),
        sa.UniqueConstraint("ref", name=op.f("uq_request_ref")),
    )
    with op.batch_alter_table("request", schema=None) as batch_op:
        batch_op.create_index("ix_request_capability_id", ["capability_id"], unique=False)

    op.create_table(
        "request_option",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("approach", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("annual_cost", sa.Integer(), nullable=True),
        sa.Column("fit", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "approach IN ('build', 'buy', 'partner', 'reuse')",
            name=op.f("ck_request_option_approach"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_request_option_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["request.id"],
            name=op.f("fk_request_option_request_id_request"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendor.id"], name=op.f("fk_request_option_vendor_id_vendor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_option")),
    )
    with op.batch_alter_table("request_option", schema=None) as batch_op:
        batch_op.create_index("ix_request_option_request_id", ["request_id"], unique=False)


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("request_option", schema=None) as batch_op:
        batch_op.drop_index("ix_request_option_request_id")

    op.drop_table("request_option")
    with op.batch_alter_table("request", schema=None) as batch_op:
        batch_op.drop_index("ix_request_capability_id")

    op.drop_table("request")
