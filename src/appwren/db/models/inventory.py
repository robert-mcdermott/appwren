"""The inventory: applications and their parts, the vendors and technologies behind them, the
capabilities they serve, the people who answer for them, and the links between them."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from appwren.db.base import Base
from appwren.db.types import JsonType, UtcDateTime

RECORD_STATUSES = ("active", "retired")
ACCOUNTABLE = "accountable"


def one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class RecordMixin:
    """What every record a person can cite has: a reference, a name, and a version."""

    __audit_skip__ = frozenset({"version", "updated_at"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active")
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # A restricted record is known only to the people named on it and those with a role over
    # its unit (spec/security.md).
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Rises with every edit. An edit made against an older version is refused.
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)

    @declared_attr
    def org_unit_id(cls) -> Mapped[int | None]:
        # The unit that answers for an application (a component takes its application's).
        # Shared records (vendors, technologies, capabilities) belong to no unit.
        return mapped_column(ForeignKey("org_unit.id"), nullable=True)


class Application(RecordMixin, Base):
    """The logical thing people name, own, use, and decide about (ADR-0013)."""

    __tablename__ = "application"
    __subject__ = "application"

    aliases: Mapped[list[str]] = mapped_column(JsonType, default=list)
    lifecycle: Mapped[str] = mapped_column(String(40), default="active")
    lifecycle_since: Mapped[date | None] = mapped_column(Date)
    sourcing: Mapped[str | None] = mapped_column(String(40))
    purpose: Mapped[str | None] = mapped_column(String(40))
    pace: Mapped[str | None] = mapped_column(String(40))
    domain: Mapped[str | None] = mapped_column(String(40))
    tier: Mapped[str | None] = mapped_column(String(8))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendor.id"))
    product: Mapped[str | None] = mapped_column(String(200))
    edition: Mapped[str | None] = mapped_column(String(120))
    hosting: Mapped[str | None] = mapped_column(String(40))
    users: Mapped[int | None] = mapped_column(Integer)
    external_users: Mapped[bool | None] = mapped_column(Boolean)
    # Who uses it: everyone, or the units that use it (ApplicationUnit) together with the
    # kinds of people who use it wherever they work (the "audiences" vocabulary).
    org_wide: Mapped[bool | None] = mapped_column(Boolean)
    audiences: Mapped[list[str] | None] = mapped_column(JsonType)
    maintainers: Mapped[int | None] = mapped_column(Integer)
    support_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    annual_cost: Mapped[int | None] = mapped_column(Integer)
    funding: Mapped[str | None] = mapped_column(String(40))
    grant_ref: Mapped[str | None] = mapped_column(String(120))
    grant_end: Mapped[date | None] = mapped_column(Date)
    sign_in: Mapped[str | None] = mapped_column(String(40))
    monitoring: Mapped[str | None] = mapped_column(String(40))
    backup: Mapped[str | None] = mapped_column(String(40))
    last_restore_test: Mapped[date | None] = mapped_column(Date)
    data_classes: Mapped[list[str] | None] = mapped_column(JsonType)
    # The highest sensitivity of its data classes, kept so lists can filter by it.
    sensitivity: Mapped[int | None] = mapped_column(Integer)
    research_continuity: Mapped[bool | None] = mapped_column(Boolean)
    regulated_record: Mapped[bool | None] = mapped_column(Boolean)
    records_retention: Mapped[bool | None] = mapped_column(Boolean)
    go_live: Mapped[date | None] = mapped_column(Date)
    retire_planned: Mapped[date | None] = mapped_column(Date)
    successor_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))
    home_url: Mapped[str | None] = mapped_column(String(300))
    docs_url: Mapped[str | None] = mapped_column(String(300))
    # The organization's own fields, defined in the program, by key.
    fields: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # Copies of the decision on record, so lists can filter and sort by them.
    disposition: Mapped[str | None] = mapped_column(String(24))
    review_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_application_org_unit_id", "org_unit_id"),
        Index("ix_application_vendor_id", "vendor_id"),
        Index("ix_application_lifecycle", "lifecycle"),
    )


class Component(RecordMixin, Base):
    """A part of one application that is built, bought, or maintained on its own."""

    __tablename__ = "component"
    __subject__ = "component"

    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    kind: Mapped[str] = mapped_column(String(40))
    repo_url: Mapped[str | None] = mapped_column(String(300))
    hosting: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_component_application_id", "application_id"),
    )


class Vendor(RecordMixin, Base):
    """A company or project that supplies software or services."""

    __tablename__ = "vendor"
    __subject__ = "vendor"

    kind: Mapped[str] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class Technology(RecordMixin, Base):
    """A language, framework, runtime, database, platform, or product that components use."""

    __tablename__ = "technology"
    __subject__ = "technology"

    kind: Mapped[str] = mapped_column(String(40))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendor.id"))
    radar: Mapped[str | None] = mapped_column(String(24))
    homepage: Mapped[str | None] = mapped_column(String(300))
    # The product's key in an end-of-life dataset, for importing support dates.
    eol_key: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class TechnologyRelease(Base):
    """A version line of a technology, and the dates its maintainers support it until."""

    __tablename__ = "technology_release"
    __audit_parent__ = ("technology", "technology_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    technology_id: Mapped[int] = mapped_column(ForeignKey("technology.id"))
    cycle: Mapped[str] = mapped_column(String(40))
    released_on: Mapped[date | None] = mapped_column(Date)
    support_ends: Mapped[date | None] = mapped_column(Date)
    extended_ends: Mapped[date | None] = mapped_column(Date)
    latest: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (UniqueConstraint("technology_id", "cycle"),)


class ComponentTechnology(Base):
    """A technology a component uses, optionally pinned to the release whose dates apply."""

    __tablename__ = "component_technology"
    __audit_parent__ = ("component", "component_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("component.id"))
    technology_id: Mapped[int] = mapped_column(ForeignKey("technology.id"))
    release_id: Mapped[int | None] = mapped_column(ForeignKey("technology_release.id"))
    version: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        UniqueConstraint("component_id", "technology_id"),
        Index("ix_component_technology_technology_id", "technology_id"),
        Index("ix_component_technology_release_id", "release_id"),
    )


class Capability(RecordMixin, Base):
    """What the organization does, independent of how or with which system. A tree."""

    __tablename__ = "capability"
    __subject__ = "capability"

    parent_id: Mapped[int | None] = mapped_column(ForeignKey("capability.id"))
    domain: Mapped[str | None] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Where it came from in a pack, so that loading the pack again does not add it twice.
    key: Mapped[str | None] = mapped_column(String(80), unique=True)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_capability_parent_id", "parent_id"),
    )


class ApplicationCapability(Base):
    """What an application does for the organization; at most one primary per capability."""

    __tablename__ = "application_capability"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    capability_id: Mapped[int] = mapped_column(ForeignKey("capability.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("application_id", "capability_id"),
        Index("ix_application_capability_capability_id", "capability_id"),
    )


class ApplicationUnit(Base):
    """A unit that uses an application."""

    __tablename__ = "application_unit"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    org_unit_id: Mapped[int] = mapped_column(ForeignKey("org_unit.id"))

    __table_args__ = (
        UniqueConstraint("application_id", "org_unit_id"),
        Index("ix_application_unit_org_unit_id", "org_unit_id"),
    )


class RecordOwner(Base):
    """A person named on a record, and in what role. On an application, exactly one person is
    accountable; the partial unique index holds that on both databases."""

    __tablename__ = "record_owner"
    __audit_parent__ = ("@record_type", "record_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(24))
    record_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    kind: Mapped[str] = mapped_column(String(24))

    __table_args__ = (
        UniqueConstraint("record_type", "record_id", "account_id", "kind"),
        Index("ix_record_owner_account_id", "account_id"),
        Index("ix_record_owner_record", "record_type", "record_id"),
        Index(
            "uq_record_owner_one_accountable",
            "record_type",
            "record_id",
            unique=True,
            sqlite_where=text("kind = 'accountable'"),
            postgresql_where=text("kind = 'accountable'"),
        ),
    )


class ExternalRef(Base):
    """What a record is called in another system: a configuration item, a ticket queue."""

    __tablename__ = "external_ref"
    __audit_parent__ = ("@record_type", "record_id")
    # A change of standing is history; when it was read, or why it could not be, is not.
    __audit_skip__ = frozenset({"standing_read_at", "standing_error"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(24))
    record_id: Mapped[int] = mapped_column(Integer)
    system: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(String(200))
    # Where the other system says how the record stands (INT-07): approved, open, closed.
    standing: Mapped[str | None] = mapped_column(String(80))
    standing_read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    standing_error: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("record_type", "record_id", "system", "value"),
        Index("ix_external_ref_record", "record_type", "record_id"),
        Index("ix_external_ref_value", "value"),
    )


class RecordLink(Base):
    """A named relationship between two records: what depends on what."""

    __tablename__ = "record_link"
    __audit_parent__ = ("@from_type", "from_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_type: Mapped[str] = mapped_column(String(24))
    from_id: Mapped[int] = mapped_column(Integer)
    relation: Mapped[str] = mapped_column(String(24))
    to_type: Mapped[str] = mapped_column(String(24))
    to_id: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("from_type", "from_id", "relation", "to_type", "to_id"),
        Index("ix_record_link_to", "to_type", "to_id"),
    )
