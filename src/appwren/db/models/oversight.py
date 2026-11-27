"""Keeping the portfolio current: confirmations of a record by the people who keep it."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import UtcDateTime


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
