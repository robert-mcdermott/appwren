"""Connectors: readers an administrator switches on, one at a time, for a named source; their
runs; and the values they supply, kept with their source and any person's override (SIG-01,
SIG-02)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import JsonType, UtcDateTime


class Connector(Base):
    """One reader for one named source. Off until an administrator switches it on. Its
    credential is never here: only the name of the environment variable that holds it."""

    __tablename__ = "connector"
    __subject__ = "connector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    credential_env: Mapped[str | None] = mapped_column(String(80))
    every_hours: Mapped[int] = mapped_column(Integer, default=24)
    next_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_summary: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __audit_skip__ = frozenset({"next_run_at", "last_run_at", "last_status", "last_summary"})


class ConnectorRun(Base):
    """One run of a connector: what it read, changed, and could not match, or why it failed.
    Not history: the changes it made are in the history of the records it changed."""

    __tablename__ = "connector_run"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connector.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)
    finished_at: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(16))
    counts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    unmatched: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    error: Mapped[str | None] = mapped_column(String(600))

    __table_args__ = (
        CheckConstraint("status IN ('ok', 'failed')", name="status"),
        Index("ix_connector_run_connector_id", "connector_id", "id"),
    )


class FactValue(Base):
    """A field of a record as a source last read it, and when; and a person's override of it,
    with the reason. The record's own field holds whichever wins."""

    __tablename__ = "fact_value"
    __audit__ = False  # the record's own field carries the change into its history

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(24))
    record_id: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(60))
    value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(120))
    read_at: Mapped[datetime] = mapped_column(UtcDateTime)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(String(500))
    override_by_name: Mapped[str | None] = mapped_column(String(200))
    override_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("record_type", "record_id", "field"),
        Index("ix_fact_value_record", "record_type", "record_id"),
    )


class Discovered(Base):
    """An application a source knows that is not on record: listed once, for a person to add
    (with its name filled in) or dismiss. A connector never makes a record itself."""

    __tablename__ = "discovered"
    __subject__ = "discovered"
    __audit_skip__ = frozenset({"last_seen_at", "name"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connector.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    first_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(16), default="new")  # new, dismissed, added
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    reason: Mapped[str | None] = mapped_column(String(300))
    record_ref: Mapped[str | None] = mapped_column(String(24))

    __table_args__ = (
        UniqueConstraint("connector_id", "external_id"),
        CheckConstraint("status IN ('new', 'dismissed', 'added')", name="status"),
        Index("ix_discovered_status", "status"),
    )


class PushKey(Base):
    """A secret an administrator issues for one push source: a script that posts facts and does
    nothing else. Shown once when issued; only its hash is kept."""

    __tablename__ = "push_key"
    __subject__ = "push_key"
    __audit_skip__ = frozenset({"last_used_at"})
    __audit_redact__ = frozenset({"digest"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16))  # the start of the key, to tell keys apart
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    created_by_name: Mapped[str | None] = mapped_column(String(200))
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    revoked_by_name: Mapped[str | None] = mapped_column(String(200))
