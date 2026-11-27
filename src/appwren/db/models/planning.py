"""Planning change: portfolio reviews and their agendas (PLN-01), initiatives (PLN-02),
requests for something new (PLN-03), and retirements (DEC-07)."""

from __future__ import annotations

from datetime import date, datetime

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

REVIEW_STATES = ("planned", "open", "closed")
AGENDA_REASONS = ("mismatch", "review_due", "undecided", "added")


class Review(RecordMixin, Base):
    """A portfolio review: a scope (its unit and everything beneath it, narrowed by tier), a
    date, a chair, and an agenda. Planned, then open, then closed; a closed review is a
    record of what was decided and changes no more."""

    __tablename__ = "review"
    __subject__ = "review"

    held_on: Mapped[date] = mapped_column(Date)
    chair_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    tiers: Mapped[list[str]] = mapped_column(JsonType, default=list)
    state: Mapped[str] = mapped_column(String(16), default="planned")
    opened_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    closed_by_name: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(one_of("state", REVIEW_STATES), name="state"),
        Index("ix_review_held_on", "held_on"),
    )


class ReviewItem(Base):
    """An application on a review's agenda: why it is there, the recommendation and the
    decision on record when it was put there, and the decision taken in the review."""

    __tablename__ = "review_item"
    __audit_parent__ = ("review", "review_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"))
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(16))
    recommendation: Mapped[str | None] = mapped_column(String(24))
    disposition: Mapped[str | None] = mapped_column(String(24))  # on record when added
    taken_decision_id: Mapped[int | None] = mapped_column(ForeignKey("decision.id"))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("review_id", "application_id"),
        CheckConstraint(one_of("reason", AGENDA_REASONS), name="reason"),
        Index("ix_review_item_review_id", "review_id"),
    )


INITIATIVE_ACTIONS = ("changes", "retires", "receives")


class Initiative(RecordMixin, Base):
    """A planned change: a modernization, a migration, a consolidation, a retirement, or
    another, with the applications it changes, an owner, a stage, and its dates."""

    __tablename__ = "initiative"
    __subject__ = "initiative"

    kind: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(40), default="proposed")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    budget: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        Index("ix_initiative_org_unit_id", "org_unit_id"),
    )


class InitiativeApplication(Base):
    """An application an initiative changes, and what it does to it: changes it, retires it,
    or moves work onto it."""

    __tablename__ = "initiative_application"
    __audit_parent__ = ("initiative", "initiative_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    initiative_id: Mapped[int] = mapped_column(ForeignKey("initiative.id", ondelete="CASCADE"))
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    action: Mapped[str] = mapped_column(String(16), default="changes")
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("initiative_id", "application_id"),
        CheckConstraint(one_of("action", INITIATIVE_ACTIONS), name="action"),
        Index("ix_initiative_application_application_id", "application_id"),
    )


REQUEST_STATES = ("submitted", "evaluating", "approved", "met", "declined")
APPROACHES = ("build", "buy", "partner", "reuse")


class Request(RecordMixin, Base):
    """A request for something new: the need (its summary), the capability it serves, who
    asked, and how it ended: approved (an application added for it), met by one already on
    record, or declined, each with a reason."""

    __tablename__ = "request"
    __subject__ = "request"

    capability_id: Mapped[int] = mapped_column(ForeignKey("capability.id"))
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    users_expected: Mapped[int | None] = mapped_column(Integer)
    needed_by: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(16), default="submitted")
    outcome_reason: Mapped[str | None] = mapped_column(Text)
    outcome_by_name: Mapped[str | None] = mapped_column(String(200))
    outcome_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(one_of("state", REQUEST_STATES), name="state"),
        Index("ix_request_capability_id", "capability_id"),
    )


class RequestOption(Base):
    """One way to meet a request: build it, buy it, partner for it, or reuse what is on
    record, with what it would cost a year, how well it fits, and why."""

    __tablename__ = "request_option"
    __audit_parent__ = ("request", "request_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("request.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    approach: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendor.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("application.id"))
    annual_cost: Mapped[int | None] = mapped_column(Integer)
    fit: Mapped[int | None] = mapped_column(Integer)  # 1 to 5
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("approach", APPROACHES), name="approach"),
        Index("ix_request_option_request_id", "request_id"),
    )


class Retirement(Base):
    """An application's retirement plan: its date, its checklist (each step done by a named
    person on a date, with a note), and, once done, the savings it realized."""

    __tablename__ = "retirement"
    __subject__ = "retirement"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"), unique=True)
    planned_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[dict[str, dict[str, str]]] = mapped_column(JsonType, default=dict)
    started_by_name: Mapped[str] = mapped_column(String(200))
    started_on: Mapped[date] = mapped_column(Date)
    completed_on: Mapped[date | None] = mapped_column(Date)
    completed_by_name: Mapped[str | None] = mapped_column(String(200))
    savings: Mapped[int | None] = mapped_column(Integer)  # a year, at retirement
