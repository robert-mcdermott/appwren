"""Decisions, mismatches, the portfolio as a whole, and portfolio snapshots (DEC-01 to
DEC-05, RPT-01, SCR-10).

A decision is a disposition recorded by a named person with the authority, with a rationale
and a date to look again (ADR-0011). It keeps the score snapshot it was made against. When
today's recommendation differs from the decision on record, the two are shown side by side
as a mismatch; the mismatch changes nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren import assessment
from appwren.access.principal import Principal
from appwren.core.clock import add_months, utc_now
from appwren.core.clock import today as today_
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.models import Application, Decision, PortfolioSnapshot, ScoreSnapshot
from appwren.db.refs import next_ref
from appwren.events import audit
from appwren.inventory import access, applications, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION
from appwren.program import catalog, vocab

NEEDS_SUCCESSOR = ("consolidate",)
YEAR = 365


def current(session: Session, application_ids: list[int]) -> dict[int, Decision]:
    if not application_ids:
        return {}
    rows = session.scalars(
        select(Decision).where(
            Decision.application_id.in_(application_ids), Decision.superseded_by.is_(None)
        )
    )
    return {row.application_id: row for row in rows}


def record(
    session: Session, principal: Principal, app: Application, values: Mapping[str, Any]
) -> Decision:
    """Record a disposition for an application. A manager may, or a leader of its unit; not
    its own accountable owner, unless the program lets owners decide, and then the decision
    says so. The scores as they are now are kept with it."""
    if not access.can_decide(session, principal, app):
        owners_may = catalog.decision_rules(session)["owners_may_decide"]
        if access.decides_own(session, principal, app) and not owners_may:
            raise PermissionDenied(
                "You are accountable for this application, so someone else records its decision."
            )
        raise PermissionDenied("Only a manager, or a leader of its unit, records a decision.")
    errors = Errors()
    on = today_()
    disposition = records.choice(
        session, "dispositions", values.get("disposition"), "disposition", errors, required=True
    )
    rationale = records.text(values.get("rationale"))
    if not rationale:
        errors.add("rationale", "Say why. The next person to look at it will want to know.")
    elif len(rationale) > 4000:
        errors.add("rationale", "Keep the rationale to 4,000 characters.")
    review_on = records.day(values.get("review_on"), "review_on", errors) or add_months(on, 12)
    if review_on <= on:
        errors.add("review_on", "The review date must be in the future.")
    target_on = records.day(values.get("target_on"), "target_on", errors)
    successor_id = records.reference(
        session, "application", values.get("successor"), "successor", errors, principal=principal
    )
    if successor_id == app.id:
        errors.add("successor", "An application cannot succeed itself.")
    if disposition in NEEDS_SUCCESSOR and successor_id is None:
        errors.add("successor", "Name the application its users will move to.")
    if errors:
        raise Invalid("The decision was not recorded.", errors)
    result = assessment.score_one(session, app, on=on)
    snapshot = assessment.take_snapshot(session, app, result, reason="decision")
    previous = current(session, [app.id]).get(app.id)
    with audit.operation(session, "decision.record"):
        row = Decision(
            ref=next_ref(session, "DEC"),
            application_id=app.id,
            disposition=disposition,
            rationale=rationale,
            target_on=target_on,
            review_on=review_on,
            successor_id=successor_id,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
            recommendation=result["recommendation"],
            decided_by=principal.account_id,
            decided_by_name=principal.name,
            decided_on=on,
            self_recorded=access.decides_own(session, principal, app),
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        if previous is not None:
            previous.superseded_by = row.id
        app.disposition, app.review_on = disposition, review_on
        if successor_id is not None:
            app.successor_id = successor_id
        records.touch(session, app)
    return row


def view(session: Session, row: Decision) -> dict[str, Any]:
    successor = session.get(Application, row.successor_id) if row.successor_id else None
    return {
        "ref": row.ref,
        "disposition": row.disposition,
        "rationale": row.rationale,
        "target_on": row.target_on,
        "review_on": row.review_on,
        "review_due": row.superseded_by is None and row.review_on < today_(),
        "successor": records.chip(APPLICATION, successor) if successor else None,
        "recommendation": row.recommendation,
        "differed": row.recommendation is not None and row.recommendation != row.disposition,
        "decided_by": row.decided_by_name,
        "decided_on": row.decided_on,
        "self_recorded": bool(row.self_recorded),
        "superseded": row.superseded_by is not None,
        "snapshot_id": row.snapshot_id,
    }


def history(session: Session, app: Application) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Decision).where(Decision.application_id == app.id).order_by(Decision.id.desc())
    ).all()
    return [view(session, row) for row in rows]


def snapshot_of(session: Session, principal: Principal, snapshot_id: int) -> dict[str, Any]:
    """A kept score, exactly as it was, and whether it is still what was recorded."""
    row = session.get(ScoreSnapshot, snapshot_id)
    if row is None:
        raise NotFound("There is no such snapshot.")
    app = session.get(Application, row.application_id)
    if app is None or not access.can_see(session, principal, APPLICATION, app):
        raise NotFound("There is no such snapshot.")
    working = row.working
    if not access.sees_sensitive(session, principal, app):
        working = assessment.redact(working, catalog.sensitive_fields(session))
    return {
        "id": row.id,
        "application": records.chip(APPLICATION, app),
        "taken_at": row.taken_at,
        "reason": row.reason,
        "intact": assessment.digest(row.working) == row.digest,
        "result": working,
    }


# --- The portfolio as a whole ------------------------------------------------------------------


def _decision_facts(session: Session, apps: list[Application]) -> dict[int, dict[str, Any]]:
    on = today_()
    found = current(session, [app.id for app in apps])
    out = {}
    for app_id, row in found.items():
        out[app_id] = {
            "decision": row.disposition,
            "decided_within_year": (on - row.decided_on) <= timedelta(days=YEAR),
            "decision_review_due": row.review_on < on,
        }
    return out


def portfolio(
    session: Session, principal: Principal, filters: Mapping[str, Any], *, keep: bool = False
) -> list[dict[str, Any]]:
    """Every application the person may see that matches the filters, with its scores,
    recommendation, decision, and flags. Cost is given only where they may see it."""
    from sqlalchemy import func

    conditions = records.conditions_for(session, principal, APPLICATION, filters)
    apps = list(
        session.scalars(
            select(Application).where(*conditions).order_by(func.lower(Application.name))
        )
    )
    scored = assessment.score_all(session, apps)
    withheld = assessment.withheld_flags(session)
    sensitive = set(access.sensitive_fields(session))
    decided = current(session, [app.id for app in apps])
    owners = records.owners_of(session, APPLICATION, [app.id for app in apps])
    rows = []
    for app in apps:
        result = scored[app.id]
        people = owners.get(app.id, [])
        is_named = principal.account_id is not None and any(
            person["account_id"] == principal.account_id for person in people
        )
        sees = access.sees_sensitive(session, principal, app, is_named=is_named)
        decision = decided.get(app.id)
        recommendation = result["recommendation"]
        flags = assessment.shown_flags(result["flags"], sees, withheld)

        def told(name: str, value: Any, sees: bool = sees) -> Any:
            # A field the program marks sensitive is withheld here as on the record (review
            # of wave 9, finding 3).
            return value if sees or name not in sensitive else "withheld"

        rows.append(
            {
                **records.chip(APPLICATION, app),
                "org_unit_id": app.org_unit_id,
                "lifecycle": app.lifecycle,
                "sourcing": told("sourcing", app.sourcing),
                "domain": told("domain", app.domain),
                "tier": told("tier", app.tier),
                "scores": result["scores"],
                "thin": {k: d["thin"] for k, d in result["dimensions"].items()},
                "confidence": result["confidence"],
                "recommendation": recommendation,
                "decision": decision.disposition if decision else None,
                "review_on": decision.review_on if decision else None,
                "self_decided": bool(decision and decision.self_recorded),
                "mismatch": bool(
                    decision and recommendation and decision.disposition != recommendation
                ),
                "flags": [f["key"] for f in flags],
                "flag_texts": {f["key"]: f["text"] for f in flags},
                "annual_cost": app.annual_cost if sees else "withheld",
                "accountable": [p["name"] for p in records.accountable(people)],
                **({"id": app.id, "_result": result, "_app": app} if keep else {}),
            }
        )  # fmt: skip
    return rows


def take_portfolio_snapshot(session: Session, principal: Principal, name: str) -> PortfolioSnapshot:
    """Keep every active application's scores together, for a review or a period's end."""
    if not principal.manages:
        raise PermissionDenied("Only a manager takes a portfolio snapshot.")
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise Invalid("The snapshot was not taken.", {"name": "Give it a name, such as 2026 Q4."})
    apps = list(session.scalars(select(Application).where(Application.status == "active")))
    scored = assessment.score_all(session, apps)
    model = assessment.current_model(session)
    digest = hashlib.sha256()
    with audit.operation(session, "portfolio.snapshot"):
        row = PortfolioSnapshot(
            ref=next_ref(session, "PSN"),
            name=name,
            taken_at=utc_now(),
            taken_by=principal.account_id,
            taken_by_name=principal.name,
            model_id=model.id,
            count=len(apps),
        )
        session.add(row)
        session.flush()
        for app in apps:
            kept = assessment.take_snapshot(
                session, app, scored[app.id], reason="portfolio", portfolio_snapshot_id=row.id
            )
            digest.update(kept.digest.encode())
        audit.record(
            session, "portfolio.snapshot.digest", row, changes={"digest": digest.hexdigest()}
        )
    return row


def take_monthly(session: Session) -> int:
    """The portfolio as it stood this month, kept by the scheduler once a month: on the first
    turn after the month begins. Returns how many it took: none, or one."""
    on = today_()
    name = f"{on:%B %Y}, monthly"
    if session.scalars(select(PortfolioSnapshot.id).where(PortfolioSnapshot.name == name)).first():
        return 0
    if (
        session.scalars(select(Application.id).where(Application.status == "active")).first()
        is None
    ):
        return 0
    take_portfolio_snapshot(session, Principal.for_command("Scheduler"), name)
    return 1


def portfolio_snapshots(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(PortfolioSnapshot).order_by(PortfolioSnapshot.id.desc())).all()
    return [
        {"ref": row.ref, "name": row.name, "taken_at": row.taken_at, "taken_by": row.taken_by_name,
         "count": row.count, "model_id": row.model_id}
        for row in rows
    ]  # fmt: skip


def portfolio_snapshot(session: Session, principal: Principal, ref: str) -> dict[str, Any]:
    row = session.scalars(
        select(PortfolioSnapshot).where(PortfolioSnapshot.ref == ref.upper())
    ).first()
    if row is None:
        raise NotFound(f"There is no snapshot {ref}.")
    kept = session.execute(
        select(ScoreSnapshot, Application)
        .join(Application, Application.id == ScoreSnapshot.application_id)
        .where(ScoreSnapshot.portfolio_snapshot_id == row.id)
        .order_by(Application.name)
    ).all()
    out = []
    for snap, app in kept:
        if not access.can_see(session, principal, APPLICATION, app):
            continue
        out.append(
            {**records.chip(APPLICATION, app), "snapshot_id": snap.id,
             "scores": {"business_value": snap.bv, "technical_health": snap.th,
                        "cost_burden": snap.cb, "risk_exposure": snap.re},
             "confidence": snap.confidence, "recommendation": snap.recommendation,
             "flags": snap.flags}
        )  # fmt: skip
    return {"ref": row.ref, "name": row.name, "taken_at": row.taken_at,
            "taken_by": row.taken_by_name, "count": row.count, "rows": out}  # fmt: skip


def _has_decision(session: Session, app: Application) -> bool:
    return app.id in current(session, [app.id])


assessment.EXTRA_FACTS.append(_decision_facts)
applications.HAS["decision"] = _has_decision
APPLICATION.extra.setdefault("history_vocabularies", {})["disposition"] = "dispositions"

_ = vocab  # the dispositions vocabulary is read through records.choice


def _with_decision() -> None:
    """An application's page shows the decision on record, and whether the reader may
    record one."""
    original = APPLICATION.extra.get("detail")

    def detail(
        session: Session, principal: Principal, app: Application, shown: Mapping[str, Any]
    ) -> dict[str, Any]:
        out = original(session, principal, app, shown) if original else {}
        row = current(session, [app.id]).get(app.id)
        out["decision"] = view(session, row) if row else None
        out["can"] = {**shown.get("can", {}), "decide": access.can_decide(session, principal, app),
                      "assess": access.can_assess(session, principal, app)}  # fmt: skip
        return out

    APPLICATION.extra["detail"] = detail


_with_decision()
