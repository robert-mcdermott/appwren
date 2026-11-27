"""Portfolio reviews: an agenda drawn from what needs deciding in a scope, the decisions taken,
and a record of them once closed (PLN-01).

A review has a scope (a unit and everything beneath it, narrowed by tier), a date, and a
chair. It is planned, then opened, then closed. Its agenda is drawn from the scope: the
applications whose decision on record differs from today's recommendation, whose decision falls
due for review by the review's date, or that have no decision; items can be added and removed
by hand until it closes. A review does not change what a decision is or who may record one: a
decision recorded while it is open is an ordinary decision, shown on its item, and kept there
when the review closes. A closed review changes no more.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import Account, Application, Decision, Review, ReviewItem
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION, REVIEW
from appwren.people import units

REASONS = {
    "mismatch": "The decision on record differs from today's recommendation",
    "review_due": "Its decision is due for review",
    "undecided": "No decision is on record",
    "added": "Added by hand",
}
IN_SERVICE = {"evaluating", "phase_in", "active", "containment", "phase_out"}


def runs(principal: Principal, org_unit_id: int | None) -> bool:
    """Managers over the unit, and its leaders, run its reviews."""
    return principal.manages_unit(org_unit_id) or principal.leads_unit(org_unit_id)


def _can_add(session: Session, principal: Principal, record: Review) -> bool:
    return runs(principal, record.org_unit_id)


def _can_edit(session: Session, principal: Principal, record: Review) -> bool:
    return record.state != "closed" and runs(principal, record.org_unit_id)


def _new(record: Review) -> None:
    record.state, record.tiers = "planned", []


def _apply(
    session: Session, record: Review, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if not creating and record.state == "closed":
        errors.add("state", "A closed review changes no more.")


def _scope(session: Session, review: Review) -> list[Application]:
    unit_ids = units.with_descendants(session, [review.org_unit_id]) if review.org_unit_id else None
    statement = select(Application).where(
        Application.status == "active", Application.lifecycle.in_(IN_SERVICE)
    )
    if unit_ids is not None:
        statement = statement.where(Application.org_unit_id.in_(unit_ids))
    if review.tiers:
        statement = statement.where(Application.tier.in_(review.tiers))
    return list(session.scalars(statement.order_by(Application.name)))


def _require(session: Session, principal: Principal, review: Review) -> None:
    if not runs(principal, review.org_unit_id):
        raise PermissionDenied("Only a manager or a leader over its unit runs a review.")
    if review.state == "closed":
        raise Conflict("The review is closed, and changes no more.")


def _next_position(session: Session, review: Review) -> int:
    found = session.scalars(
        select(func.max(ReviewItem.position)).where(ReviewItem.review_id == review.id)
    ).first()
    return (found or 0) + 1


def draw(session: Session, principal: Principal, review: Review) -> int:
    """Add to the agenda what needs deciding in the scope now. What is already on it stays.
    Returns how many were added."""
    from appwren.assessment import score_all

    _require(session, principal, review)
    apps = [app for app in _scope(session, review)
            if access.sees_application(session, principal, app)]  # fmt: skip
    have = set(
        session.scalars(select(ReviewItem.application_id).where(ReviewItem.review_id == review.id))
    )
    scored = score_all(session, [app for app in apps if app.id not in have])
    position = _next_position(session, review)
    added = 0
    for app in apps:
        if app.id in have:
            continue
        result = scored[app.id]
        recommendation = result["recommendation"]
        mismatch = any(flag["key"] == "mismatch" for flag in result["flags"])
        if app.disposition and mismatch:
            reason = "mismatch"
        elif app.disposition and app.review_on and app.review_on <= review.held_on:
            reason = "review_due"
        elif not app.disposition and recommendation:
            reason = "undecided"
        else:
            continue
        session.add(ReviewItem(review_id=review.id, application_id=app.id, position=position,
                               reason=reason, recommendation=recommendation,
                               disposition=app.disposition))  # fmt: skip
        position += 1
        added += 1
    session.flush()
    return added


def add_item(
    session: Session, principal: Principal, review: Review, ref: str, note: str | None
) -> ReviewItem:
    from appwren.assessment import score_one

    _require(session, principal, review)
    app = records.load(session, principal, APPLICATION, ref)
    if session.scalars(
        select(ReviewItem.id).where(
            ReviewItem.review_id == review.id, ReviewItem.application_id == app.id
        )
    ).first():
        raise Conflict(f"{app.name} is already on the agenda.")
    said = (note or "").strip()[:2000] or None
    row = ReviewItem(review_id=review.id, application_id=app.id,
                     position=_next_position(session, review), reason="added",
                     recommendation=score_one(session, app)["recommendation"],
                     disposition=app.disposition, note=said)  # fmt: skip
    session.add(row)
    session.flush()
    return row


def remove_item(session: Session, principal: Principal, review: Review, item_id: int) -> None:
    _require(session, principal, review)
    row = session.get(ReviewItem, item_id)
    if row is None or row.review_id != review.id:
        raise NotFound("That is not on the agenda.")
    session.delete(row)
    session.flush()


def open_review(session: Session, principal: Principal, review: Review) -> Review:
    _require(session, principal, review)
    if review.state == "open":
        raise Conflict("The review is already open.")
    review.state, review.opened_at = "open", utc_now()
    records.touch(session, review)
    session.flush()
    return review


def _taken(session: Session, review: Review, app_ids: list[int]) -> dict[int, Decision]:
    """For each application, the latest decision recorded while the review was open."""
    if review.opened_at is None or not app_ids:
        return {}
    until = review.closed_at or utc_now()
    statement = select(Decision).where(
        Decision.application_id.in_(app_ids),
        Decision.created_at >= review.opened_at,
        Decision.created_at <= until,
    )
    found: dict[int, Decision] = {}
    for row in session.scalars(statement.order_by(Decision.created_at)):
        found[row.application_id] = row
    return found


def close_review(session: Session, principal: Principal, review: Review) -> Review:
    """Close it: each item keeps the decision taken on it, and nothing changes after."""
    _require(session, principal, review)
    if review.state != "open":
        raise Invalid("The review was not closed.", {"state": "Open the review first."})
    review.state, review.closed_at, review.closed_by_name = "closed", utc_now(), principal.name
    items = list(session.scalars(select(ReviewItem).where(ReviewItem.review_id == review.id)))
    taken = _taken(session, review, [item.application_id for item in items])
    for item in items:
        decision = taken.get(item.application_id)
        item.taken_decision_id = decision.id if decision else None
    records.touch(session, review)
    session.flush()
    return review


def agenda(session: Session, principal: Principal, review: Review) -> dict[str, Any]:
    """The agenda as the person may see it, with each item's recommendation and decision on
    record then, the decision on record now, and the decision taken in the review."""
    from appwren.assessment import score_all

    rows = list(
        session.execute(
            select(ReviewItem, Application)
            .join(Application, Application.id == ReviewItem.application_id)
            .where(ReviewItem.review_id == review.id)
            .order_by(ReviewItem.position, ReviewItem.id)
        )
    )
    seen = [(item, app) for item, app in rows if access.sees_application(session, principal, app)]
    apps = [app for _, app in seen]
    scored = score_all(session, apps) if apps and review.state != "closed" else {}
    if review.state == "closed":
        ids = {item.taken_decision_id for item, _ in seen if item.taken_decision_id}
        taken = {row.application_id: row for row in session.scalars(
            select(Decision).where(Decision.id.in_(ids)))} if ids else {}  # fmt: skip
    else:
        taken = _taken(session, review, [app.id for app in apps])
    items = []
    for item, app in seen:
        decision = taken.get(app.id)
        now = scored.get(app.id)
        items.append({
            "id": item.id,
            "application": records.chip(APPLICATION, app),
            "tier": app.tier,
            "reason": item.reason,
            "reason_label": REASONS[item.reason],
            "note": item.note,
            "recommendation": item.recommendation,
            "disposition": item.disposition,
            "recommendation_now": now["recommendation"] if now else None,
            "disposition_now": app.disposition,
            "review_on": app.review_on,
            "taken": {"ref": decision.ref, "disposition": decision.disposition,
                      "by": decision.decided_by_name, "on": decision.decided_on,
                      "rationale": decision.rationale} if decision else None,
        })  # fmt: skip
    decided = sum(1 for item in items if item["taken"])
    return {"items": items, "hidden": len(rows) - len(seen), "decided": decided,
            "waiting": len(items) - decided}  # fmt: skip


def _detail(
    session: Session, principal: Principal, record: Review, shown: Mapping[str, Any]
) -> dict[str, Any]:
    chair = session.get(Account, record.chair_id) if record.chair_id else None
    return {
        "state": record.state,
        "opened_at": record.opened_at,
        "closed_at": record.closed_at,
        "closed_by": record.closed_by_name,
        "chair": {"id": chair.id, "name": chair.display_name} if chair else None,
        "agenda": agenda(session, principal, record),
        "may_run": runs(principal, record.org_unit_id) and record.state != "closed",
    }


def _cards(session: Session, principal: Principal, rows: list[Review]) -> list[dict[str, Any]]:
    counts: dict[int, int] = {}
    if rows:
        for review_id, count in session.execute(
            select(ReviewItem.review_id, func.count(ReviewItem.id))
            .where(ReviewItem.review_id.in_([row.id for row in rows]))
            .group_by(ReviewItem.review_id)
        ):
            counts[review_id] = count
    return [{"state": row.state, "held_on": row.held_on, "items": counts.get(row.id, 0)}
            for row in rows]  # fmt: skip


SOON = 14  # days before a review at which the people who run it see it on Home


def owed(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Reviews coming up, or held and not yet closed, for the people who run them."""
    from datetime import timedelta

    from appwren.core.clock import today

    on = today()
    out = []
    for row in session.scalars(
        select(Review).where(
            Review.state != "closed", Review.status == "active",
            Review.held_on <= on + timedelta(days=SOON),
        ).order_by(Review.held_on)
    ):  # fmt: skip
        if not runs(principal, row.org_unit_id):
            continue
        waiting = session.scalars(
            select(func.count(ReviewItem.id)).where(ReviewItem.review_id == row.id)
        ).one()
        out.append({"ref": row.ref, "name": row.name, "held_on": row.held_on,
                    "late": row.held_on < on, "items": waiting, "state": row.state})  # fmt: skip
    return out


def load(session: Session, principal: Principal, ref: str) -> Review:
    return records.load(session, principal, REVIEW, ref)


REVIEW.extra.update(
    can_add=_can_add,
    can_edit=_can_edit,
    can_see=lambda session, principal, record: True,
    visible_to=lambda session, principal: None,
    new=_new,
    apply=_apply,
    detail=_detail,
    cards=_cards,
    add_refusal="Only a manager, or a leader of the unit, can plan a review of it.",
)
