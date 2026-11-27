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
