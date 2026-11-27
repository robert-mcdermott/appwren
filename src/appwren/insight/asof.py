"""As of: an application, and the portfolio, as they stood on a chosen day (RPT-06).

Nothing is stored for this. Every change to a record is an event in the history, holding the
values before and after; the state on a day is those changes, up to the end of that day,
applied in order. The decision on a day is the one recorded last by then, and the scores are
those of the nearest portfolio snapshot taken on or before it.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid
from appwren.db.models import (
    Application,
    Decision,
    Event,
    OrgUnit,
    PortfolioSnapshot,
    ScoreSnapshot,
)
from appwren.events import chain
from appwren.events.audit import CREATED, DELETED
from appwren.insight.shares import IN_SERVICE
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION, TYPES, Field
from appwren.program import vocab

BASE = (Field("name", "Name"), Field("summary", "Summary", "long"),
        Field("org_unit_id", "Unit", "unit"), Field("status", "Status"))  # fmt: skip


def day(value: Any) -> date:
    """The day asked for: a date, today or earlier."""
    try:
        on = value if isinstance(value, date) else date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise Invalid("Choose a day.", {"on": "Give a date."}) from None
    if on > today():
        raise Invalid("Choose a day.", {"on": "Choose today or a day before it."})
    return on


def moment(on: date) -> datetime:
    """The first instant after the day: everything before it happened by its end."""
    return datetime.combine(on + timedelta(days=1), time.min, tzinfo=UTC)


def replay(
    session: Session, subject_type: str, ids: list[int] | None, until: datetime
) -> dict[int, dict[str, Any]]:
    """Each record's values as its history left them by ``until``. A record created later,
    or deleted by then, is not in the answer."""
    statement = select(Event.subject_id, Event.action, Event.changes).where(
        Event.subject_type == subject_type, Event.at < until, Event.subject_id.is_not(None)
    )
    if ids is not None:
        statement = statement.where(Event.subject_id.in_(ids))
    states: dict[int, dict[str, Any]] = {}
    for subject_id, action, changes in session.execute(statement.order_by(Event.id)):
        if action == DELETED:
            states.pop(subject_id, None)
            continue
        if action == CREATED:
            states[subject_id] = {}
        state = states.get(subject_id)
        if state is None:
            continue  # changed, but created before the history began: not known
        for key, (_, after) in (changes or {}).items():
            state[key] = after
    return states


def _decisions(session: Session, until: datetime) -> dict[int, Decision]:
    """The decision on record for each application at ``until``: the last recorded by then."""
    found: dict[int, Decision] = {}
    for row in session.scalars(
        select(Decision).where(Decision.created_at < until).order_by(Decision.created_at)
    ):
        found[row.application_id] = row
    return found


def _snapshot(session: Session, until: datetime) -> PortfolioSnapshot | None:
    return session.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.taken_at < until)
        .order_by(PortfolioSnapshot.taken_at.desc())
    ).first()


class _Shown:
    """Values as people read them: a vocabulary's label, a unit's or record's name."""

    def __init__(self, session: Session, principal: Principal | None = None) -> None:
        self.session = session
        self.principal = principal  # an application they may not see is not named
        self.vocabularies: dict[str, dict[str, str]] = {}
        self.units = {unit.id: unit.name for unit in session.scalars(select(OrgUnit))}

    def label(self, name: str, key: Any) -> Any:
        if name not in self.vocabularies:
            self.vocabularies[name] = vocab.labels(self.session, name)
        return self.vocabularies[name].get(key, key)

    def __call__(self, field: Field, value: Any) -> Any:
        if value is None or value == []:
            return None
        if field.kind == "choice" and field.vocab:
            return self.label(field.vocab, value)
        if field.kind == "many":
            return ", ".join(str(self.label(field.vocab, v) if field.vocab else v) for v in value)
        if field.kind == "unit":
            return self.units.get(value, "A unit since removed")
        if field.kind == "ref" and field.target in TYPES:
            record_type = TYPES[field.target]
            row = self.session.get(record_type.model, value)
            if row is None:
                return "A record since removed"
            if (
                record_type is APPLICATION
                and self.principal is not None
                and not access.sees_application(self.session, self.principal, row)
            ):
                return "An application you may not see"
            return row.name
        if field.name == "status":
            return {"active": "Active", "archived": "Archived"}.get(value, value)
        if field.kind == "bool":
            return "Yes" if value else "No"
        return value


def application(session: Session, principal: Principal, app: Application, on: date) -> dict:
    """One application as it stood at the end of ``on``, beside how it is now."""
    from appwren.insight.trends import _item
    from appwren.landscape import costs

    until = moment(on)
    then = replay(session, "application", [app.id], until).get(app.id)
    out: dict[str, Any] = {**records.chip(APPLICATION, app), "on": on, "existed": then is not None}
    if then is None:
        return out
    owners = records.owners_of(session, APPLICATION, [app.id]).get(app.id, [])
    withheld = set(records.withheld_from(session, principal, APPLICATION, app, owners,
                                         access.sensitive_fields(session)))  # fmt: skip
    if not costs.sees_cost(session, principal, app):
        withheld.add("annual_cost")
    shown = _Shown(session, principal)
    fields = []
    for field in (*BASE, *APPLICATION.fields):
        if field.name in withheld:
            continue
        was, now = then.get(field.name), chain.jsonable(getattr(app, field.name, None))
        fields.append({"field": field.name, "label": field.label, "kind": field.kind,
                       "then": shown(field, was), "now": shown(field, now),
                       "changed": was != now})  # fmt: skip
    decision = _decisions(session, until).get(app.id)
    snapshot = _snapshot(session, until)
    scored = None
    if snapshot is not None:
        snap = session.scalars(
            select(ScoreSnapshot).where(ScoreSnapshot.portfolio_snapshot_id == snapshot.id,
                                        ScoreSnapshot.application_id == app.id)
        ).first()  # fmt: skip
        if snap is not None:
            scored = {"snapshot": {"ref": snapshot.ref, "name": snapshot.name,
                                   "taken_at": snapshot.taken_at}, **_item(snap)}  # fmt: skip
    later = session.scalars(
        select(Event.id).where(Event.subject_type == "application", Event.subject_id == app.id,
                               Event.at >= until)
    ).all()  # fmt: skip
    return {
        **out,
        "fields": fields,
        "decision": {"ref": decision.ref, "disposition": decision.disposition,
                     "label": shown.label("dispositions", decision.disposition),
                     "decided_on": decision.decided_on, "by": decision.decided_by_name}
        if decision else None,
        "scores": scored,
        "changes_since": len(later),
    }  # fmt: skip


def portfolio(session: Session, principal: Principal, on: date) -> dict[str, Any]:
    """The applications in service at the end of ``on``: each with its stage, unit, tier, and
    decision then, beside its stage and decision now."""
    until = moment(on)
    states = replay(session, "application", None, until)
    apps = {app.id: app for app in session.scalars(
        select(Application).where(Application.id.in_(list(states)))
    )}  # fmt: skip
    decisions = _decisions(session, until)
    now = {app.id: app.disposition for app in apps.values()}
    shown = _Shown(session)
    rows, then_ids = [], set()
    for app_id, state in states.items():
        app = apps.get(app_id)
        if app is None or not access.sees_application(session, principal, app):
            continue
        if state.get("status") != "active" or state.get("lifecycle") not in IN_SERVICE:
            continue
        decision = decisions.get(app_id)
        then_ids.add(app_id)
        rows.append({
            **records.chip(APPLICATION, app), "name_then": state.get("name"),
            "unit": shown.units.get(state.get("org_unit_id")), "tier": state.get("tier"),
            "lifecycle": state.get("lifecycle"), "lifecycle_now": app.lifecycle,
            "status_now": app.status,
            "decision": decision.disposition if decision else None,
            "decision_now": now.get(app_id),
        })  # fmt: skip
    rows.sort(key=lambda row: row["name_then"] or row["name"])
    in_service_now = {
        app.id for app in session.scalars(
            select(Application).where(Application.status == "active",
                                      Application.lifecycle.in_(IN_SERVICE))
        ) if access.sees_application(session, principal, app)
    }  # fmt: skip
    snapshot = _snapshot(session, until)
    return {
        "on": on,
        "applications": rows,
        "lifecycle": dict(Counter(row["lifecycle"] for row in rows)),
        "decisions": dict(Counter(row["decision"] or "none" for row in rows)),
        "since": {
            "added": len(in_service_now - then_ids),
            "left": sum(1 for row in rows if row["status_now"] != "active"
                        or row["lifecycle_now"] not in IN_SERVICE),
        },
        "snapshot": {"ref": snapshot.ref, "name": snapshot.name, "taken_at": snapshot.taken_at}
        if snapshot else None,
    }  # fmt: skip
