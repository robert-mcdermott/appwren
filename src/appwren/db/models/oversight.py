"""Keeping the portfolio current: confirmations of a record by the people who keep it, and
campaigns that ask for them."""

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
