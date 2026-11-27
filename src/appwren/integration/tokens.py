"""API tokens: how another system signs in (INT-02).

An administrator issues a token for one role, perhaps limited to one unit, and perhaps to
reading. It is shown once, when it is made, and only its SHA-256 is kept. It never signs in
to the web app and can never administer: a token is for scripts and other systems, and what
it changes is recorded against its name. Every token ends, a year at most after it is made.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.access.principal import Grant, Principal
from appwren.core.clock import today, utc_now
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import ApiToken, ApiTokenUse, OrgUnit
from appwren.events import audit

PREFIX = "awt_"
ROLES = (
    roles.MANAGER,
    roles.ARCHITECT,
    roles.AUDITOR,
    roles.LEADER,
    roles.STEWARD,
    roles.MEMBER,
)  # fmt: skip  (never an administrator)
MAX_LIVE = 50
MAX_DAYS = 366  # a year, and a day for a leap year
USED_EVERY = timedelta(minutes=5)  # how often a token's last use is written down


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _admin(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator issues and revokes tokens.")


def create(session: Session, principal: Principal, values: dict[str, Any]) -> tuple[ApiToken, str]:
    """Issue a token. Returns the row and the token itself, which is never shown again."""
    _admin(principal)
    errors: dict[str, str] = {}
    name = str(values.get("name") or "").strip()
    if not name or len(name) > 80:
        errors["name"] = "Say what the token is for, in up to 80 characters."
    role = str(values.get("role") or "")
    if role not in ROLES:
        errors["role"] = f"Choose one of: {', '.join(ROLES)}. A token never administers."
    unit_id = values.get("org_unit_id")
    if unit_id not in (None, ""):
        if session.get(OrgUnit, int(unit_id)) is None:
            errors["org_unit_id"] = "There is no such unit."
        elif role not in roles.SCOPED:
            errors["org_unit_id"] = "Only a steward, leader, architect, or manager has a unit."
    elif role in roles.UNIT_REQUIRED:
        errors["org_unit_id"] = "A steward's or a leader's token is for one unit. Choose it."
    expires = today() + timedelta(days=90)
    if values.get("expires_on"):
        try:
            expires = date.fromisoformat(str(values["expires_on"]))
        except ValueError:
            errors["expires_on"] = "Give a date as year-month-day."
        else:
            if expires <= today():
                errors["expires_on"] = "Choose a day after today."
            elif expires > today() + timedelta(days=MAX_DAYS):
                errors["expires_on"] = "A token works for a year at most. Issue a new one then."
    if sum(1 for row in listing(session, principal) if row["live"]) >= MAX_LIVE:
        errors["name"] = f"There are {MAX_LIVE} live tokens. Revoke one no longer used."
    if errors:
        raise Invalid("The token was not issued.", errors)
    token = PREFIX + secrets.token_urlsafe(32)
    with audit.operation(session, "token.create"):
        row = ApiToken(
            name=name, role=role, org_unit_id=int(unit_id) if unit_id not in (None, "") else None,
            read_only=bool(values.get("read_only", True)), prefix=token[:10],
            token_hash=digest(token), expires_on=expires, created_at=utc_now(),
            created_by_name=principal.name,
        )  # fmt: skip
        session.add(row)
        session.flush()
    return row, token


def view(row: ApiToken, unit: str | None, used: datetime | None) -> dict[str, Any]:
    expired = row.expires_on < today()
    return {
        "id": row.id, "name": row.name, "role": row.role, "unit": unit,
        "org_unit_id": row.org_unit_id, "read_only": row.read_only, "prefix": row.prefix,
        "expires_on": row.expires_on, "created_at": row.created_at,
        "created_by": row.created_by_name, "last_used_at": used, "revoked_at": row.revoked_at,
        "live": row.revoked_at is None and not expired, "expired": expired,
    }  # fmt: skip


def listing(session: Session, principal: Principal) -> list[dict[str, Any]]:
    _admin(principal)
    used = dict(session.execute(select(ApiTokenUse.token_id, ApiTokenUse.last_used_at)).all())
    names = {unit.id: unit.name for unit in session.scalars(select(OrgUnit))}
    rows = session.scalars(select(ApiToken).order_by(ApiToken.id.desc()))
    return [view(row, names.get(row.org_unit_id or 0), used.get(row.id)) for row in rows]  # type: ignore[arg-type]


def revoke(session: Session, principal: Principal, token_id: int) -> None:
    _admin(principal)
    row = session.get(ApiToken, token_id)
    if row is None:
        raise NotFound("There is no such token.")
    if row.revoked_at is None:
        with audit.operation(session, "token.revoke"):
            row.revoked_at = utc_now()
            session.flush()


def authenticate(session: Session, token: str) -> ApiToken | None:
    """The token's row if it may be used now. Notes the use, now and then."""
    if not token.startswith(PREFIX) or len(token) > 200:
        return None
    row = session.scalars(select(ApiToken).where(ApiToken.token_hash == digest(token))).first()
    if row is None or row.revoked_at is not None or row.expires_on < today():
        return None
    now = utc_now()
    used = session.get(ApiTokenUse, row.id)
    if used is None:
        session.add(ApiTokenUse(token_id=row.id, last_used_at=now))
    elif now - used.last_used_at > USED_EVERY:
        used.last_used_at = now
    return row


def principal_for(session: Session, row: ApiToken) -> Principal:
    """Who a token is for permission checks: its role, over its unit and those beneath it."""
    from appwren.people import units

    grants = () if row.role == roles.MEMBER else (Grant(row.role, row.org_unit_id),)
    coverage: dict[str, frozenset[int] | None] = {}
    if row.role in roles.SCOPED:
        coverage[row.role] = (
            None if row.org_unit_id is None else units.with_descendants(session, [row.org_unit_id])
        )
    members = units.with_descendants(session, [row.org_unit_id]) if row.org_unit_id else frozenset()
    return Principal(
        account_id=None, name=f"{row.name} (token {row.prefix})", grants=grants,
        coverage=coverage, member_units=members, has_password=False, token_id=row.id,
    )  # fmt: skip
