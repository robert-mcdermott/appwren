"""Keeping the portfolio current: confirmations of a record, campaigns that ask for them,
tasks raised by what happens, saved views, and contested scores."""

from __future__ import annotations

from datetime import date, datetime

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
)
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import JsonType, UtcDateTime


class Attestation(Base):
    """That a person who keeps an application confirmed, on a date, that its record is right:
    the record and its parts. A statement, never edited; the next one follows it (CUR-03)."""

    __tablename__ = "attestation"
    __subject__ = "attestation"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    attested_by: Mapped[int | None] = mapped_column(Integer)
    attested_by_name: Mapped[str] = mapped_column(String(200))
    attested_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_attestation_application_id", "application_id", "attested_on"),)


CAMPAIGN_KINDS = ("confirm", "assess")
CAMPAIGN_STATUSES = ("open", "closed", "cancelled")
ITEM_STATUSES = ("pending", "done", "excused")


class Campaign(Base):
    """The owners of the applications in a unit asked to do one thing by a date: confirm each
    record, or assess each application (CUR-05)."""

    __tablename__ = "campaign"
    __subject__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    message: Mapped[str | None] = mapped_column(Text)
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    tiers: Mapped[list[str]] = mapped_column(JsonType, default=list)
    stages: Mapped[list[str]] = mapped_column(JsonType, default=list)
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    started_on: Mapped[date] = mapped_column(Date)
    started_by: Mapped[int | None] = mapped_column(Integer)
    started_by_name: Mapped[str] = mapped_column(String(200))
    ended_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint("kind IN ('confirm', 'assess')", name="kind"),
        CheckConstraint("status IN ('open', 'closed', 'cancelled')", name="status"),
    )


class CampaignItem(Base):
    """One application in a campaign, and who was asked about it. Done when the thing is done
    after the campaign began; excused by whoever runs the campaign, with a reason."""

    __tablename__ = "campaign_item"
    __audit_parent__ = ("campaign", "campaign_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"))
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    org_unit_id: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    done_on: Mapped[date | None] = mapped_column(Date)
    done_by_name: Mapped[str | None] = mapped_column(String(200))
    excuse: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("campaign_id", "application_id"),
        CheckConstraint("status IN ('pending', 'done', 'excused')", name="status"),
        Index("ix_campaign_item_account_id", "account_id", "status"),
    )


TASK_STATUSES = ("open", "done", "dismissed")


class Task(Base):
    """Something to be done about a record, for a person, by a date, raised by what happened:
    a contract's notice date near, a release reaching end of support, a grant ending, an owner
    leaving (CUR-06). ``key`` says what raised it, so the same cause never raises it twice. It
    closes by itself when its cause is settled, or by a person with a note."""

    __tablename__ = "task"
    __subject__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    subject_type: Mapped[str] = mapped_column(String(24))
    subject_id: Mapped[int] = mapped_column(Integer)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))
    org_unit_id: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    raised_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    closed_by_name: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'done', 'dismissed')", name="status"),
        Index("ix_task_account_id", "account_id", "status"),
        Index("ix_task_status", "status", "due_on"),
    )


class SavedView(Base):
    """A list as someone filtered and sorted it, kept under a name (CUR-08). It holds the
    filters and never the rows, so whoever opens it sees only what they may see."""

    __tablename__ = "saved_view"
    __audit__ = False  # a convenience of one person's, not part of the record

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    owner_name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(80))  # the list: /applications
    name: Mapped[str] = mapped_column(String(80))
    query: Mapped[str] = mapped_column(String(1000))  # its filters, as the address has them
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("account_id", "path", "name"),
        Index("ix_saved_view_path", "path"),
    )


CONTEST_STATUSES = ("open", "accepted", "answered")


class ScoreContest(Base):
    """An owner saying one factor of an application's scores is wrong: what it should be, why,
    and where the evidence is; and the portfolio team's answer (SCR-13). Both stay on the
    record. The score moves only when the record or an assessment is changed."""

    __tablename__ = "score_contest"
    __subject__ = "score_contest"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    dimension: Mapped[str] = mapped_column(String(40))
    factor: Mapped[str] = mapped_column(String(60))
    factor_label: Mapped[str] = mapped_column(String(200))
    level_shown: Mapped[int | None] = mapped_column(Integer)
    level_claimed: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    raised_by: Mapped[int | None] = mapped_column(Integer)
    raised_by_name: Mapped[str] = mapped_column(String(200))
    raised_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    answer: Mapped[str | None] = mapped_column(Text)
    answered_by_name: Mapped[str | None] = mapped_column(String(200))
    answered_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'accepted', 'answered')", name="status"),
        Index("ix_score_contest_application_id", "application_id", "status"),
    )
