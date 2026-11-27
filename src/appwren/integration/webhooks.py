"""Webhooks: AppWren tells another system when something happens (INT-03).

Deliveries are made from the history, and from the reminders that say something is late. A
job reads the events and reminders added since it last looked, turns the ones that matter
into messages for the webhooks that asked for them, and sends what is waiting. Each message
is small and says what changed, never what a record holds; the receiver asks the API for
more if it needs it. Every message is signed with the webhook's secret, so the receiver can
tell it came from here and was not altered.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.config import Config
from appwren.core import net
from appwren.core.clock import utc_now
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import (
    Application,
    Decision,
    Event,
    Reminder,
    Webhook,
    WebhookCursor,
    WebhookDelivery,
    WebhookState,
)
from appwren.events import audit
from appwren.events.chain import jsonable

TOPICS = {
    "decision.recorded": "A decision is recorded for an application",
    "application.stage_changed": "An application moves to another lifecycle stage",
    "confirmation.lapsed": "An application's record goes past the date it was to be confirmed by",
    "assessment.lapsed": "An application's assessment goes past the date it was due again",
}
LAPSES = {"confirmation": "confirmation.lapsed", "assessment": "assessment.lapsed"}
MAX_ATTEMPTS = 6
BATCH = 50
TIMEOUT = 10
GIVE_UP_AFTER = 20  # failures in a row before a webhook is switched off

Send = Callable[[str, bytes, dict[str, str]], int]


def sign(secret: str, stamp: str, body: bytes) -> str:
    """The signature a receiver recomputes: HMAC-SHA256 over the time, a dot, and the body."""
    mac = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A receiver that answers with a redirect is not followed: it could point anywhere."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _inside(host: str) -> bool:
    """A name that is plainly this machine or a private network, without asking any DNS."""
    if host.lower() in ("localhost", "localhost.localdomain") or host.lower().endswith(
        ".localhost"
    ):
        return True
    try:
        return not ipaddress.ip_address(host.strip("[]")).is_global
    except ValueError:
        return False


def _public(host: str) -> bool:
    """Whether a name resolves only to addresses on the public internet."""
    try:
        found = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    return bool(found) and all(ipaddress.ip_address(address).is_global for address in found)


def _post(url: str, body: bytes, headers: dict[str, str]) -> int:
    host = urlsplit(url).hostname or ""
    if not _public(host):
        # Never the machine's own network: a webhook is for another system, somewhere else.
        raise ValueError(f"{host} is not an address on the public internet")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310

    def deliver() -> int:
        with net.opener().open(request, timeout=TIMEOUT) as answer:
            return int(answer.status)

    return net.within(TIMEOUT * 3, deliver)


def _clean(values: dict[str, Any], current: Webhook | None) -> dict[str, Any]:
    errors: dict[str, str] = {}
    name = str(values.get("name", current.name if current else "") or "").strip()
    if not name or len(name) > 80:
        errors["name"] = "Give it a name of up to 80 characters."
    url = str(values.get("url", current.url if current else "") or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or len(url) > 500:
        errors["url"] = "Give an address that starts with https://."
    elif parts.scheme == "http":
        errors["url"] = "Use https, so that what is sent cannot be read on the way."
    elif _inside(parts.hostname):
        errors["url"] = "Give an address on the public internet, not this machine or its network."
    elif parts.username or parts.password:
        errors["url"] = "Do not put a password in the address. Deliveries are signed instead."
    topics = values.get("topics", current.topics if current else [])
    if not isinstance(topics, list) or not topics or set(topics) - set(TOPICS):
        errors["topics"] = "Choose at least one kind of event."
    if errors:
        raise Invalid("The webhook was not saved.", errors)
    return {
        "name": name,
        "url": url,
        "topics": [topic for topic in TOPICS if topic in topics],
        "active": bool(values.get("active", current.active if current else True)),
    }


def _admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator sets up webhooks.")


def create(session: Session, principal: Principal, values: dict[str, Any]) -> tuple[Webhook, str]:
    """Add a webhook. Returns it with its secret, which is shown this once."""
    _admin(principal)
    cleaned = _clean(values, None)
    secret = "whsec_" + secrets.token_urlsafe(32)
    with audit.operation(session, "webhook.create"):
        row = Webhook(
            **cleaned, secret=secret, created_by=principal.account_id, created_at=utc_now()
        )
        session.add(row)
        session.flush()
    return row, secret


def find(session: Session, webhook_id: int) -> Webhook:
    row = session.get(Webhook, webhook_id)
    if row is None:
        raise NotFound("There is no such webhook.")
    return row


def change(session: Session, principal: Principal, row: Webhook, values: dict[str, Any]) -> Webhook:
    _admin(principal)
    cleaned = _clean(values, row)
    with audit.operation(session, "webhook.change"):
        for key, value in cleaned.items():
            if getattr(row, key) != value:
                setattr(row, key, value)
        session.flush()
    if cleaned["active"]:  # switching it on again gives it a fresh start
        state = session.get(WebhookState, row.id)
        if state is not None:
            state.failures, state.paused = 0, False
    return row


def remove(session: Session, principal: Principal, row: Webhook) -> None:
    _admin(principal)
    with audit.operation(session, "webhook.remove"):
        session.execute(
            WebhookDelivery.__table__.delete().where(WebhookDelivery.webhook_id == row.id)
        )
        session.execute(WebhookState.__table__.delete().where(WebhookState.webhook_id == row.id))
        session.delete(row)
        session.flush()


def view(session: Session, row: Webhook) -> dict[str, Any]:
    recent = session.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == row.id)
        .order_by(WebhookDelivery.id.desc())
        .limit(10)
    ).all()
    state = session.get(WebhookState, row.id)
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "topics": row.topics,
        "active": row.active,
        "paused": bool(state and state.paused),
        "created_at": row.created_at,
        "last_status": state.last_status if state else None,
        "last_delivered_at": state.last_delivered_at if state else None,
        "failures": state.failures if state else 0,
        "deliveries": [
            {
                "id": item.id,
                "topic": item.topic,
                "status": item.status,
                "attempts": item.attempts,
                "created_at": item.created_at,
                "sent_at": item.sent_at,
                "last_error": item.last_error,
            }
            for item in recent
        ],
    }


def listing(session: Session, principal: Principal) -> dict[str, Any]:
    _admin(principal)
    rows = session.scalars(select(Webhook).order_by(Webhook.id)).all()
    return {
        "webhooks": [view(session, row) for row in rows],
        "topics": [{"key": key, "label": label} for key, label in TOPICS.items()],
    }


# --- From the history to messages ---


def _changed(event: Event, field: str) -> tuple[Any, Any] | None:
    change_ = (event.changes or {}).get(field)
    if isinstance(change_, list) and len(change_) == 2 and change_[0] != change_[1]:
        return change_[0], change_[1]
    return None


def _app(session: Session, app_id: int | None) -> dict[str, Any]:
    app = session.get(Application, app_id) if app_id else None
    if app is None:
        return {"ref": None, "name": None}
    # A restricted application's name is not sent: receivers often post to a shared channel.
    return {"ref": app.ref, "name": None if app.restricted else app.name, "tier": app.tier}


def _message(session: Session, event: Event) -> tuple[str, dict[str, Any]] | None:
    """What an event means to the outside, if anything: a topic and a small payload."""
    if event.subject_type == "application" and event.action in ("created", "updated"):
        moved = _changed(event, "lifecycle")
        if moved is None or moved[0] is None:
            return None
        return "application.stage_changed", {
            **_app(session, event.subject_id), "from": moved[0], "to": moved[1],
        }  # fmt: skip
    if event.subject_type == "decision" and event.action == "created":
        decision = session.get(Decision, event.subject_id)
        if decision is None:
            return None
        return "decision.recorded", {
            **_app(session, decision.application_id), "decision": decision.ref,
            "disposition": decision.disposition, "recommendation": decision.recommendation,
            "decided_on": decision.decided_on, "review_on": decision.review_on,
        }  # fmt: skip
    return None


def _lapse(session: Session, reminder: Reminder) -> tuple[str, dict[str, Any]] | None:
    """A reminder that something is now late, as a message: a confirmation or an assessment
    past its date."""
    topic = LAPSES.get(reminder.subject_type)
    if topic is None or reminder.stage != "overdue":
        return None
    if reminder.subject_type == "confirmation":
        app_id = reminder.subject_id
    else:
        from appwren.db.models import Assessment

        found = session.get(Assessment, reminder.subject_id)
        app_id = found.application_id if found else reminder.subject_id
    return topic, {**_app(session, app_id), "due_on": reminder.due_on}


def queue(session: Session, since: datetime | None = None) -> int:
    """Turn the events and reminders added since last time into deliveries. Returns how many
    were queued. A webhook is told of what happened after it was added, or after ``since``."""
    paused = set(
        session.scalars(select(WebhookState.webhook_id).where(WebhookState.paused.is_(True)))
    )
    hooks = [
        hook
        for hook in session.scalars(select(Webhook).where(Webhook.active.is_(True)))
        if hook.id not in paused
    ]
    cursor = session.get(WebhookCursor, 1)
    if cursor is None:
        cursor = WebhookCursor(id=1, event_id=0, reminder_id=0)
        session.add(cursor)
    newest = session.scalars(select(Event.id).order_by(Event.id.desc()).limit(1)).first() or 0
    latest = session.scalars(select(Reminder.id).order_by(Reminder.id.desc()).limit(1)).first()
    latest = latest or 0
    made = 0
    now = utc_now()

    def deliver(topic: str, event_id: int, at: datetime, body: dict[str, Any]) -> None:
        nonlocal made
        for hook in hooks:
            if topic in hook.topics and at >= (since or hook.created_at):
                session.add(WebhookDelivery(webhook_id=hook.id, event_id=event_id, topic=topic,
                                            payload=jsonable(body), created_at=now,
                                            send_after=now))  # fmt: skip
                made += 1

    if hooks and newest > (cursor.event_id or 0):
        events = session.scalars(
            select(Event)
            .where(Event.id > (cursor.event_id or 0), Event.id <= newest,
                   Event.subject_type.in_(("application", "decision")))
            .order_by(Event.id)
        )  # fmt: skip
        for event in events:
            message = _message(session, event)
            if message is not None:
                topic, payload = message
                body = {"topic": topic, "event": event.id, "at": event.at, "data": payload}
                deliver(topic, event.id, event.at, body)
    if hooks and latest > (cursor.reminder_id or 0):
        reminders = session.scalars(
            select(Reminder)
            .where(Reminder.id > (cursor.reminder_id or 0), Reminder.id <= latest,
                   Reminder.stage == "overdue")
            .order_by(Reminder.id)
        )  # fmt: skip
        for reminder in reminders:
            message = _lapse(session, reminder)
            if message is not None:
                topic, payload = message
                # A lapse is news when the job first sees it, to every webhook then.
                deliver(topic, 0, now, {"topic": topic, "event": None, "at": now, "data": payload})
    cursor.event_id, cursor.reminder_id = newest, latest
    return made


def _prepare(item: WebhookDelivery, hook: Webhook) -> tuple[str, bytes, dict[str, str]]:
    """The message as it will be sent: the address, the body, and the signed headers."""
    body = json.dumps(item.payload, separators=(",", ":"), sort_keys=True).encode()
    stamp = str(int(utc_now().timestamp()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AppWren-Webhook",
        "X-AppWren-Topic": item.topic,
        "X-AppWren-Delivery": str(item.id),
        "X-AppWren-Timestamp": stamp,
        "X-AppWren-Signature": sign(hook.secret, stamp, body),
    }
    return hook.url, body, headers


def _attempt(send: Send, url: str, body: bytes, headers: dict[str, str]) -> str | None:
    """Send it, with no database session open, and say what went wrong, if anything. A
    receiver that is slow to answer must never hold anyone else's work up."""
    try:
        status = send(url, body, headers)
        return None if 200 <= status < 300 else f"The receiver answered {status}."
    except urllib.error.HTTPError as exc:
        return f"The receiver answered {exc.code}."
    except (OSError, ValueError) as exc:
        return f"It could not be reached: {type(exc).__name__}."


def _record(
    session: Session, item: WebhookDelivery, hook: Webhook, problem: str | None, *, counts: bool
) -> bool:
    """Keep how an attempt went. ``counts`` is false for a test, which is not held against
    the webhook."""
    item.attempts += 1
    now = utc_now()
    state = session.get(WebhookState, hook.id)
    if state is None:
        state = WebhookState(webhook_id=hook.id, failures=0, paused=False)
        session.add(state)
    if problem is None:
        item.status, item.sent_at, item.last_error = "sent", now, None
        state.last_status, state.last_delivered_at = "Delivered", now
        if counts:
            state.failures = 0
        return True
    item.last_error = state.last_status = problem
    if item.attempts >= MAX_ATTEMPTS:
        item.status = "failed"
    else:
        item.send_after = now + timedelta(minutes=2**item.attempts)  # 2, 4, 8, 16, 32
    if counts:
        state.failures += 1
        if state.failures >= GIVE_UP_AFTER:
            state.paused = True
            state.last_status = f"Paused after {GIVE_UP_AFTER} failures in a row. {problem}"
    return False


def _claim(db: Database) -> list[int]:
    """Take a batch to send, so that no other process takes the same ones."""
    now = utc_now()
    with db.bookkeeping() as session:
        rows = session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.status == "queued", WebhookDelivery.send_after <= now)
            .order_by(WebhookDelivery.id)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.send_after = now + timedelta(minutes=10)  # taken up again if this process dies
        return [row.id for row in rows]


def send_queued(db: Database, send: Send = _post) -> tuple[int, int]:
    """Send what is due. Returns how many were delivered and how many were not."""
    sent = failed = 0
    for delivery_id in _claim(db):
        with db.bookkeeping() as session:
            item = session.get(WebhookDelivery, delivery_id)
            hook = session.get(Webhook, item.webhook_id) if item else None
            if item is None or hook is None or item.status != "queued":
                continue
            state = session.get(WebhookState, hook.id)
            if not hook.active or (state is not None and state.paused):
                item.status, item.last_error = "failed", "The webhook is switched off or paused."
                failed += 1
                continue
            message = _prepare(item, hook)
        problem = _attempt(send, *message)
        with db.bookkeeping() as session:
            item = session.get(WebhookDelivery, delivery_id)
            hook = session.get(Webhook, item.webhook_id) if item else None
            if item is None or hook is None:
                continue
            if _record(session, item, hook, problem, counts=True):
                sent += 1
            else:
                failed += 1
    return sent, failed


def run_once(db: Database, _config: Config | None = None, send: Send = _post) -> dict[str, int]:
    with db.bookkeeping() as session:
        queued = queue(session)
    sent, failed = send_queued(db, send)
    return {"queued": queued, "sent": sent, "failed": failed}


def send_test(db: Database, principal: Principal, webhook_id: int, send: Send = _post) -> str:
    """Send one made-up message now, and say how it went."""
    _admin(principal)
    with db.bookkeeping() as session:
        hook = find(session, webhook_id)
        now = utc_now()
        item = WebhookDelivery(
            webhook_id=hook.id,
            event_id=0,
            topic="test",
            payload={
                "topic": "test",
                "event": 0,
                "at": jsonable(now),
                "data": {"message": "A test from AppWren."},
            },
            created_at=now,
            send_after=now,
            attempts=MAX_ATTEMPTS - 1,
        )
        session.add(item)
        session.flush()
        item_id, message = item.id, _prepare(item, hook)
    problem = _attempt(send, *message)
    with db.bookkeeping() as session:
        item = session.get(WebhookDelivery, item_id)
        hook = find(session, webhook_id)
        assert item is not None
        ok = _record(session, item, hook, problem, counts=False)
        return "Delivered" if ok else str(item.last_error)
