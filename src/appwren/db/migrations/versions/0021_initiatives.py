"""Initiatives and the applications they change (PLN-02)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("INI",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    have = op.get_bind().execute(sa.text("SELECT prefix FROM counter WHERE prefix = 'INI'")).first()
    if have is None:
        op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "initiative",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("budget", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_initiative_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_initiative_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["account.id"], name=op.f("fk_initiative_owner_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_initiative")),
        sa.UniqueConstraint("ref", name=op.f("uq_initiative_ref")),
    )
    with op.batch_alter_table("initiative", schema=None) as batch_op:
        batch_op.create_index("ix_initiative_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "initiative_application",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("initiative_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('changes', 'retires', 'receives')",
            name=op.f("ck_initiative_application_action"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_initiative_application_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["initiative_id"],
            ["initiative.id"],
            name=op.f("fk_initiative_application_initiative_id_initiative"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_initiative_application")),
        sa.UniqueConstraint(
            "initiative_id",
            "application_id",
            name=op.f("uq_initiative_application_initiative_id_application_id"),
        ),
    )
    with op.batch_alter_table("initiative_application", schema=None) as batch_op:
        batch_op.create_index(
            "ix_initiative_application_application_id", ["application_id"], unique=False
        )


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("initiative_application", schema=None) as batch_op:
        batch_op.drop_index("ix_initiative_application_application_id")

    op.drop_table("initiative_application")
    with op.batch_alter_table("initiative", schema=None) as batch_op:
        batch_op.drop_index("ix_initiative_org_unit_id")

    op.drop_table("initiative")
