"""The retirement playbook: a retirement planned, checked off, and counted (DEC-07).

Whoever keeps an application starts its retirement plan with a date. The plan is a checklist:
its users told, its data archived (and where), its interfaces removed, its licenses and
contracts ended, access to it removed, and its infrastructure torn down. Each step is done by
a named person on a date, with a note. When every step is done the plan is completed: the
application is retired, and the savings (its annual cost at that point, the sum of its cost
lines where it has any) are on record. A report sums the savings realized, by year.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import Application, Interface, Retirement
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION

STEPS = {
    "users_told": "Its users told",
    "data_archived": "Its data archived, and where",
    "interfaces_removed": "Its interfaces removed",
    "licenses_ended": "Its licenses and contracts ended",
    "access_removed": "Access to it removed",
    "infrastructure_removed": "Its infrastructure torn down",
}


def _require(session: Session, principal: Principal, app: Application) -> None:
    if not access.keeps(session, principal, app):
        raise PermissionDenied("Only whoever keeps the application plans its retirement.")


def _plan(session: Session, app: Application) -> Retirement | None:
    return session.scalars(select(Retirement).where(Retirement.application_id == app.id)).first()


def _open(session: Session, app: Application) -> Retirement:
    plan = _plan(session, app)
    if plan is None:
        raise NotFound(f"{app.name} has no retirement plan.")
    if plan.completed_on is not None:
        raise Conflict("The retirement is complete, and changes no more.")
    return plan


def start(
    session: Session, principal: Principal, app: Application, planned_on: Any, note: str | None
) -> Retirement:
    """A plan, with the date the application is to be retired by. Its planned retirement on
    the record moves to the same date."""
    _require(session, principal, app)
    if _plan(session, app) is not None:
        raise Conflict(f"{app.name} already has a retirement plan.")
    errors = records.Errors()
    when = records.day(planned_on, "planned_on", errors)
    if when is None and not errors:
        errors.add("planned_on", "Say when it is to be retired by.")
    if errors:
        raise Invalid("The plan was not started.", errors)
    plan = Retirement(application_id=app.id, planned_on=when,
                      note=(note or "").strip()[:2000] or None, steps={},
                      started_by_name=principal.name, started_on=today())  # fmt: skip
    session.add(plan)
    if app.retire_planned != when:
        app.retire_planned = when
        records.touch(session, app)
    session.flush()
    return plan


def mark(
    session: Session, principal: Principal, app: Application, step: str, done: bool,
    note: str | None,
) -> Retirement:  # fmt: skip
    """A step done (by this person, today, with a note), or undone."""
    _require(session, principal, app)
    if step not in STEPS:
        raise NotFound(f"There is no step {step}.")
    plan = _open(session, app)
    steps = dict(plan.steps or {})
    if done:
        steps[step] = {"done_on": today().isoformat(), "by": principal.name,
                       "note": (note or "").strip()[:1000]}  # fmt: skip
    else:
        steps.pop(step, None)
    plan.steps = steps
    session.flush()
    return plan


def complete(session: Session, principal: Principal, app: Application) -> Retirement:
    """Every step done: the application is retired, and its savings are on record."""
    _require(session, principal, app)
    plan = _open(session, app)
    waiting = [label for key, label in STEPS.items() if key not in (plan.steps or {})]
    if waiting:
        said = ", ".join(each.lower() for each in waiting)
        raise Invalid("The retirement was not completed.", {"steps": f"Still to do: {said}."})
    plan.completed_on, plan.completed_by_name = today(), principal.name
    plan.savings = app.annual_cost or 0
    if app.lifecycle != "retired":
        records.update(session, principal, APPLICATION, app, {"lifecycle": "retired"},
                       version=app.version)  # fmt: skip
    session.flush()
    return plan


def cancel(session: Session, principal: Principal, app: Application) -> None:
    """Not to be retired after all: the plan goes, and is in the history."""
    _require(session, principal, app)
    session.delete(_open(session, app))
    session.flush()


def view(session: Session, principal: Principal, app: Application) -> dict[str, Any]:
    plan = _plan(session, app)
    from appwren.landscape import costs

    interfaces = session.scalars(
        select(Interface).where(
            Interface.status == "active",
            (Interface.source_id == app.id) | (Interface.target_id == app.id),
        )
    ).all()
    found: dict[str, Any] = {
        "steps": [{"key": key, "label": label} for key, label in STEPS.items()],
        "interfaces": len(interfaces),
        "may_keep": access.keeps(session, principal, app),
        "plan": None,
    }
    if plan is not None:
        sees = costs.sees_cost(session, principal, app)
        done = plan.steps or {}
        found["plan"] = {
            "planned_on": plan.planned_on, "note": plan.note, "started_by": plan.started_by_name,
            "started_on": plan.started_on, "completed_on": plan.completed_on,
            "completed_by": plan.completed_by_name,
            "savings": plan.savings if sees else None,
            "done": {key: done[key] for key in STEPS if key in done},
            "progress": sum(1 for key in STEPS if key in done),
            "late": plan.completed_on is None and plan.planned_on < today(),
        }  # fmt: skip
    return found


def report(session: Session, principal: Principal) -> dict[str, Any]:
    """Retirements under way, and done with their savings, by year: of the applications the
    person may see, savings only where they may see what the application cost."""
    from appwren.landscape import costs

    rows = session.execute(
        select(Retirement, Application)
        .join(Application, Application.id == Retirement.application_id)
        .order_by(Retirement.planned_on)
    )
    under_way, done = [], []
    by_year: dict[int, int] = defaultdict(int)
    on = today()
    for plan, app in rows:
        if not access.sees_application(session, principal, app):
            continue
        sees = costs.sees_cost(session, principal, app)
        item = {**records.chip(APPLICATION, app), "planned_on": plan.planned_on,
                "progress": sum(1 for key in STEPS if key in (plan.steps or {})),
                "steps": len(STEPS), "started_on": plan.started_on}  # fmt: skip
        if plan.completed_on is None:
            under_way.append({**item, "late": plan.planned_on < on})
        else:
            saved = plan.savings if sees else None
            done.append({**item, "completed_on": plan.completed_on, "savings": saved})
            if saved:
                by_year[plan.completed_on.year] += saved
    done.sort(key=lambda item: item["completed_on"], reverse=True)
    return {
        "under_way": under_way,
        "done": done,
        "savings_by_year": [
            {"year": year, "savings": by_year[year]} for year in sorted(by_year, reverse=True)
        ],
        "savings": sum(by_year.values()),
        "withheld": sum(1 for item in done if item["savings"] is None),
    }
