"""Scenarios: what a set of proposed changes would do, before anyone commits to it (PLN-04).

A scenario names applications and what it would do to each: retire it, consolidate it into
another, or replace it with another. Its effect is worked out from the records as they are,
each time it is opened: the cost the applications leaving would save a year, the people whose
application would change, the interfaces that would stop, the capabilities left with nothing
to serve them, and the risk that would go with them. Building one changes no record. A
scenario can become an initiative, proposed, naming the same applications.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Conflict, Invalid, PermissionDenied
from appwren.db.models import (
    Application,
    ApplicationCapability,
    Capability,
    Initiative,
    Interface,
    Scenario,
    ScenarioChange,
)
from appwren.insight.shares import IN_SERVICE
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import (
    APPLICATION,
    CAPABILITY,
    INITIATIVE,
    INTERFACE,
    SCENARIO,
)

ACTIONS = {
    "retire": "Retire it",
    "consolidate": "Consolidate it into",
    "replace": "Replace it with",
}
KINDS = {"retire": "retire", "consolidate": "consolidate", "replace": "replace"}


def _keeps(principal: Principal) -> bool:
    return access.keeps_shared(principal)


def _require(principal: Principal, record: Scenario) -> None:
    if not _keeps(principal):
        raise PermissionDenied("Only an architect or a manager changes a scenario.")
    if record.initiative_id is not None:
        raise Conflict("It has become an initiative, and changes no more.")


def set_changes(
    session: Session, principal: Principal, record: Scenario, wanted: list[Mapping[str, Any]]
) -> None:
    """The applications it would change, and how. Replaces those it had."""
    _require(principal, record)
    errors = Errors()
    chosen: dict[int, tuple[str, int | None, str | None]] = {}
    for index, item in enumerate(wanted):
        where = f"changes[{index}]"
        ref = str(item.get("application") or "").strip()
        try:
            app = records.load(session, principal, APPLICATION, ref)
        except Exception:
            errors.add(where, f"There is no application {ref or '(none given)'}.")
            continue
        action = str(item.get("action") or "")
        if action not in ACTIONS:
            errors.add(where, "Say whether it is retired, consolidated, or replaced.")
            continue
        into_id = None
        if action != "retire":
            into_ref = str(item.get("into") or "").strip()
            try:
                into = records.load(session, principal, APPLICATION, into_ref)
            except Exception:
                how = "move into" if action == "consolidate" else "be replaced by"
                errors.add(where, f"Name the application {app.name} would {how}.")
                continue
            if into.id == app.id:
                errors.add(where, f"{app.name} cannot take its own place.")
                continue
            into_id = into.id
        if app.id in chosen:
            errors.add(where, f"{app.name} appears twice.")
            continue
        note = " ".join(str(item.get("note") or "").split())[:500] or None
        chosen[app.id] = (action, into_id, note)
    leaving = set(chosen)
    for _, into_id, _ in chosen.values():
        if into_id in leaving:
            name = session.get(Application, into_id).name  # type: ignore[union-attr]
            errors.add("changes", f"{name} is itself leaving, so nothing can move into it.")
            break
    if errors:
        raise Invalid("The changes were not saved.", errors)
    have = {row.application_id: row for row in session.scalars(
        select(ScenarioChange).where(ScenarioChange.scenario_id == record.id))}  # fmt: skip
    for app_id, row in have.items():
        if app_id not in chosen:
            app = session.get(Application, app_id)
            if app is not None and access.sees_application(session, principal, app):
                session.delete(row)
    for app_id, (action, into_id, note) in chosen.items():
        row = have.get(app_id)
        if row is None:
            session.add(ScenarioChange(scenario_id=record.id, application_id=app_id,
                                       action=action, into_id=into_id, note=note))  # fmt: skip
        else:
            row.action, row.into_id, row.note = action, into_id, note
    records.touch(session, record)
    session.flush()


def _changes(session: Session, record: Scenario) -> list[tuple[ScenarioChange, Application]]:
    return list(session.execute(
        select(ScenarioChange, Application)
        .join(Application, Application.id == ScenarioChange.application_id)
        .where(ScenarioChange.scenario_id == record.id)
        .order_by(Application.name)
    ))  # fmt: skip


def effect(session: Session, principal: Principal, record: Scenario) -> dict[str, Any]:
    """What the changes would do, from the records as they are now. Of the applications the
    person may not see, nothing is named; cost is summed only where they may see it."""
    from appwren import assessment
    from appwren.landscape import costs

    rows = _changes(session, record)
    leaving = {app.id: app for _, app in rows}
    into = {change.application_id: change.into_id for change, _ in rows}
    seen = {app_id for app_id, app in leaving.items()
            if access.sees_application(session, principal, app)}  # fmt: skip
    # Cost: what the applications leaving cost a year, before anything that takes their place.
    costed = [app for app in leaving.values() if app.id in seen
              and costs.sees_cost(session, principal, app)]  # fmt: skip
    saved = sum(app.annual_cost or 0 for app in costed)
    # People: those who use an application that would go.
    people = sum(app.users or 0 for app in leaving.values() if app.id in seen)
    # Interfaces: one end leaving, the other staying, and not the one it moves into.
    broken = []
    if leaving:
        for row in session.scalars(
            select(Interface)
            .where(
                Interface.status == "active",
                or_(Interface.source_id.in_(leaving), Interface.target_id.in_(leaving)),
            )
            .order_by(Interface.name)
        ):
            ends = (row.source_id, row.target_id)
            if all(end in leaving for end in ends):
                continue  # both go: it goes with them
            gone = row.source_id if row.source_id in leaving else row.target_id
            other = row.target_id if gone == row.source_id else row.source_id
            if into.get(gone) == other:
                continue  # it fed what replaces it: that work moves inside
            if not access.can_see(session, principal, INTERFACE, row):
                continue
            stays = session.get(Application, other)
            broken.append(
                {
                    **records.chip(INTERFACE, row),
                    "leaving": records.chip(APPLICATION, leaving[gone]),
                    "staying": records.chip(APPLICATION, stays) if stays else None,
                }
            )
    # Capabilities: served by one leaving and by nothing in service that stays.
    uncovered = []
    if leaving:
        served = session.execute(
            select(ApplicationCapability.capability_id, Application.id)
            .join(Application, Application.id == ApplicationCapability.application_id)
            .where(Application.status == "active", Application.lifecycle.in_(IN_SERVICE))
        ).all()
        by_capability: dict[int, set[int]] = {}
        for capability_id, app_id in served:
            by_capability.setdefault(capability_id, set()).add(app_id)
        for capability_id, apps in sorted(by_capability.items()):
            if apps & set(leaving) and not apps - set(leaving):
                capability = session.get(Capability, capability_id)
                if capability is not None:
                    by = [records.chip(APPLICATION, leaving[i]) for i in sorted(apps) if i in seen]
                    uncovered.append({**records.chip(CAPABILITY, capability), "served_by": by})
    # Risk: what the applications leaving carry today.
    scored = assessment.score_all(session, [leaving[i] for i in sorted(seen)]) if seen else {}
    risks = []
    flags: Counter[str] = Counter()
    texts: dict[str, str] = {}
    for app_id in sorted(seen, key=lambda i: leaving[i].name):
        found = scored.get(app_id)
        if found is None:
            continue
        raised = [flag for flag in found["flags"] if flag["severity"] in ("danger", "warn")]
        for flag in raised:
            flags[flag["key"]] += 1
            texts[flag["key"]] = flag["text"]
        risks.append({**records.chip(APPLICATION, leaving[app_id]),
                      "risk_exposure": found["scores"].get("risk_exposure"),
                      "flags": [flag["text"] for flag in raised]})  # fmt: skip
    risky = [item["risk_exposure"] for item in risks if item["risk_exposure"] is not None]
    return {
        "applications": len(seen),
        "hidden": len(leaving) - len(seen),
        "cost_saved": saved,
        "cost_withheld": len(seen) - len(costed),
        "people": people,
        "interfaces": broken,
        "capabilities": uncovered,
        "risk": {
            "applications": risks,
            "average": round(sum(risky) / len(risky), 2) if risky else None,
            "flags": [{"key": key, "text": texts[key], "count": count}
                      for key, count in flags.most_common()],
        },
    }  # fmt: skip


def _detail(
    session: Session, principal: Principal, record: Scenario, shown: Mapping[str, Any]
) -> dict[str, Any]:
    rows = _changes(session, record)
    changes = []
    for change, app in rows:
        if not access.sees_application(session, principal, app):
            continue
        target = session.get(Application, change.into_id) if change.into_id else None
        changes.append({
            **records.chip(APPLICATION, app), "lifecycle": app.lifecycle,
            "action": change.action, "action_label": ACTIONS[change.action],
            "into": records.chip(APPLICATION, target) if target else None, "note": change.note,
        })  # fmt: skip
    initiative = session.get(Initiative, record.initiative_id) if record.initiative_id else None
    return {
        "changes": changes,
        "effect": effect(session, principal, record),
        "initiative": records.chip(INITIATIVE, initiative) if initiative else None,
        "may_keep": _keeps(principal) and initiative is None,
    }


def _cards(session: Session, principal: Principal, rows: list[Scenario]) -> list[dict[str, Any]]:
    counts: Counter[int] = Counter()
    if rows:
        for (scenario_id,) in session.execute(
            select(ScenarioChange.scenario_id).where(
                ScenarioChange.scenario_id.in_([row.id for row in rows]))
        ):  # fmt: skip
            counts[scenario_id] += 1
    return [{"changes": counts.get(row.id, 0), "became": bool(row.initiative_id)} for row in rows]


def to_initiative(
    session: Session, principal: Principal, record: Scenario, values: Mapping[str, Any]
) -> Initiative:
    """Make a proposed initiative of it, naming the same applications: those leaving as
    retired by it, and those taking their place as receiving work. The scenario then keeps a
    link to it and changes no more."""
    _require(principal, record)
    rows = _changes(session, record)
    if not rows:
        raise Invalid("Nothing was made.", {"changes": "Name what it would change first."})
    actions = {change.action for change, _ in rows}
    kind = KINDS[actions.pop()] if len(actions) == 1 else (
        "consolidate" if "consolidate" in actions else "replace")  # fmt: skip
    unit = values.get("org_unit_id") or rows[0][1].org_unit_id
    initiative = records.create(session, principal, INITIATIVE, {
        "name": str(values.get("name") or record.name)[:200], "summary": record.summary,
        "kind": kind, "stage": "proposed", "org_unit_id": unit,
    })  # fmt: skip
    from appwren.planning import initiatives

    named: dict[str, dict[str, Any]] = {}
    for change, app in rows:
        named[app.ref] = {"application": app.ref, "action": "retires", "note": change.note}
    for change, _ in rows:
        target = session.get(Application, change.into_id) if change.into_id else None
        if target is not None and target.ref not in named:
            named[target.ref] = {"application": target.ref, "action": "receives", "note": None}
    initiatives.set_applications(session, principal, initiative, list(named.values()))
    record.initiative_id = initiative.id
    records.touch(session, record)
    session.flush()
    return initiative


SCENARIO.extra.update(detail=_detail, cards=_cards)
