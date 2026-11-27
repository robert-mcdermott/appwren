"""Contesting a score: an owner says one factor is wrong, what it should be, and why, with a
link to the evidence; the portfolio team accepts it or answers it, and both stay on the
record (SCR-13).

A contest does not move a score. Scores come from the record and the assessment, and a
contest that is right is put right there: accepting one says so, and tells the owner where.
What a contest does is put the disagreement in front of the people who can settle it, with
the evidence, instead of in an email nobody can find a year later.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access import roles
from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import Account, Application, ScoreContest
from appwren.inventory import access
from appwren.inventory.records import Errors, url
from appwren.inventory.registry import APPLICATION
from appwren.people import notices


def may_raise(session: Session, principal: Principal, app: Application) -> bool:
    """Whoever keeps the application."""
    return access.can_edit(session, principal, APPLICATION, app)


def may_answer(principal: Principal, app: Application) -> bool:
    """The portfolio team: managers and architects over its unit."""
    return principal.covers(roles.MANAGER, app.org_unit_id) or principal.covers(
        roles.ARCHITECT, app.org_unit_id
    )


def _name(session: Session, principal: Principal) -> str:
    who = session.get(Account, principal.account_id) if principal.account_id else None
    return who.display_name if who else principal.actor.label


def raise_contest(
    session: Session, principal: Principal, app: Application, values: Mapping[str, Any]
) -> ScoreContest:
    if not may_raise(session, principal, app):
        raise PermissionDenied("Only someone who keeps this application contests its scores.")
    from appwren import assessment

    result = assessment.score_one(session, app)
    factors = {
        factor["key"]: (key, factor)
        for key, dimension in result["dimensions"].items()
        for factor in dimension["factors"]
    }
    errors = Errors()
    chosen = factors.get(str(values.get("factor") or ""))
    if chosen is None:
        errors.add("factor", "Choose the factor you say is wrong.")
    claimed = values.get("level_claimed")
    if claimed not in (None, ""):
        try:
            claimed = int(claimed)
        except (TypeError, ValueError):
            claimed = 0
        if not 1 <= claimed <= 5:
            errors.add("level_claimed", "A level is from 1 to 5, or leave it empty.")
    else:
        claimed = None
    note = str(values.get("note") or "").strip()
    if not note:
        errors.add("note", "Say why it is wrong. The person who answers will read it.")
    evidence = url(values.get("evidence_url"), "evidence_url", errors, max_length=500)
    if errors:
        raise Invalid("The contest was not recorded.", errors)
    assert chosen is not None
    dimension, factor = chosen
    row = ScoreContest(
        application_id=app.id, dimension=dimension, factor=factor["key"],
        factor_label=factor["label"], level_shown=factor.get("level"), level_claimed=claimed,
        note=note[:4000], evidence_url=evidence, raised_by=principal.account_id,
        raised_by_name=_name(session, principal), raised_on=today(), status="open",
    )  # fmt: skip
    session.add(row)
    session.flush()
    if app.org_unit_id is not None:
        notices.tell_all(
            session, notices.holders(session, [roles.MANAGER, roles.ARCHITECT], app.org_unit_id),
            "contest", f"{row.raised_by_name} contests {factor['label'].lower()} for "
            f"{app.ref} {app.name}", f"/applications/{app.ref}?tab=scores", by=principal,
        )  # fmt: skip
    return row


def answer(
    session: Session, principal: Principal, row: ScoreContest, *, accept: bool, text: str
) -> ScoreContest:
    app = session.get(Application, row.application_id)
    assert app is not None
    if not may_answer(principal, app):
        raise PermissionDenied("A manager or an architect over its unit answers a contest.")
    if row.status != "open":
        raise Invalid("This contest has already been answered.")
    text = (text or "").strip()
    if not text:
        raise Invalid(
            "The answer was not recorded.",
            {"answer": "Say what was decided, and, if it is accepted, what will be changed."},
        )
    row.status = "accepted" if accept else "answered"
    row.answer = text[:4000]
    row.answered_by_name = _name(session, principal)
    row.answered_on = today()
    session.flush()
    notices.tell(
        session, row.raised_by, "contest",
        f"{row.answered_by_name} {'accepted' if accept else 'answered'} your contest of "
        f"{row.factor_label.lower()} for {app.ref} {app.name}",
        f"/applications/{app.ref}?tab=scores", by=principal,
    )  # fmt: skip
    return row


def view(row: ScoreContest, principal: Principal, app: Application) -> dict[str, Any]:
    return {
        "id": row.id,
        "application": {"ref": app.ref, "name": app.name, "type": "application"},
        "dimension": row.dimension,
        "factor": row.factor,
        "factor_label": row.factor_label,
        "level_shown": row.level_shown,
        "level_claimed": row.level_claimed,
        "note": row.note,
        "evidence_url": row.evidence_url,
        "raised_by": row.raised_by_name,
        "raised_on": row.raised_on,
        "status": row.status,
        "answer": row.answer,
        "answered_by": row.answered_by_name,
        "answered_on": row.answered_on,
        "can_answer": row.status == "open" and may_answer(principal, app),
    }


def of_application(
    session: Session, principal: Principal, app: Application
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ScoreContest)
        .where(ScoreContest.application_id == app.id)
        .order_by(ScoreContest.raised_on.desc(), ScoreContest.id.desc())
    )
    return [view(row, principal, app) for row in rows]


def load(session: Session, principal: Principal, contest_id: int) -> ScoreContest:
    row = session.get(ScoreContest, contest_id)
    app = session.get(Application, row.application_id) if row else None
    if row is None or app is None or not access.sees_application(session, principal, app):
        raise NotFound("There is no such contest.")
    return row


def waiting(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Open contests this person may answer, oldest first."""
    if not (principal.manages_somewhere or principal.architects):
        return []
    out = []
    for row, app in session.execute(
        select(ScoreContest, Application)
        .join(Application, Application.id == ScoreContest.application_id)
        .where(ScoreContest.status == "open")
        .order_by(ScoreContest.raised_on, ScoreContest.id)
    ):
        if may_answer(principal, app) and access.sees_application(session, principal, app):
            out.append(view(row, principal, app))
    return out
