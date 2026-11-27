"""Insight: leadership reports, frozen when made (RPT-05), and scenarios (PLN-04)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.models.inventory import RECORD_STATUSES, RecordMixin, one_of
from appwren.db.types import JsonType, UtcDateTime


class Report(Base):
    """A leadership report for a period, worked out once and stored whole. Reopening it reads
    what was stored, never the records as they are now; its digest shows it is the same."""

    __tablename__ = "report"
    __subject__ = "report"
    __audit_redact__ = frozenset({"content"})  # the event keeps its digest, not the whole

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    content: Mapped[dict[str, Any]] = mapped_column(JsonType)
    digest: Mapped[str] = mapped_column(String(64))
    made_at: Mapped[datetime] = mapped_column(UtcDateTime)
    made_by: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    made_by_name: Mapped[str] = mapped_column(String(200))


SCENARIO_ACTIONS = ("retire", "consolidate", "replace")


class Scenario(RecordMixin, Base):
    """A proposed set of changes, and what they would do, before anyone commits to them. It
    changes nothing; it can become an initiative."""

    __tablename__ = "scenario"
    __subject__ = "scenario"

    initiative_id: Mapped[int | None] = mapped_column(ForeignKey("initiative.id"))

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class ScenarioChange(Base):
    """One application a scenario changes: retired, consolidated into another, or replaced by
    another."""

    __tablename__ = "scenario_change"
    __audit_parent__ = ("scenario", "scenario_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"))
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    action: Mapped[str] = mapped_column(String(16))
    into_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("scenario_id", "application_id"),
        CheckConstraint(one_of("action", SCENARIO_ACTIONS), name="action"),
        Index("ix_scenario_change_application_id", "application_id"),
    )
