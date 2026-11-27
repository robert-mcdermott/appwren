"""Reminders and escalation: what is nearly due or late, and who is told (CUR-04).

One pass looks at everything with a date on it: an assessment about to expire, a decision's
review date and its target date, and a contract's notice date. Later parts of the program add
their own dates through ``SOURCES``. Whoever a thing is waiting on is reminded shortly before
its date and again when it passes. If it stays late, the steward of its unit is told, and
later the unit's leader. Each of those is said once for a given date; moving the date starts
again.

A reminder is a notice, so it is read in the app and, where email is set up, sent as each
person has chosen. Nothing here changes a record.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.core.clock import add_months, today
from appwren.db.models import Account, Application, Assessment, Contract, Decision, Reminder
from appwren.engine.model import months_current
from appwren.people import notices

DEFAULTS = {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21}
STAGES = ("soon", "overdue", "steward", "leader")
NOT_IN_SERVICE = ("retired", "archived")
# A contract whose notice date passed this long ago is history, not a reminder.
CONTRACT_PAST = timedelta(days=30)


@dataclass(frozen=True)
class Due:
    """One thing with a date: what it is, who it waits on, and where to go."""

    kind: str
    id: int
    due_on: date
    what: str  # "APP-0012 Specimen Tracker", as it reads after "Due in 3 days: "
    href: str
    waiting_on: tuple[int, ...]
    unit_id: int | None
    escalates: bool = True
    late: str = "Overdue"  # how being past the date is said


def _model(session: Session) -> Mapping[str, Any]:
    from appwren.assessment import current_model
    from appwren.core.errors import Invalid

    try:
        return current_model(session).definition
    except Invalid:
        return {}


def schedule(session: Session, model: Mapping[str, Any] | None = None) -> dict[str, int]:
    """When reminders are sent, from the scoring model's cadence."""
    cadence = (model if model is not None else _model(session)).get("cadence") or {}
    found = cadence.get("reminders") or {}
    return {key: int(found.get(key, default)) for key, default in DEFAULTS.items()}


def _in_service(session: Session) -> dict[int, Application]:
    return {
        app.id: app
        for app in session.scalars(
            select(Application).where(Application.lifecycle.not_in(NOT_IN_SERVICE))
        )
    }


def _active(session: Session, account_id: int | None) -> bool:
    account = session.get(Account, account_id) if account_id else None
    return account is not None and account.status == "active"


def _assessments(session: Session, horizon: date, model: Mapping[str, Any]) -> Iterator[Due]:
    apps = _in_service(session)
    for row in session.scalars(
        select(Assessment).where(
            Assessment.superseded_by.is_(None), Assessment.application_id.in_(list(apps) or [0])
        )
    ):
        app = apps[row.application_id]
        expires = add_months(row.assessed_on, months_current(model, _tier(app)))
        if expires > horizon:
            continue
        yield Due(
            "assessment", row.id, expires, f"assessment of {app.ref} {app.name}",
            f"/applications/{app.ref}/assess", tuple(notices.accountable(session, app.id)),
            app.org_unit_id, late="Assessment expired",
        )  # fmt: skip


def _decisions(session: Session, horizon: date) -> Iterator[Due]:
    apps = _in_service(session)
    for row in session.scalars(
        select(Decision).where(
            Decision.superseded_by.is_(None), Decision.application_id.in_(list(apps) or [0])
        )
    ):
        app = apps[row.application_id]
        if row.review_on <= horizon:
            # The review is the decider's; if they have gone, the unit's leaders'.
            people = (
                (row.decided_by,)
                if row.decided_by is not None and _active(session, row.decided_by)
                else tuple(notices.holders(session, [roles.LEADER], app.org_unit_id))
                if app.org_unit_id is not None
                else ()
            )
            yield Due(
                "decision_review", row.id, row.review_on,
                f"review of the decision on {app.ref} {app.name}",
                f"/applications/{app.ref}?tab=decisions", people, app.org_unit_id,
                escalates=False, late="Review overdue",
            )  # fmt: skip
        if row.target_on is not None and row.target_on <= horizon:
            yield Due(
                "decision_target", row.id, row.target_on,
                f"{app.ref} {app.name}: {row.disposition.capitalize()}",
                f"/applications/{app.ref}?tab=decisions",
                tuple(notices.accountable(session, app.id)), app.org_unit_id,
                late="Past its target date",
            )  # fmt: skip


def _contracts(session: Session, on: date, horizon: date) -> Iterator[Due]:
    from appwren.landscape.costs import notice_by

    for row in session.scalars(
        select(Contract).where(Contract.status == "active", Contract.ends_on.is_not(None))
    ):
        when = notice_by(row)
        if (
            when is None
            or when > horizon
            or when < on - CONTRACT_PAST
            or (row.ends_on and row.ends_on < on)
        ):
            continue
        yield Due(
            "contract_notice", row.id, when, f"notice date of {row.ref} {row.name}",
            f"/contracts/{row.ref}", (row.owner_id,) if row.owner_id else (), None,
            escalates=False, late="Notice date passed",
        )  # fmt: skip


def _tier(app: Application) -> int | None:
    try:
        return int(app.tier) if app.tier else None
    except ValueError:
        return None


# Further sources of dates, added by later parts of the program: each yields what is due on
# or before the horizon.
SOURCES: list[Callable[[Session, date, date], Iterable[Due]]] = []


def due_items(session: Session, on: date, horizon: date) -> list[Due]:
    model = _model(session)
    found = [
        *_assessments(session, horizon, model),
        *_decisions(session, horizon),
        *_contracts(session, on, horizon),
    ]
    for source in SOURCES:
        found.extend(source(session, on, horizon))
    return found


def _when(days: int) -> str:
    if days == 0:
        return "today"
    return "tomorrow" if days == 1 else f"in {days} days"


def _late(days: int) -> str:
    return "1 day" if days == 1 else f"{days} days"


def stage_of(due: Due, on: date, plan: dict[str, int]) -> str | None:
    """How far along the reminders for this are: the furthest stage it has reached."""
    late = (on - due.due_on).days
    if late < 1:
        return "soon" if (due.due_on - on).days <= plan["soon_days"] else None
    if due.escalates and late >= plan["leader_after_days"]:
        return "leader"
    if due.escalates and late >= plan["steward_after_days"]:
        return "steward"
    return "overdue"


def send(session: Session, *, on: date | None = None) -> dict[str, int]:
    """Send every reminder that is due and has not been sent. Safe to run at any time: what
    has been said for a date is not said again."""
    on = on or today()
    plan = schedule(session)
    horizon = on + timedelta(days=plan["soon_days"])
    already = {
        (row.subject_type, row.subject_id, row.due_on, row.stage)
        for row in session.scalars(select(Reminder))
    }
    counts = {"reminders": 0, "overdue": 0, "escalated": 0}

    def tell(people: Iterable[int | None], kind: str, text: str, href: str) -> int:
        return notices.tell_all(session, people, kind, text, href)

    for due in due_items(session, on, horizon):
        stage = stage_of(due, on, plan)
        if stage is None or (due.kind, due.id, due.due_on, stage) in already:
            continue
        # Whatever this stage follows is taken as said: something found already three weeks
        # late is told to the leader once, and not also to everyone below in the same hour.
        for earlier in STAGES[: STAGES.index(stage) + 1]:
            key = (due.kind, due.id, due.due_on, earlier)
            if key not in already:
                already.add(key)
                session.add(
                    Reminder(
                        subject_type=due.kind,
                        subject_id=due.id,
                        due_on=due.due_on,
                        stage=earlier,
                        sent_on=on,
                    )
                )
        late = (on - due.due_on).days
        what = due.what[:300]
        if stage == "soon":
            counts["reminders"] += tell(
                due.waiting_on, "reminder", f"Due {_when(-late)}: {what}", due.href
            )
        elif stage == "overdue":
            counts["overdue"] += tell(
                due.waiting_on, "overdue", f"{due.late} by {_late(late)}: {what}", due.href
            )
        elif due.unit_id is not None:
            role = roles.STEWARD if stage == "steward" else roles.LEADER
            above = [
                each for each in notices.holders(session, [role], due.unit_id)
                if each not in due.waiting_on
            ]  # fmt: skip
            text = f"{due.late} by {_late(late)}, and now with you: {what}"
            counts["escalated"] += tell(above, "escalated", text, due.href)
    session.flush()
    return counts
