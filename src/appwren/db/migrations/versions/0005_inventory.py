"""Inventory: applications, components, vendors, technologies and their releases,
capabilities, people in roles, units that use an application, links, and external
references (INV-01 to INV-11, LND-01, LND-02).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import appwren.db.types

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("APP", "CMP", "VEN", "TEC", "CAP")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "external_ref",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_ref")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "system",
            "value",
            name=op.f("uq_external_ref_record_type_record_id_system_value"),
        ),
    )
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.create_index("ix_external_ref_record", ["record_type", "record_id"], unique=False)
        batch_op.create_index("ix_external_ref_value", ["value"], unique=False)

    op.create_table(
        "record_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_type", sa.String(length=24), nullable=False),
        sa.Column("from_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=24), nullable=False),
        sa.Column("to_type", sa.String(length=24), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_link")),
        sa.UniqueConstraint(
            "from_type",
            "from_id",
            "relation",
            "to_type",
            "to_id",
            name=op.f("uq_record_link_from_type_from_id_relation_to_type_to_id"),
        ),
    )
    with op.batch_alter_table("record_link", schema=None) as batch_op:
        batch_op.create_index("ix_record_link_to", ["to_type", "to_id"], unique=False)

    op.create_table(
        "capability",
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("domain", sa.String(length=40), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_capability_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_capability_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["capability.id"], name=op.f("fk_capability_parent_id_capability")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capability")),
        sa.UniqueConstraint("key", name=op.f("uq_capability_key")),
        sa.UniqueConstraint("ref", name=op.f("uq_capability_ref")),
    )
    with op.batch_alter_table("capability", schema=None) as batch_op:
        batch_op.create_index("ix_capability_parent_id", ["parent_id"], unique=False)

    op.create_table(
        "record_owner",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=24), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_record_owner_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_owner")),
        sa.UniqueConstraint(
            "record_type",
            "record_id",
            "account_id",
            "kind",
            name=op.f("uq_record_owner_record_type_record_id_account_id_kind"),
        ),
    )
    with op.batch_alter_table("record_owner", schema=None) as batch_op:
        batch_op.create_index("ix_record_owner_account_id", ["account_id"], unique=False)
        batch_op.create_index("ix_record_owner_record", ["record_type", "record_id"], unique=False)
        batch_op.create_index(
            "uq_record_owner_one_accountable",
            ["record_type", "record_id"],
            unique=True,
            sqlite_where=sa.text("kind = 'accountable'"),
            postgresql_where=sa.text("kind = 'accountable'"),
        )

    op.create_table(
        "vendor",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("website", sa.String(length=300), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_vendor_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_vendor_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor")),
        sa.UniqueConstraint("ref", name=op.f("uq_vendor_ref")),
    )
    op.create_table(
        "application",
        sa.Column("aliases", appwren.db.types.JsonType, nullable=False),
        sa.Column("lifecycle", sa.String(length=40), nullable=False),
        sa.Column("lifecycle_since", sa.Date(), nullable=True),
        sa.Column("sourcing", sa.String(length=40), nullable=True),
        sa.Column("purpose", sa.String(length=40), nullable=True),
        sa.Column("pace", sa.String(length=40), nullable=True),
        sa.Column("domain", sa.String(length=40), nullable=True),
        sa.Column("tier", sa.String(length=8), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("product", sa.String(length=200), nullable=True),
        sa.Column("edition", sa.String(length=120), nullable=True),
        sa.Column("hosting", sa.String(length=40), nullable=True),
        sa.Column("users", sa.Integer(), nullable=True),
        sa.Column("external_users", sa.Boolean(), nullable=True),
        sa.Column("maintainers", sa.Integer(), nullable=True),
        sa.Column("support_unit_id", sa.Integer(), nullable=True),
        sa.Column("annual_cost", sa.Integer(), nullable=True),
        sa.Column("funding", sa.String(length=40), nullable=True),
        sa.Column("grant_ref", sa.String(length=120), nullable=True),
        sa.Column("grant_end", sa.Date(), nullable=True),
        sa.Column("sign_in", sa.String(length=40), nullable=True),
        sa.Column("monitoring", sa.String(length=40), nullable=True),
        sa.Column("backup", sa.String(length=40), nullable=True),
        sa.Column("last_restore_test", sa.Date(), nullable=True),
        sa.Column("data_classes", appwren.db.types.JsonType, nullable=True),
        sa.Column("sensitivity", sa.Integer(), nullable=True),
        sa.Column("research_continuity", sa.Boolean(), nullable=True),
        sa.Column("regulated_record", sa.Boolean(), nullable=True),
        sa.Column("records_retention", sa.Boolean(), nullable=True),
        sa.Column("go_live", sa.Date(), nullable=True),
        sa.Column("retire_planned", sa.Date(), nullable=True),
        sa.Column("successor_id", sa.Integer(), nullable=True),
        sa.Column("home_url", sa.String(length=300), nullable=True),
        sa.Column("docs_url", sa.String(length=300), nullable=True),
        sa.Column("fields", appwren.db.types.JsonType, nullable=False),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_application_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_application_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["successor_id"],
            ["application.id"],
            name=op.f("fk_application_successor_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["support_unit_id"],
            ["org_unit.id"],
            name=op.f("fk_application_support_unit_id_org_unit"),
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendor.id"], name=op.f("fk_application_vendor_id_vendor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application")),
        sa.UniqueConstraint("ref", name=op.f("uq_application_ref")),
    )
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.create_index("ix_application_lifecycle", ["lifecycle"], unique=False)
        batch_op.create_index("ix_application_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_application_vendor_id", ["vendor_id"], unique=False)

    op.create_table(
        "technology",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("radar", sa.String(length=24), nullable=True),
        sa.Column("homepage", sa.String(length=300), nullable=True),
        sa.Column("eol_key", sa.String(length=80), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_technology_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_technology_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendor.id"], name=op.f("fk_technology_vendor_id_vendor")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technology")),
        sa.UniqueConstraint("ref", name=op.f("uq_technology_ref")),
    )
    op.create_table(
        "application_capability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_application_capability_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["capability_id"],
            ["capability.id"],
            name=op.f("fk_application_capability_capability_id_capability"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_capability")),
        sa.UniqueConstraint(
            "application_id",
            "capability_id",
            name=op.f("uq_application_capability_application_id_capability_id"),
        ),
    )
    with op.batch_alter_table("application_capability", schema=None) as batch_op:
        batch_op.create_index(
            "ix_application_capability_capability_id", ["capability_id"], unique=False
        )

    op.create_table(
        "application_unit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_application_unit_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_application_unit_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_unit")),
        sa.UniqueConstraint(
            "application_id",
            "org_unit_id",
            name=op.f("uq_application_unit_application_id_org_unit_id"),
        ),
    )
    with op.batch_alter_table("application_unit", schema=None) as batch_op:
        batch_op.create_index("ix_application_unit_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "component",
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("repo_url", sa.String(length=300), nullable=True),
        sa.Column("hosting", sa.String(length=40), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_component_status")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
            name=op.f("fk_component_application_id_application"),
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_component_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component")),
        sa.UniqueConstraint("ref", name=op.f("uq_component_ref")),
    )
    with op.batch_alter_table("component", schema=None) as batch_op:
        batch_op.create_index("ix_component_application_id", ["application_id"], unique=False)

    op.create_table(
        "technology_release",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("technology_id", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.String(length=40), nullable=False),
        sa.Column("released_on", sa.Date(), nullable=True),
        sa.Column("support_ends", sa.Date(), nullable=True),
        sa.Column("extended_ends", sa.Date(), nullable=True),
        sa.Column("latest", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(
            ["technology_id"],
            ["technology.id"],
            name=op.f("fk_technology_release_technology_id_technology"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technology_release")),
        sa.UniqueConstraint(
            "technology_id", "cycle", name=op.f("uq_technology_release_technology_id_cycle")
        ),
    )
    op.create_table(
        "component_technology",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("technology_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component.id"],
            name=op.f("fk_component_technology_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["technology_release.id"],
            name=op.f("fk_component_technology_release_id_technology_release"),
        ),
        sa.ForeignKeyConstraint(
            ["technology_id"],
            ["technology.id"],
            name=op.f("fk_component_technology_technology_id_technology"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_technology")),
        sa.UniqueConstraint(
            "component_id",
            "technology_id",
            name=op.f("uq_component_technology_component_id_technology_id"),
        ),
    )
    with op.batch_alter_table("component_technology", schema=None) as batch_op:
        batch_op.create_index("ix_component_technology_release_id", ["release_id"], unique=False)
        batch_op.create_index(
            "ix_component_technology_technology_id", ["technology_id"], unique=False
        )


def downgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String))
    op.execute(counter.delete().where(counter.c.prefix.in_(PREFIXES)))
    with op.batch_alter_table("component_technology", schema=None) as batch_op:
        batch_op.drop_index("ix_component_technology_technology_id")
        batch_op.drop_index("ix_component_technology_release_id")

    op.drop_table("component_technology")
    op.drop_table("technology_release")
    with op.batch_alter_table("component", schema=None) as batch_op:
        batch_op.drop_index("ix_component_application_id")

    op.drop_table("component")
    with op.batch_alter_table("application_unit", schema=None) as batch_op:
        batch_op.drop_index("ix_application_unit_org_unit_id")

    op.drop_table("application_unit")
    with op.batch_alter_table("application_capability", schema=None) as batch_op:
        batch_op.drop_index("ix_application_capability_capability_id")

    op.drop_table("application_capability")
    op.drop_table("technology")
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.drop_index("ix_application_vendor_id")
        batch_op.drop_index("ix_application_org_unit_id")
        batch_op.drop_index("ix_application_lifecycle")

    op.drop_table("application")
    op.drop_table("vendor")
    with op.batch_alter_table("record_owner", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_record_owner_one_accountable",
            sqlite_where=sa.text("kind = 'accountable'"),
            postgresql_where=sa.text("kind = 'accountable'"),
        )
        batch_op.drop_index("ix_record_owner_record")
        batch_op.drop_index("ix_record_owner_account_id")

    op.drop_table("record_owner")
    with op.batch_alter_table("capability", schema=None) as batch_op:
        batch_op.drop_index("ix_capability_parent_id")

    op.drop_table("capability")
    with op.batch_alter_table("record_link", schema=None) as batch_op:
        batch_op.drop_index("ix_record_link_to")

    op.drop_table("record_link")
    with op.batch_alter_table("external_ref", schema=None) as batch_op:
        batch_op.drop_index("ix_external_ref_value")
        batch_op.drop_index("ix_external_ref_record")

    op.drop_table("external_ref")
