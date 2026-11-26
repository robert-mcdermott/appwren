"""Decisions: the disposition a named person recorded for an application, with why."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import UtcDateTime


class Decision(Base):
    """A disposition for an application by a named person with the authority, with a
    rationale and a date to look again. Never edited; the next decision supersedes it. It
    keeps the score snapshot it was made against, and that snapshot's digest, so what the
    system recommended at the time is on the record."""

    __tablename__ = "decision"
    __subject__ = "decision"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    disposition: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    target_on: Mapped[date | None] = mapped_column(Date)
    review_on: Mapped[date] = mapped_column(Date)
    successor_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("score_snapshot.id"))
    snapshot_digest: Mapped[str] = mapped_column(String(64))
    recommendation: Mapped[str | None] = mapped_column(String(24))
    decided_by: Mapped[int | None] = mapped_column(Integer)
    decided_by_name: Mapped[str] = mapped_column(String(200))
    decided_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_decision_application_id", "application_id"),)
