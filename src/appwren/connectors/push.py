"""Push sources: facts posted by the organization's own tools, each holding a push key an
administrator issued (SIG-06).

A key is shown once, when it is issued, and kept only as a hash. It may post facts and nothing
else: no other route accepts it, and a person signed in cannot post facts. Facts arrive in one
format, whatever sent them: a record's reference, a field a source may supply, a value, and
when it was observed. A batch is checked whole before anything is written, so a batch with one
bad fact writes nothing and says which.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.connectors import sourced
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import PushKey, TechnologyRelease
from appwren.events.actor import Actor
from appwren.inventory.registry import find_any

PREFIX = "awp_"
MOST_FACTS = 1000
WHEN = "give observed_at as a date and time, such as 2026-11-20T09:00:00Z"

# Fields that only pushes fill: what the service desk and the monitoring know.
INCIDENTS = sourced.field("application", "incidents_90d", "Incidents (90 days)", "count")
TICKETS = sourced.field("application", "tickets_90d", "Support tickets (90 days)", "count")


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _require(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator issues push keys.")


def issue(session: Session, principal: Principal, name: str) -> tuple[PushKey, str]:
    """A new key for one push source. The key itself is returned this once, never again."""
    _require(principal)
    name = " ".join((name or "").split())
    if not name:
        raise Invalid("No key was issued.", {"name": "Name the tool that will post with it."})
    key = PREFIX + secrets.token_urlsafe(32)
    row = PushKey(name=name[:120], prefix=key[: len(PREFIX) + 6], digest=_digest(key),
                  created_at=utc_now(), created_by_name=principal.name)  # fmt: skip
    session.add(row)
    session.flush()
    return row, key


def revoke(session: Session, principal: Principal, key_id: int) -> PushKey:
    _require(principal)
    row = session.get(PushKey, key_id)
    if row is None:
        raise NotFound("There is no such key.")
    if row.revoked_at is not None:
        raise Conflict("That key is already revoked.")
    row.revoked_at, row.revoked_by_name = utc_now(), principal.name
    session.flush()
    return row


def view(row: PushKey) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "prefix": row.prefix,
        "created_at": row.created_at,
        "created_by": row.created_by_name,
        "last_used_at": row.last_used_at,
        "revoked_at": row.revoked_at,
        "revoked_by": row.revoked_by_name,
    }


def listing(session: Session, principal: Principal) -> list[dict[str, Any]]:
    _require(principal)
    rows = session.scalars(select(PushKey).order_by(PushKey.revoked_at.is_not(None), PushKey.name))
    return [view(row) for row in rows]


def holder(session: Session, presented: str | None) -> PushKey | None:
    """The key presented, if it is one that was issued and is not revoked."""
    if not presented or not presented.startswith(PREFIX):
        return None
    digest = _digest(presented)
    row = session.scalars(select(PushKey).where(PushKey.digest == digest)).first()
    if row is None or row.revoked_at is not None or not hmac.compare_digest(row.digest, digest):
        return None
    return row


def actor(row: PushKey) -> Actor:
    return Actor.system(f"Push: {row.name}")


def _when(value: Any, now: datetime) -> datetime:
    """When the fact was observed: as sent, with its time zone, or now if not sent."""
    if value in (None, ""):
        return now
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "give observed_at as a date and time, such as 2026-11-20T09:00:00Z"
        ) from exc
    if moment.tzinfo is None:
        raise ValueError("say the time zone, such as Z for UTC")
    if moment > now:
        raise ValueError("it is in the future")
    return moment


def _target(session: Session, fact: dict[str, Any]) -> tuple[Any, sourced.Field]:
    ref = str(fact.get("record") or "").strip()
    try:
        record_type, record = find_any(session, ref)
    except NotFound as exc:
        raise ValueError(f"there is no record {ref or '(none given)'}") from exc
    key = record_type.key
    release = fact.get("release")
    if release not in (None, ""):
        if key != "technology":
            raise ValueError("only a technology has releases")
        record = session.scalars(
            select(TechnologyRelease).where(
                TechnologyRelease.technology_id == record.id,
                TechnologyRelease.cycle == str(release),
            )
        ).first()
        if record is None:
            raise ValueError(f"{ref} has no release {release}")
        key = "technology_release"
    spec = sourced.spec_for(key, str(fact.get("field") or ""))
    if spec is None:
        raise ValueError(f"no source supplies {fact.get('field')!r} for this kind of record")
    return record, spec


def take(session: Session, row: PushKey, facts: Any) -> dict[str, int]:
    """Write a batch of facts from one key, each with the key's name as its source. Every fact
    is checked first; if any fails, nothing is written."""
    if not isinstance(facts, list) or not facts:
        raise Invalid("Nothing was written.", {"facts": "Send a list of facts."})
    if len(facts) > MOST_FACTS:
        raise Invalid("Nothing was written.", {"facts": f"Send up to {MOST_FACTS} at a time."})
    now = utc_now()
    ready: list[tuple[Any, sourced.Field, Any, datetime]] = []
    errors: dict[str, str] = {}
    for index, fact in enumerate(facts):
        try:
            if not isinstance(fact, dict):
                raise ValueError("each fact is an object")
            record, spec = _target(session, fact)
            value = sourced.clean(spec, fact.get("value"))
            if value is None:
                raise ValueError("give a value")
            ready.append((record, spec, value, _when(fact.get("observed_at"), now)))
        except ValueError as exc:
            errors[f"facts.{index}"] = str(exc)
    if errors:
        raise Invalid("Nothing was written.", errors)
    counts = {"accepted": len(ready), "changed": 0, "unchanged": 0, "kept": 0}
    for record, spec, value, observed in ready:
        outcome = sourced.write(
            session, source=f"push:{row.prefix}", source_name=row.name, record=record,
            spec=spec, value=value, read_at=observed,
        )  # fmt: skip
        counts[outcome] += 1
    return counts
