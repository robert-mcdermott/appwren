"""Suggestions: changes proposed to an application, waiting for a person who keeps it (INT-05).

An assistant working for a person, a script, or the person themselves, proposes a value for
one field of an application. Nothing on the record changes. Someone who keeps the
application accepts it, which is their own edit, checked by the same rules as any other and
kept in the history under their name, or dismisses it.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import Application, Suggestion
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION

MAX_PENDING = 50  # for one application at once
MAX_MINE = 10  # from one person, or one token, on one application at once
MAX_VALUE = 4000  # characters, as JSON: the longest field is a summary
HEADER = {"name": "Name", "summary": "Summary"}


def _fields() -> dict[str, str]:
    return {**HEADER, **{field.name: field.label for field in APPLICATION.fields}}


def _withheld(session: Session, principal: Principal, app: Application) -> set[str]:
    """The sensitive fields this person may not see on this application, and so may not
    propose either: a proposal would say what they think the value is."""
    if access.sees_sensitive(session, principal, app):
        return set()
    return set(access.sensitive_fields(session))


def propose(
    session: Session, principal: Principal, app: Application, values: dict[str, Any]
) -> Suggestion:
    """Propose a value for one field. Anyone who may see the application may."""
    if not access.sees_application(session, principal, app):
        raise NotFound(f"There is no application {app.ref}.")
    errors: dict[str, str] = {}
    field = str(values.get("field") or "")
    known = _fields()
    if field not in known or field in _withheld(session, principal, app):
        errors["field"] = (
            f"Propose one of: {', '.join(sorted(set(known) - _withheld(session, principal, app)))}."
        )
    note = " ".join(str(values.get("note") or "").split())[:1000] or None
    if "value" not in values:
        errors["value"] = "Give the value to propose."
    elif len(json.dumps(values.get("value"), default=str)) > MAX_VALUE:
        errors["value"] = f"Keep a proposed value to {MAX_VALUE:,} characters."
    pending = session.scalars(
        select(Suggestion.id).where(Suggestion.application_id == app.id,
                                    Suggestion.status == "pending")
    ).all()  # fmt: skip
    if len(pending) >= MAX_PENDING:
        errors["field"] = "This application has as many waiting suggestions as it may hold."
    mine = session.scalars(
        select(Suggestion.id).where(Suggestion.application_id == app.id,
                                    Suggestion.status == "pending",
                                    Suggestion.source == principal.name[:200])
    ).all()  # fmt: skip
    if len(mine) >= MAX_MINE:
        errors["field"] = f"You have {MAX_MINE} proposals waiting on it. Wait for an answer."
    if errors:
        raise Invalid("The suggestion was not made.", errors)
    row = Suggestion(
        application_id=app.id, field=field, proposed=values.get("value"), note=note,
        source=principal.name[:200], proposed_by=principal.account_id, status="pending",
        created_at=utc_now(),
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


def view(row: Suggestion, labels: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row.id, "field": row.field, "field_label": labels.get(row.field, row.field),
        "value": row.proposed, "note": row.note, "source": row.source, "status": row.status,
        "created_at": row.created_at, "decided_by": row.decided_by_name,
        "decided_at": row.decided_at,
    }  # fmt: skip


def of_application(session: Session, principal: Principal, app: Application) -> dict[str, Any]:
    """What waits on the application, and the last few decided."""
    labels = _fields()
    pending = session.scalars(
        select(Suggestion)
        .where(Suggestion.application_id == app.id, Suggestion.status == "pending")
        .order_by(Suggestion.id.desc())
    ).all()
    decided = session.scalars(
        select(Suggestion)
        .where(Suggestion.application_id == app.id, Suggestion.status != "pending")
        .order_by(Suggestion.id.desc())
        .limit(10)
    ).all()
    rows = [*pending, *decided]
    hidden = _withheld(session, principal, app)
    shown = [row for row in rows if row.field not in hidden]
    return {
        "pending": [view(row, labels) for row in shown if row.status == "pending"],
        "decided": [view(row, labels) for row in shown if row.status != "pending"][:10],
        "may_decide": access.can_edit(session, principal, APPLICATION, app),
    }


def _decidable(
    session: Session, principal: Principal, suggestion_id: int
) -> tuple[Suggestion, Application]:
    row = session.get(Suggestion, suggestion_id)
    app = session.get(Application, row.application_id) if row else None
    if row is None or app is None or not access.sees_application(session, principal, app):
        raise NotFound("There is no such suggestion.")
    if not access.can_edit(session, principal, APPLICATION, app):
        raise PermissionDenied("Only someone who keeps the application accepts or dismisses.")
    if principal.token_id is not None:
        raise PermissionDenied("A suggestion is accepted or dismissed by a person, signed in.")
    if row.status != "pending":
        raise Conflict("It has already been decided.")
    return row, app


def accept(session: Session, principal: Principal, suggestion_id: int) -> Application:
    """Make the change, as the person accepting it."""
    row, app = _decidable(session, principal, suggestion_id)
    records.update(session, principal, APPLICATION, app, {row.field: row.proposed},
                   version=app.version)  # fmt: skip
    row.status, row.decided_by_name, row.decided_at = "accepted", principal.name, utc_now()
    session.flush()
    return app


def dismiss(session: Session, principal: Principal, suggestion_id: int) -> Application:
    row, app = _decidable(session, principal, suggestion_id)
    row.status, row.decided_by_name, row.decided_at = "dismissed", principal.name, utc_now()
    session.flush()
    return app


def _with_suggestions() -> None:
    """An application's page says how many proposed changes wait on it."""
    from sqlalchemy import func

    original = APPLICATION.extra.get("detail")

    def detail(
        session: Session, principal: Principal, record: Application, shown: Any
    ) -> dict[str, Any]:
        out = original(session, principal, record, shown) if original else {}
        waiting = session.scalar(
            select(func.count()).select_from(Suggestion).where(
                Suggestion.application_id == record.id, Suggestion.status == "pending")
        )  # fmt: skip
        return {**out, "suggestions_pending": waiting or 0}

    APPLICATION.extra["detail"] = detail


_with_suggestions()
