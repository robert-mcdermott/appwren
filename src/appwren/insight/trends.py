"""Trends: how the portfolio moved between two portfolio snapshots, and an application's
scores over time (RPT-04).

A portfolio snapshot keeps every scored application's scores, recommendation, confidence, and
flags as they were. Two of them, side by side, say what moved: the figures each held, the
applications whose recommendation changed, whose scores rose or fell by half a point or more,
and whose flags came or went, and the decisions recorded between them. Nothing here is
worked out again from the records as they are now, except the column for today.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid, NotFound
from appwren.db.models import Application, Decision, PortfolioSnapshot, ScoreSnapshot
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION

DIMENSIONS = {"bv": "business_value", "th": "technical_health", "cb": "cost_burden",
              "re": "risk_exposure"}  # fmt: skip
MOVED = 0.5  # a score that moved by this much or more is listed
LOW = 70  # confidence below this is low


def _snapshot(session: Session, ref: str) -> PortfolioSnapshot:
    row = session.scalars(
        select(PortfolioSnapshot).where(PortfolioSnapshot.ref == ref.strip().upper())
    ).first()
    if row is None:
        raise NotFound(f"There is no snapshot {ref}.")
    return row


def _held(
    session: Session, principal: Principal, snapshot: PortfolioSnapshot
) -> dict[int, tuple[ScoreSnapshot, Application]]:
    rows = session.execute(
        select(ScoreSnapshot, Application)
        .join(Application, Application.id == ScoreSnapshot.application_id)
        .where(ScoreSnapshot.portfolio_snapshot_id == snapshot.id)
    )
    return {app.id: (snap, app) for snap, app in rows
            if access.sees_application(session, principal, app)}  # fmt: skip


def _figures(held: list[dict[str, Any]]) -> dict[str, Any]:
    """The figures a set of scored applications gives: how many, by recommendation, with low
    confidence, with each flag, and each score's average."""
    scored = len(held)
    out: dict[str, Any] = {
        "scored": scored,
        "low_confidence": sum(1 for item in held if item["confidence"] < LOW),
        "recommendations": dict(
            Counter(item["recommendation"] for item in held if item["recommendation"])
        ),
        "flags": dict(Counter(flag for item in held for flag in item["flags"])),
        "averages": {},
    }
    for dimension in DIMENSIONS.values():
        values = [item["scores"][dimension] for item in held
                  if item["scores"].get(dimension) is not None]  # fmt: skip
        out["averages"][dimension] = round(sum(values) / len(values), 2) if values else None
    return out


def _item(snap: ScoreSnapshot) -> dict[str, Any]:
    return {
        "scores": {name: getattr(snap, short) for short, name in DIMENSIONS.items()},
        "recommendation": snap.recommendation,
        "confidence": snap.confidence,
        "flags": list(snap.flags or []),
    }


def _decided(
    session: Session, principal: Principal, start: datetime | None, end: datetime | None
) -> list[dict[str, Any]]:
    statement = select(Decision, Application).join(
        Application, Application.id == Decision.application_id
    )
    if start is not None:
        statement = statement.where(Decision.created_at > start)
    if end is not None:
        statement = statement.where(Decision.created_at <= end)
    return [
        {**records.chip(APPLICATION, app), "decision": row.ref, "disposition": row.disposition,
         "recommendation": row.recommendation, "decided_on": row.decided_on,
         "by": row.decided_by_name}
        for row, app in session.execute(statement.order_by(Decision.created_at))
        if access.sees_application(session, principal, app)
    ]  # fmt: skip


def compare(
    session: Session, principal: Principal, before_ref: str, after_ref: str | None = None
) -> dict[str, Any]:
    """Two snapshots side by side, the later one ``after_ref`` (or today's scores, if none):
    the figures each held, and what moved between them."""
    before = _snapshot(session, before_ref)
    then = _held(session, principal, before)
    if after_ref:
        after = _snapshot(session, after_ref)
        if after.taken_at <= before.taken_at:
            raise Invalid("Nothing was compared.", {"after": "Choose a later snapshot."})
        later = {app_id: (_item(snap), app) for app_id, (snap, app) in
                 _held(session, principal, after).items()}  # fmt: skip
        end = after.taken_at
        label = {"ref": after.ref, "name": after.name, "taken_at": after.taken_at}
    else:
        from appwren.assessment import score_all
        from appwren.insight.shares import IN_SERVICE

        apps = [app for app in session.scalars(
            select(Application).where(Application.status == "active",
                                      Application.lifecycle.in_(IN_SERVICE))
        ) if access.sees_application(session, principal, app)]  # fmt: skip
        found = score_all(session, apps) if apps else {}
        later = {
            app.id: ({"scores": found[app.id]["scores"],
                      "recommendation": found[app.id]["recommendation"],
                      "confidence": found[app.id]["confidence"],
                      "flags": [flag["key"] for flag in found[app.id]["flags"]]}, app)
            for app in apps if app.status == "active"
        }  # fmt: skip
        end = None
        label = {"ref": None, "name": "Today", "taken_at": None}
    earlier = {app_id: (_item(snap), app) for app_id, (snap, app) in then.items()}
    moved: dict[str, list[dict[str, Any]]] = {"recommendation": [], "scores": [], "flags": []}
    for app_id, (was, app) in sorted(earlier.items(), key=lambda pair: pair[1][1].name):
        if app_id not in later:
            continue
        now = later[app_id][0]
        chip = records.chip(APPLICATION, app)
        if was["recommendation"] != now["recommendation"]:
            moved["recommendation"].append({**chip, "from": was["recommendation"],
                                            "to": now["recommendation"]})  # fmt: skip
        changes = {}
        for dimension in DIMENSIONS.values():
            a, b = was["scores"].get(dimension), now["scores"].get(dimension)
            if a is not None and b is not None and abs(b - a) >= MOVED:
                changes[dimension] = {"from": a, "to": b}
        if changes:
            moved["scores"].append({**chip, "changes": changes})
        came = sorted(set(now["flags"]) - set(was["flags"]))
        went = sorted(set(was["flags"]) - set(now["flags"]))
        if came or went:
            moved["flags"].append({**chip, "raised": came, "cleared": went})
    return {
        "before": {"ref": before.ref, "name": before.name, "taken_at": before.taken_at,
                   "figures": _figures([item for item, _ in earlier.values()])},
        "after": {**label, "figures": _figures([item for item, _ in later.values()])},
        "moved": moved,
        "added": [records.chip(APPLICATION, app) for app_id, (_, app) in later.items()
                  if app_id not in earlier],
        "gone": [records.chip(APPLICATION, app) for app_id, (_, app) in earlier.items()
                 if app_id not in later],
        "decided": _decided(session, principal, before.taken_at, end),
        "threshold": MOVED,
    }  # fmt: skip


def over_time(session: Session, principal: Principal, app: Application) -> list[dict[str, Any]]:
    """Every score snapshot of an application, oldest first: from each portfolio snapshot and
    each decision."""
    rows = session.scalars(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.application_id == app.id)
        .order_by(ScoreSnapshot.taken_at, ScoreSnapshot.id)
    )
    return [{"taken_at": snap.taken_at, "reason": snap.reason, **_item(snap)} for snap in rows]
