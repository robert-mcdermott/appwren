"""What other systems use: API tokens, webhooks, and the deliveries waiting to be sent
(INT-02, INT-03)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from appwren.db.base import Base
from appwren.db.types import JsonType, UtcDateTime


class ApiToken(Base):
    """A secret another system presents instead of signing in. An administrator issues it
    for one role, perhaps for one unit, and perhaps for reading only. Only its hash is kept.
    A change made with it is recorded against the token's name."""

    __tablename__ = "api_token"
    __subject__ = "api_token"
    __audit_redact__ = frozenset({"token_hash"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A person's own token acts as them, to read and to draft; an administrator's acts as a
    # role. Only one of the two is set.
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"))
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(24))
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    prefix: Mapped[str] = mapped_column(String(12))  # the start of the token, to tell them apart
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    created_by_name: Mapped[str] = mapped_column(String(200))
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class ApiTokenUse(Base):
    """When a token was last used. Bookkeeping, kept apart from the token so that using a
    token is not an entry in the history."""

    __tablename__ = "api_token_use"
    __audit__ = False

    token_id: Mapped[int] = mapped_column(ForeignKey("api_token.id"), primary_key=True)
    last_used_at: Mapped[datetime] = mapped_column(UtcDateTime)


class Webhook(Base):
    """An address AppWren tells when something of a chosen kind happens."""

    __tablename__ = "webhook"
    __subject__ = "webhook"
    __audit_redact__ = frozenset({"secret"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str] = mapped_column(String(80))  # signs each delivery
    topics: Mapped[list[str]] = mapped_column(JsonType, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)


class WebhookDelivery(Base):
    """One message for one webhook, until it is sent or given up on."""

    __tablename__ = "webhook_delivery"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook.id"))
    event_id: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    send_after: Mapped[datetime] = mapped_column(UtcDateTime)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_webhook_delivery_status", "status", "send_after"),)


class WebhookCursor(Base):
    """The last event, and the last reminder, the webhook job has looked at. One row."""

    __tablename__ = "webhook_cursor"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    event_id: Mapped[int] = mapped_column(Integer, default=0)
    reminder_id: Mapped[int] = mapped_column(Integer, default=0)


class WebhookState(Base):
    """How a webhook's deliveries are going. Bookkeeping, kept apart from the webhook."""

    __tablename__ = "webhook_state"
    __audit__ = False

    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook.id"), primary_key=True)
    last_status: Mapped[str | None] = mapped_column(String(200))
    last_delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    failures: Mapped[int] = mapped_column(Integer, default=0)  # in a row
    # Set when deliveries have failed too many times in a row; cleared when it is switched on.
    paused: Mapped[bool] = mapped_column(Boolean, default=False)


SUGGESTION_STATES = ("pending", "accepted", "dismissed")


class Suggestion(Base):
    """A change someone or something proposes to an application, waiting for a person who
    keeps it to accept or dismiss. Nothing on the record changes until it is accepted, and
    accepting it is that person's own edit, in the history under their name."""

    __tablename__ = "suggestion"
    __subject__ = "suggestion"
    __audit_parent__ = ("application", "application_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    field: Mapped[str] = mapped_column(String(60))
    proposed: Mapped[Any] = mapped_column(JsonType)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))  # who, or what, proposed it
    proposed_by: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    decided_by_name: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_suggestion_application", "application_id", "status"),)


class AssistantExchange(Base):
    """One thing asked of the assistant and what it answered. That an exchange happened, who
    asked, and about what, is in the history; the words themselves are kept here."""

    __tablename__ = "assistant_exchange"
    __subject__ = "assistant_exchange"
    __audit_skip__ = frozenset({"prompt", "response"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(Integer)
    asked_by_name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(24))  # draft or question
    model: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
