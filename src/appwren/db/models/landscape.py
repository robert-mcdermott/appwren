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
