"""The landscape around each application: what it exchanges with others, where it runs, and
what it costs (wave 2)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
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
