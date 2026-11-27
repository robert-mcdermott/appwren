"""Leadership reports: a period's report, worked out once and kept whole (RPT-05).

A manager makes a report for a period, often a quarter. AppWren works it out then, from the
records as they are, and stores every figure and list in it; reopening it reads what was
stored, so a report read a year on says what it said the day it was made. Its digest, the
SHA-256 of its canonical form, is shown with it and checked each time it is opened.

What it holds: where the portfolio stood when it was made (the dashboard's figures, its cost
for those who see every cost, and its maturity), and what happened in the period: decisions,
closed reviews, initiatives under way and done, requests, retirements and their savings, and
how the scores moved between the period's snapshots.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import isoformat, today, utc_now
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db import refs
from appwren.db.models import (
    Application,
    Decision,
    Initiative,
    PortfolioSnapshot,
    Report,
    Request,
    Retirement,
    Review,
    ReviewItem,
)
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION, INITIATIVE, REVIEW
from appwren.program import vocab


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return isoformat(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"{type(value).__name__} is not kept in a report")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_plain)


def digest_of(title: str, period_from: date, period_to: date, content: dict[str, Any]) -> str:
    whole = {"title": title, "from": period_from.isoformat(), "to": period_to.isoformat(),
             "content": content}  # fmt: skip
    return hashlib.sha256(canonical(whole).encode()).hexdigest()


def _counts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"label": item["label"], "count": item["count"],
             **({"key": item["key"]} if "key" in item else {}),
             **({"severity": item["severity"]} if "severity" in item else {})}
            for item in items]  # fmt: skip


def _portfolio(session: Session, principal: Principal) -> dict[str, Any]:
    from appwren import reporting
    from appwren.inventory import maturity

    board = reporting.dashboard(session, principal, {})
    grown = maturity.report(session, principal)
    cost = board.get("costs")
    return {
        "total": board["total"]["count"],
        "headline": _counts(board["headline"]),
        "recommendations": _counts(board["recommendations"]),
        "decisions": _counts(board["decisions"]),
        "lifecycle": _counts(board["lifecycle"]),
        "flags": _counts(board["flags"]),
        "cost": cost["total"] if cost else None,
        "maturity": {"levels": [list(pair) for pair in grown["levels"]],
                     "counts": grown["all"]["counts"]},
    }  # fmt: skip


def _decided(session: Session, principal: Principal, start: date, end: date) -> dict[str, Any]:
    labels = vocab.labels(session, "dispositions")
    items = [
        {**records.chip(APPLICATION, app), "decision": row.ref, "disposition": row.disposition,
         "recommendation": row.recommendation, "decided_on": row.decided_on,
         "by": row.decided_by_name}
        for row, app in session.execute(
            select(Decision, Application)
            .join(Application, Application.id == Decision.application_id)
            .where(Decision.decided_on >= start, Decision.decided_on <= end)
            .order_by(Decision.decided_on, Decision.id)
        )
        if access.sees_application(session, principal, app)
    ]  # fmt: skip
    tally = Counter(item["disposition"] for item in items)
    return {
        "count": len(items),
        "by_disposition": [{"key": key, "label": labels.get(key, key), "count": tally[key]}
                           for key in vocab.keys(session, "dispositions") if tally.get(key)],
        "against_recommendation": sum(1 for item in items
                                      if item["recommendation"] not in (None, item["disposition"])),
        "items": items,
    }  # fmt: skip


def _within(moment: datetime | None, start: date, end: date) -> bool:
    return moment is not None and start <= moment.date() <= end


def _reviews(session: Session, start: date, end: date) -> list[dict[str, Any]]:
    out = []
    for review in session.scalars(select(Review).order_by(Review.held_on)):
        if not _within(review.closed_at, start, end):
            continue
        items = session.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)).all()
        out.append({**records.chip(REVIEW, review), "held_on": review.held_on,
                    "items": len(items),
                    "decided": sum(1 for item in items if item.taken_decision_id)})  # fmt: skip
    return out


def _initiatives(session: Session, end: date) -> dict[str, Any]:
    kinds = vocab.labels(session, "initiative_kinds")
    under_way, done = [], []
    for row in session.scalars(select(Initiative).order_by(Initiative.ends_on, Initiative.ref)):
        if row.status != "active":
            continue
        item = {**records.chip(INITIATIVE, row), "kind": kinds.get(row.kind, row.kind),
                "starts_on": row.starts_on, "ends_on": row.ends_on,
                "budget": row.budget}  # fmt: skip
        if row.stage == "in_progress":
            under_way.append({**item, "late": bool(row.ends_on and row.ends_on < end)})
        elif row.stage == "done":
            done.append(item)
    return {"under_way": under_way, "late": sum(1 for item in under_way if item["late"]),
            "done": done}  # fmt: skip


def _requests(session: Session, start: date, end: date) -> dict[str, Any]:
    rows = session.scalars(select(Request).where(Request.status == "active")).all()
    ended = Counter(row.state for row in rows if _within(row.outcome_at, start, end))
    return {
        "opened": sum(1 for row in rows if _within(row.created_at, start, end)),
        "approved": ended["approved"], "met": ended["met"], "declined": ended["declined"],
        "open": sum(1 for row in rows if row.state in ("submitted", "evaluating")),
    }  # fmt: skip


def _retirements(session: Session, principal: Principal, start: date, end: date) -> dict:
    from appwren.landscape import costs

    done = []
    for plan, app in session.execute(
        select(Retirement, Application)
        .join(Application, Application.id == Retirement.application_id)
        .where(Retirement.completed_on >= start, Retirement.completed_on <= end)
        .order_by(Retirement.completed_on)
    ):
        if access.sees_application(session, principal, app):
            saved = plan.savings if costs.sees_cost(session, principal, app) else None
            done.append({**records.chip(APPLICATION, app), "completed_on": plan.completed_on,
                         "savings": saved})  # fmt: skip
    return {"completed": done, "savings": sum(item["savings"] or 0 for item in done)}


def _movement(session: Session, principal: Principal, start: date, end: date) -> dict | None:
    """How the scores moved: from the last snapshot before the period (or its first) to its
    last. None without two snapshots to compare."""
    from appwren.insight import trends

    taken = session.scalars(select(PortfolioSnapshot).order_by(PortfolioSnapshot.taken_at)).all()
    inside = [snap for snap in taken if start <= snap.taken_at.date() <= end]
    earlier = [snap for snap in taken if snap.taken_at.date() < start]
    if not inside:
        return None
    before = earlier[-1] if earlier else inside[0]
    after = inside[-1]
    if before.id == after.id:
        return None
    found = trends.compare(session, principal, before.ref, after.ref)
    moved = found["moved"]
    return {
        "before": {key: found["before"][key] for key in ("ref", "name", "taken_at", "figures")},
        "after": {key: found["after"][key] for key in ("ref", "name", "taken_at", "figures")},
        "recommendation_changed": len(moved["recommendation"]),
        "scores_moved": len(moved["scores"]),
        "flags_raised": sum(len(item["raised"]) for item in moved["flags"]),
        "flags_cleared": sum(len(item["cleared"]) for item in moved["flags"]),
        "added": len(found["added"]),
        "threshold": found["threshold"],
    }


def compose(session: Session, principal: Principal, start: date, end: date) -> dict[str, Any]:
    """A period's report as it would be made now: plain values only, as it is stored."""
    content = {
        "portfolio": _portfolio(session, principal),
        "decided": _decided(session, principal, start, end),
        "reviews": _reviews(session, start, end),
        "initiatives": _initiatives(session, end),
        "requests": _requests(session, start, end),
        "retirements": _retirements(session, principal, start, end),
        "movement": _movement(session, principal, start, end),
    }
    return json.loads(canonical(content))


def _date(value: Any, field: str, errors: dict[str, str]) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        errors[field] = "Give a date."
        return None


def make(session: Session, principal: Principal, values: dict[str, Any]) -> Report:
    """Work out a report for a period and keep it. Only a manager makes one."""
    if not principal.manages:
        raise PermissionDenied("Only a manager makes a leadership report.")
    errors: dict[str, str] = {}
    title = str(values.get("title") or "").strip()
    if not title or len(title) > 200:
        errors["title"] = "Give it a title of up to 200 characters."
    start = _date(values.get("period_from"), "period_from", errors)
    end = _date(values.get("period_to"), "period_to", errors)
    if start and end and end < start:
        errors["period_to"] = "The period ends on or after it starts."
    if end and end > today():
        errors["period_to"] = "A report covers a period that has ended, up to today."
    if errors or start is None or end is None:
        raise Invalid("The report was not made.", errors)
    content = compose(session, principal, start, end)
    row = Report(
        ref=refs.next_ref(session, "RPT"), title=title, period_from=start, period_to=end,
        content=content, digest=digest_of(title, start, end, content), made_at=utc_now(),
        made_by=principal.account_id, made_by_name=principal.name,
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


def _readable(principal: Principal) -> None:
    if not principal.reads_all:
        raise PermissionDenied("Leadership reports are for those who may see every record.")


def load(session: Session, principal: Principal, ref: str) -> Report:
    _readable(principal)
    row = session.scalars(select(Report).where(Report.ref == ref.strip().upper())).first()
    if row is None:
        raise NotFound(f"There is no report {ref}.")
    return row


def _summary(row: Report) -> dict[str, Any]:
    return {"ref": row.ref, "title": row.title, "period_from": row.period_from,
            "period_to": row.period_to, "made_at": row.made_at, "made_by": row.made_by_name,
            "digest": row.digest}  # fmt: skip


def listing(session: Session, principal: Principal) -> list[dict[str, Any]]:
    _readable(principal)
    rows = session.scalars(select(Report).order_by(Report.period_to.desc(), Report.id.desc()))
    return [_summary(row) for row in rows]


def view(row: Report) -> dict[str, Any]:
    """The report as it was made, and whether it is still exactly that."""
    worked = digest_of(row.title, row.period_from, row.period_to, row.content)
    return {**_summary(row), "content": row.content, "intact": worked == row.digest}
