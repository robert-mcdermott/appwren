"""The landscape around each application: what it exchanges with others, where it runs, and
what it costs (wave 2)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.models.inventory import RECORD_STATUSES, RecordMixin, one_of
from appwren.db.types import JsonType


class Interface(RecordMixin, Base):
    """Data passing from one application to another: how, how often, and of which classes.

    It belongs to no unit. Who may see it follows its two applications, and whoever keeps
    either of them keeps it.
    """

    __tablename__ = "interface"
    __subject__ = "interface"

    source_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    method: Mapped[str] = mapped_column(String(40))
    frequency: Mapped[str | None] = mapped_column(String(40))
    data_classes: Mapped[list[str] | None] = mapped_column(JsonType)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint("source_id <> target_id", name="two_ends"),
        Index("ix_interface_source_id", "source_id"),
        Index("ix_interface_target_id", "target_id"),
    )


class HostingPlatform(RecordMixin, Base):
    """Somewhere things run: a data center, a cloud account, a cluster, a hosting provider.
    Kept for the whole organization by architects and managers."""

    __tablename__ = "hosting_platform"
    __subject__ = "hosting_platform"

    kind: Mapped[str] = mapped_column(String(40))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendor.id"))
    location: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class Deployment(RecordMixin, Base):
    """An application, or one of its components, running in an environment on a platform.
    It takes its unit, its visibility, and its keepers from its application."""

    __tablename__ = "deployment"
    __subject__ = "deployment"

    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    component_id: Mapped[int | None] = mapped_column(ForeignKey("component.id"))
    environment: Mapped[str] = mapped_column(String(40))
    platform_id: Mapped[int] = mapped_column(ForeignKey("hosting_platform.id"))
    url: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_deployment_application_id", "application_id"),
        Index("ix_deployment_platform_id", "platform_id"),
    )


class FundingSource(RecordMixin, Base):
    """What pays: an operating budget, a grant, a chargeback, a capital project. A shared
    record; the amounts are on the cost lines that name it."""

    __tablename__ = "funding_source"
    __subject__ = "funding_source"

    kind: Mapped[str] = mapped_column(String(40))
    code: Mapped[str | None] = mapped_column(String(80))
    ends_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class Contract(RecordMixin, Base):
    """An agreement with a vendor that covers one or more applications. Sensitive as a whole:
    seen by those who run the portfolio and those who may see the cost of an application
    it covers."""

    __tablename__ = "contract"
    __subject__ = "contract"

    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor.id"))
    number: Mapped[str | None] = mapped_column(String(120))
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    # How long before the end the vendor must be told, if it is not to renew.
    notice_days: Mapped[int | None] = mapped_column(Integer)
    auto_renews: Mapped[bool | None] = mapped_column(Boolean)
    annual_value: Mapped[int | None] = mapped_column(Integer)
    licenses: Mapped[int | None] = mapped_column(Integer)
    data_agreement: Mapped[str | None] = mapped_column(String(40))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_contract_vendor_id", "vendor_id"),
        Index("ix_contract_ends_on", "ends_on"),
    )


class ContractApplication(Base):
    """An application a contract covers, and how many of its licenses that application uses."""

    __tablename__ = "contract_application"
    __audit_parent__ = ("contract", "contract_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"))
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    licenses_used: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("contract_id", "application_id"),
        Index("ix_contract_application_application_id", "application_id"),
    )


class CostLine(Base):
    """A yearly amount an application costs, by category, with what pays for it. Once an
    application has lines, its annual cost is their sum."""

    __tablename__ = "cost_line"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    category: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(Integer)
    funding_source_id: Mapped[int | None] = mapped_column(ForeignKey("funding_source.id"))
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id"))
    note: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount"),
        Index("ix_cost_line_application_id", "application_id"),
        Index("ix_cost_line_funding_source_id", "funding_source_id"),
    )
