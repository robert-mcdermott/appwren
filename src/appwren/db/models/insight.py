"""Insight: leadership reports, frozen when made (RPT-05), and scenarios (PLN-04)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
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
