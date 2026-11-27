"""Confirming a record: the people who keep an application say that its record is right, on a
cadence set by its tier (CUR-03).

A confirmation covers the application's record and its parts: components, interfaces, where
it runs, cost lines, and the people named on it. A record past its confirmation is *stale*:
its page says so, data quality counts it, and the engine takes the scoring model's penalty
off its data confidence, with the reason in the working. Confirming it gives the points back.

A record that was never confirmed is due one period after it was added, or after the day this
installation began asking, whichever is later. So an upgrade makes nothing stale on its first
day, and a record added yesterday is not stale today.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.access.principal import Principal
from appwren.core.clock import add_months, today, utc_now
from appwren.core.errors import PermissionDenied
from appwren.db.models import Account, Application, Attestation
from appwren.engine.model import months_to_confirm
from appwren.inventory import access
from appwren.program import settings

BEGAN = "attestation_began"  # the day this installation began asking, as an ISO date
NOTE_LIMIT = 2000


def began(session: Session) -> date | None:
    value = settings.get(session, BEGAN)
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def begin(session: Session) -> bool:
    """Note the day this installation began asking, if it has not been noted. Run at setup
    and at every upgrade, so the day is the first on which this code ran."""
    if began(session) is not None:
        return False
    return settings.put(session, BEGAN, today().isoformat())


def latest(session: Session, application_ids: Iterable[int]) -> dict[int, Attestation]:
    """Each application's most recent confirmation."""
    ids = list(application_ids)
    found: dict[int, Attestation] = {}
    if not ids:
        return found
    for row in session.scalars(
        select(Attestation)
        .where(Attestation.application_id.in_(ids))
        .order_by(Attestation.attested_on, Attestation.id)
    ):
        found[row.application_id] = row
    return found


def due_on(
    app: Application, last: Attestation | None, start: date | None, model: Mapping[str, Any]
) -> date:
    """When the record is next to be confirmed."""
    tier = int(app.tier) if app.tier and str(app.tier).isdigit() else None
    if last is not None:
        base = last.attested_on
    else:
        added = app.created_at.date()
        base = max(added, start) if start is not None else today()
    return add_months(base, months_to_confirm(model, tier))


def facts(
    session: Session, apps: list[Application], model: Mapping[str, Any], on: date
) -> dict[int, dict[str, Any]]:
    """What the engine reads: when each record was last confirmed, when it is next due, and
    whether it is past that."""
    last = latest(session, [app.id for app in apps])
    start = began(session)
    out = {}
    for app in apps:
        row = last.get(app.id)
        due = due_on(app, row, start, model)
        out[app.id] = {
            "confirmed_on": row.attested_on if row else None,
            "confirm_due": due,
            "stale": due < on,
        }
    return out


def can_confirm(session: Session, principal: Principal, app: Application) -> bool:
    """Anyone named on it, its unit's stewards, and managers."""
    if access.named(session, principal, app):
        return True
    return principal.covers(roles.STEWARD, app.org_unit_id) or principal.covers(
        roles.MANAGER, app.org_unit_id
    )


def confirm(
    session: Session, principal: Principal, app: Application, *, note: str | None = None
) -> Attestation:
    """Confirm that an application's record is right as of today."""
    if not can_confirm(session, principal, app):
        raise PermissionDenied(
            "Only someone named on this application, its unit's steward, or a manager confirms "
            "its record."
        )
    if app.lifecycle in ("retired", "archived"):
        raise PermissionDenied("A retired or archived application's record is not confirmed.")
    who = session.get(Account, principal.account_id) if principal.account_id else None
    text = (note or "").strip()[:NOTE_LIMIT] or None
    row = Attestation(
        application_id=app.id,
        attested_by=principal.account_id,
        attested_by_name=who.display_name if who else principal.actor.label,
        attested_on=today(),
        note=text,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    from appwren.oversight import campaigns

    campaigns.refresh_application(session, app.id, "confirm")
    return row


def view(row: Attestation) -> dict[str, Any]:
    return {
        "id": row.id,
        "by": row.attested_by_name,
        "by_id": row.attested_by,
        "on": row.attested_on,
        "note": row.note,
    }


def history(session: Session, app: Application) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Attestation)
        .where(Attestation.application_id == app.id)
        .order_by(Attestation.attested_on.desc(), Attestation.id.desc())
    )
    return [view(row) for row in rows]


def state(
    session: Session, principal: Principal, app: Application, model: Mapping[str, Any]
) -> dict[str, Any]:
    """What the application's page shows: the last confirmation, when the next is due, and
    whether this person may confirm it."""
    row = latest(session, [app.id]).get(app.id)
    due = due_on(app, row, began(session), model)
    in_service = app.lifecycle not in ("retired", "archived")
    return {
        "last": view(row) if row else None,
        "due_on": due if in_service else None,
        "stale": in_service and due < today(),
        "months": months_to_confirm(
            model, int(app.tier) if app.tier and str(app.tier).isdigit() else None
        ),
        "can_confirm": in_service and can_confirm(session, principal, app),
    }


def _due(session: Session, on: date, horizon: date) -> list[Any]:
    """Reminders: each record in service whose confirmation is nearly due, or late."""
    from appwren.people import notices
    from appwren.reminders import NOT_IN_SERVICE, Due, _model

    model = _model(session)  # the defaults, before a model is installed
    apps = list(
        session.scalars(select(Application).where(Application.lifecycle.not_in(NOT_IN_SERVICE)))
    )
    last = latest(session, [app.id for app in apps])
    start = began(session)
    found = []
    for app in apps:
        due = due_on(app, last.get(app.id), start, model)
        if due > horizon:
            continue
        found.append(
            Due(
                "confirmation",
                app.id,
                due,
                f"confirming the record of {app.ref} {app.name}",
                f"/applications/{app.ref}",
                tuple(notices.accountable(session, app.id)),
                app.org_unit_id,
                late="Not confirmed",
            )
        )
    return found


def _register() -> None:
    from appwren import reminders

    if _due not in reminders.SOURCES:
        reminders.SOURCES.append(_due)


_register()
