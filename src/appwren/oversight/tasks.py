"""Tasks raised by what happens: a contract's notice date near, a release in use reaching
end of support, a grant near its end, an owner leaving (CUR-06).

Each day the triggers look at the dates and the people on record. What needs someone raises a
task for the person who must act, with a date and the reason, and tells them. The cause is in
the task's key, so the same cause never raises a second task. A task closes by itself when its
cause is settled (the contract was renewed or has ended, nothing runs on the release any
more, a decision was recorded, someone was named), or by a person with a note.

How far ahead each trigger looks is the scoring model's cadence (``triggers``). A signal
crossing a threshold waits for signals.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import (
    Account,
    Application,
    Component,
    ComponentTechnology,
    Contract,
    CostLine,
    Decision,
    FundingSource,
    RecordOwner,
    Task,
    Technology,
    TechnologyRelease,
)
from appwren.inventory import access
from appwren.people import notices

DEFAULTS = {"contract_notice_days": 60, "end_of_support_days": 180, "grant_end_days": 180}
NOT_IN_SERVICE = ("retired", "archived")
# An end of support or a grant end this long past is already old news: flagged, not raised.
PAST = timedelta(days=90)
SYSTEM = "AppWren"
KINDS = {
    "contract_notice": "Contract notice",
    "end_of_support": "End of support",
    "grant_end": "Grant ending",
    "departure": "Owner left",
}


def windows(session: Session) -> dict[str, int]:
    from appwren.reminders import _model

    found = (_model(session).get("cadence") or {}).get("triggers") or {}
    return {key: int(found.get(key, default)) for key, default in DEFAULTS.items()}


def _active(session: Session, account_id: int | None) -> bool:
    account = session.get(Account, account_id) if account_id else None
    return account is not None and account.status == "active"


def _first_active(session: Session, candidates: list[int]) -> int | None:
    return next((each for each in candidates if _active(session, each)), None)


def _keeper(session: Session, org_unit_id: int | None) -> int | None:
    """A steward of the unit, or failing one, a manager over it."""
    if org_unit_id is None:
        return None
    for role in (roles.STEWARD, roles.MANAGER):
        found = _first_active(session, notices.holders(session, [role], org_unit_id))
        if found is not None:
            return found
    return None


def _owner_of(session: Session, app: Application) -> int | None:
    """Whoever answers for the application, or a steward of its unit, or a manager over it."""
    found = _first_active(session, notices.accountable(session, app.id))
    return found if found is not None else _keeper(session, app.org_unit_id)


def raise_task(
    session: Session, *, key: str, kind: str, title: str, reason: str, subject_type: str,
    subject_id: int, due_on: date, account_id: int | None, application: Application | None = None,
) -> Task | None:  # fmt: skip
    """Raise a task, unless this cause has raised one before."""
    if session.scalars(select(Task.id).where(Task.key == key)).first() is not None:
        return None
    task = Task(
        key=key, kind=kind, title=title[:300], reason=reason, subject_type=subject_type,
        subject_id=subject_id, application_id=application.id if application else None,
        org_unit_id=application.org_unit_id if application else None, account_id=account_id,
        due_on=due_on, status="open", raised_on=today(),
    )  # fmt: skip
    session.add(task)
    session.flush()
    notices.tell(session, account_id, "task", f"New task: {task.title}", f"/tasks/{task.id}")
    return task


def settle(session: Session, task: Task, why: str) -> None:
    task.status, task.closed_on = "done", today()
    task.closed_by_name, task.note = SYSTEM, why


# --- The triggers -----------------------------------------------------------------------------


def _contracts(session: Session, on: date, days: int) -> dict[str, dict[str, Any]]:
    from appwren.landscape.costs import notice_by

    wanted = {}
    for row in session.scalars(
        select(Contract).where(Contract.status == "active", Contract.ends_on.is_not(None))
    ):
        when = notice_by(row)
        if when is None or row.ends_on is None or row.ends_on < on or when > on + timedelta(days):
            continue
        renews = " It renews by itself unless notice is given." if row.auto_renews else ""
        wanted[f"contract_notice:{row.id}:{when.isoformat()}"] = {
            "kind": "contract_notice",
            "title": f"Decide whether {row.ref} {row.name} renews",
            "reason": f"Its term ends on {row.ends_on.isoformat()}, and notice is due by "
            f"{when.isoformat()}.{renews}",
            "subject_type": "contract", "subject_id": row.id, "due_on": when,
            "account_id": row.owner_id if _active(session, row.owner_id) else None,
        }  # fmt: skip
    return wanted


def _end_of_support(session: Session, on: date, days: int) -> dict[str, dict[str, Any]]:
    wanted = {}
    rows = session.execute(
        select(Application, TechnologyRelease, Technology)
        .join(Component, Component.application_id == Application.id)
        .join(ComponentTechnology, ComponentTechnology.component_id == Component.id)
        .join(TechnologyRelease, TechnologyRelease.id == ComponentTechnology.release_id)
        .join(Technology, Technology.id == TechnologyRelease.technology_id)
        .where(
            Component.status == "active",
            Application.status == "active",
            Application.lifecycle.not_in(NOT_IN_SERVICE),
            TechnologyRelease.support_ends.is_not(None),
            TechnologyRelease.support_ends <= on + timedelta(days),
            TechnologyRelease.support_ends >= on - PAST,
        )
    ).all()
    for app, release, tech in rows:
        ends = release.support_ends
        assert ends is not None
        key = f"end_of_support:{app.id}:{release.id}:{ends.isoformat()}"
        if key in wanted:
            continue
        verb = "ended" if ends < on else "ends"
        wanted[key] = {
            "kind": "end_of_support",
            "title": f"Plan for {tech.name} {release.cycle} in {app.ref} {app.name}",
            "reason": f"Support for {tech.name} {release.cycle} {verb} on {ends.isoformat()}, "
            f"and {app.name} runs on it.",
            "subject_type": "application", "subject_id": app.id, "due_on": ends,
            "account_id": _owner_of(session, app), "application": app,
        }  # fmt: skip
    return wanted


def _grants(session: Session, on: date, days: int) -> dict[str, dict[str, Any]]:
    ending: dict[int, tuple[date, str]] = {}
    low, high = on - PAST, on + timedelta(days)
    for app in session.scalars(
        select(Application).where(
            Application.status == "active",
            Application.lifecycle.not_in(NOT_IN_SERVICE),
            Application.grant_end.is_not(None),
        )
    ):
        assert app.grant_end is not None
        if low <= app.grant_end <= high:
            ending[app.id] = (app.grant_end, "its grant")
    for app_id, source in session.execute(
        select(CostLine.application_id, FundingSource)
        .join(FundingSource, FundingSource.id == CostLine.funding_source_id)
        .where(
            FundingSource.kind == "grant",
            FundingSource.status == "active",
            FundingSource.ends_on.is_not(None),
        )
    ):
        assert source.ends_on is not None
        if low <= source.ends_on <= high and app_id not in ending:
            ending[app_id] = (source.ends_on, f"{source.ref} {source.name}")
    wanted = {}
    apps = {
        app.id: app
        for app in session.scalars(
            select(Application).where(Application.id.in_(list(ending) or [0]))
        )
    }
    for app_id, (ends, what) in ending.items():
        app = apps[app_id]
        if app.lifecycle in NOT_IN_SERVICE:
            continue
        verb = "ended" if ends < on else "ends"
        wanted[f"grant_end:{app.id}:{ends.isoformat()}"] = {
            "kind": "grant_end",
            "title": f"Decide what becomes of {app.ref} {app.name} when its grant ends",
            "reason": f"It is paid for by {what}, which {verb} on {ends.isoformat()}. Record a "
            "decision: keep it on other money, or plan its end.",
            "subject_type": "application", "subject_id": app.id, "due_on": ends,
            "account_id": _owner_of(session, app), "application": app,
        }  # fmt: skip
    return wanted


def _departures(session: Session, on: date) -> dict[str, dict[str, Any]]:
    wanted = {}
    for app, owner in session.execute(
        select(Application, Account)
        .join(RecordOwner, RecordOwner.record_id == Application.id)
        .join(Account, Account.id == RecordOwner.account_id)
        .where(
            RecordOwner.record_type == "application",
            RecordOwner.kind == "accountable",
            Account.status == "disabled",
            Application.status == "active",
            Application.lifecycle.not_in(NOT_IN_SERVICE),
        )
    ):
        above = _keeper(session, app.org_unit_id)
        wanted[f"departure:{app.id}:{owner.id}"] = {
            "kind": "departure",
            "title": f"Name who is accountable for {app.ref} {app.name}",
            "reason": f"{owner.display_name}, who was accountable for it, has left.",
            "subject_type": "application", "subject_id": app.id, "due_on": on + timedelta(days=14),
            "account_id": above, "application": app,
        }  # fmt: skip
    return wanted


def _decided_since(session: Session, task: Task) -> bool:
    return (
        session.scalars(
            select(Decision.id).where(
                Decision.application_id == task.application_id,
                Decision.decided_on >= task.raised_on,
            )
        ).first()
        is not None
    )


SETTLED = {
    "contract_notice": "The contract's term changed, or it has ended.",
    "end_of_support": "Nothing of it runs on that release any more, or its support was extended.",
    "grant_end": "The grant's end date changed.",
    "departure": "Someone is accountable for it again.",
}


def run(session: Session, *, on: date | None = None) -> dict[str, int]:
    """Raise what is due and settle what is no longer. Safe to run at any time."""
    on = on or today()
    days = windows(session)
    wanted: dict[str, dict[str, Any]] = {
        **_contracts(session, on, days["contract_notice_days"]),
        **_end_of_support(session, on, days["end_of_support_days"]),
        **_grants(session, on, days["grant_end_days"]),
        **_departures(session, on),
    }
    raised = settled = 0
    for key, values in wanted.items():
        if raise_task(session, key=key, **values) is not None:
            raised += 1
    for task in session.scalars(select(Task).where(Task.status == "open")):
        if task.kind == "grant_end" and task.application_id and _decided_since(session, task):
            settle(session, task, "A decision on it was recorded.")
            settled += 1
        elif task.key not in wanted and task.kind in SETTLED:
            settle(session, task, SETTLED[task.kind])
            settled += 1
    session.flush()
    return {"tasks_raised": raised, "tasks_settled": settled}


def departure(session: Session, account_id: int) -> int:
    """When an account is disabled: a task at once for each application it was accountable
    for, rather than at the next turn of the scheduler."""
    found = 0
    for key, values in _departures(session, today()).items():
        if key.endswith(f":{account_id}") and raise_task(session, key=key, **values):
            found += 1
    return found


# --- Seeing and closing them ----------------------------------------------------------------


def _sees(session: Session, principal: Principal, task: Task) -> bool:
    if principal.account_id is not None and task.account_id == principal.account_id:
        return True
    if principal.reads_all:
        return True
    if task.application_id is not None:
        app = session.get(Application, task.application_id)
        if app is None or not access.sees_application(session, principal, app):
            return False
        return any(
            principal.covers(role, task.org_unit_id)
            for role in (roles.STEWARD, roles.LEADER, roles.MANAGER)
        )
    return False


def may_close(principal: Principal, task: Task) -> bool:
    if principal.account_id is not None and task.account_id == principal.account_id:
        return True
    if principal.manages:
        return True
    return task.org_unit_id is not None and (
        principal.covers(roles.STEWARD, task.org_unit_id)
        or principal.covers(roles.MANAGER, task.org_unit_id)
    )


def load(session: Session, principal: Principal, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None or not _sees(session, principal, task):
        raise NotFound("There is no such task.")
    return task


def close(session: Session, principal: Principal, task: Task, *, how: str, note: str) -> Task:
    """Mark a task done, or dismiss it, with a note."""
    if not may_close(principal, task):
        raise PermissionDenied(
            "Only whoever it is for, or a steward or manager over it, closes it."
        )
    if task.status != "open":
        raise Invalid("This task is already closed.")
    note = (note or "").strip()
    if not note:
        raise Invalid("The task was not closed.", {"note": "Say what was done, or why not."})
    who = session.get(Account, principal.account_id) if principal.account_id else None
    task.status = "done" if how == "done" else "dismissed"
    task.closed_on = today()
    task.closed_by_name = who.display_name if who else principal.actor.label
    task.note = note[:2000]
    session.flush()
    return task


def _href(session: Session, task: Task) -> str:
    if task.subject_type == "contract":
        contract = session.get(Contract, task.subject_id)
        return f"/contracts/{contract.ref}" if contract else "/contracts"
    app = session.get(Application, task.application_id) if task.application_id else None
    if app is None:
        return "/"
    return f"/applications/{app.ref}" + ("?tab=decisions" if task.kind == "grant_end" else "")


def view(session: Session, principal: Principal, task: Task) -> dict[str, Any]:
    about = None
    if task.subject_type == "contract":
        contract = session.get(Contract, task.subject_id)
        if contract is not None:
            about = {"ref": contract.ref, "name": contract.name, "type": "contract"}
    elif task.application_id is not None:
        app = session.get(Application, task.application_id)
        if app is not None:
            about = {"ref": app.ref, "name": app.name, "type": "application"}
    who = session.get(Account, task.account_id) if task.account_id else None
    return {
        "id": task.id,
        "kind": task.kind,
        "kind_label": KINDS.get(task.kind, task.kind),
        "title": task.title,
        "reason": task.reason,
        "about": about,
        "href": _href(session, task),
        "assignee": {"id": who.id, "name": who.display_name} if who else None,
        "due_on": task.due_on,
        "late": task.status == "open" and task.due_on < today(),
        "status": task.status,
        "raised_on": task.raised_on,
        "closed_on": task.closed_on,
        "closed_by": task.closed_by_name,
        "note": task.note,
        "mine": principal.account_id is not None and task.account_id == principal.account_id,
        "can_close": task.status == "open" and may_close(principal, task),
    }


def listing(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Tasks the person may see: by default, those still open. ``mine`` for their own,
    ``status`` for open, done, or dismissed, ``kind``, and ``unassigned``."""
    statement = select(Task).order_by(Task.due_on, Task.id)
    status = filters.get("status") or "open"
    if status != "all":
        statement = statement.where(Task.status == status)
    if filters.get("kind"):
        statement = statement.where(Task.kind == filters["kind"])
    if filters.get("mine") in (True, "1", "true"):
        statement = statement.where(Task.account_id == (principal.account_id or 0))
    if filters.get("unassigned") in (True, "1", "true"):
        statement = statement.where(Task.account_id.is_(None))
    rows = [row for row in session.scalars(statement) if _sees(session, principal, row)]
    return [view(session, principal, row) for row in rows]


def owed(session: Session, principal: Principal) -> list[dict[str, Any]]:
    if principal.account_id is None:
        return []
    rows = session.scalars(
        select(Task)
        .where(Task.status == "open", Task.account_id == principal.account_id)
        .order_by(Task.due_on)
    )
    return [view(session, principal, row) for row in rows]


def _due(session: Session, on: date, horizon: date) -> list[Any]:
    """Reminders: open tasks as their date comes and goes."""
    from appwren.reminders import Due

    return [
        Due(
            "task",
            task.id,
            task.due_on,
            task.title,
            f"/tasks/{task.id}",
            (task.account_id,),
            task.org_unit_id,
            escalates=task.org_unit_id is not None,
        )
        for task in session.scalars(
            select(Task).where(
                Task.status == "open", Task.account_id.is_not(None), Task.due_on <= horizon
            )
        )
    ]


def _register() -> None:
    from appwren import reminders

    if _due not in reminders.SOURCES:
        reminders.SOURCES.append(_due)


_register()
