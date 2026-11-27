"""Assessment and scoring: the question bank and the scoring model, each in versions;
assessments, which are never edited; and the snapshots that keep a score as it was."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import JsonType, UtcDateTime


class Questionnaire(Base):
    """A version of the question bank. Once an assessment answers it, it is never changed."""

    __tablename__ = "questionnaire"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(16))  # current, superseded
    definition: Mapped[dict[str, Any]] = mapped_column(JsonType)
    published_at: Mapped[datetime] = mapped_column(UtcDateTime)
    published_by: Mapped[str] = mapped_column(String(200))


class ScoringModel(Base):
    """A version of the scoring model: profiles, rules, guardrails, flags, and cadence. Once a
    snapshot uses it, it is never changed (ADR-0007)."""

    __tablename__ = "scoring_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(16))
    definition: Mapped[dict[str, Any]] = mapped_column(JsonType)
    published_at: Mapped[datetime] = mapped_column(UtcDateTime)
    published_by: Mapped[str] = mapped_column(String(200))


class Assessment(Base):
    """A set of answers about one application, by a named person on a date. Never edited;
    the next one supersedes it."""

    __tablename__ = "assessment"
    __subject__ = "assessment"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaire.id"))
    # Each question's key: {"level": 1..5 or null for don't know, "note": text or null}
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType)
    note: Mapped[str | None] = mapped_column(Text)
    assessed_by: Mapped[int | None] = mapped_column(Integer)
    assessed_by_name: Mapped[str] = mapped_column(String(200))
    assessed_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    superseded_by: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_assessment_application_id", "application_id"),)


class PortfolioSnapshot(Base):
    """Every scored application's scores, kept together at a moment."""

    __tablename__ = "portfolio_snapshot"
    __subject__ = "portfolio_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    taken_at: Mapped[datetime] = mapped_column(UtcDateTime)
    taken_by: Mapped[int | None] = mapped_column(Integer)
    taken_by_name: Mapped[str] = mapped_column(String(200))
    model_id: Mapped[int] = mapped_column(ForeignKey("scoring_model.id"))
    count: Mapped[int] = mapped_column(Integer)


class ScoreSnapshot(Base):
    """An application's scores and their whole working, as they were. Snapshots are many and
    derived, so each is not an event of its own; its ``digest`` is, in the event of whatever
    took it (a decision, a portfolio snapshot), so a snapshot altered later is detectable."""

    __tablename__ = "score_snapshot"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    portfolio_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("portfolio_snapshot.id"))
    taken_at: Mapped[datetime] = mapped_column(UtcDateTime)
    reason: Mapped[str] = mapped_column(String(16))  # decision, portfolio, manual
    model_id: Mapped[int] = mapped_column(ForeignKey("scoring_model.id"))
    profile_key: Mapped[str] = mapped_column(String(40))
    bv: Mapped[float | None] = mapped_column(Float)
    th: Mapped[float | None] = mapped_column(Float)
    cb: Mapped[float | None] = mapped_column(Float)
    re: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[int] = mapped_column(Integer)
    recommendation: Mapped[str | None] = mapped_column(String(24))
    flags: Mapped[list[str]] = mapped_column(JsonType)
    working: Mapped[dict[str, Any]] = mapped_column(JsonType)
    digest: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_score_snapshot_application_id", "application_id"),
        Index("ix_score_snapshot_portfolio_snapshot_id", "portfolio_snapshot_id"),
        UniqueConstraint("application_id", "portfolio_snapshot_id"),
    )
