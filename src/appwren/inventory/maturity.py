"""Engineering maturity: what engineering practice each component has, measured (SCR-12).

Each check is read from a record's field or a fact a source supplied: monitoring and backups
from the application's record, documentation from its documentation address or a README in the
repository, and the rest from the repository. A component reaches a level when every check of
that level and those below it is met; a check about code does not apply to what is not code,
such as a database. An application is at the level of its least mature component. Only what is
built here, or has a repository recorded, is measured: a bought product's engineering is its
vendor's.

The levels and their checks are in the program, beside the cadence. By default: bronze is
monitoring, backups, and documentation; silver adds tests and continuous integration; gold adds
automated dependency updates and no open critical dependency alert.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.db.among import among
from appwren.db.models import Application, Component, FactValue
from appwren.engine.maturity import CHECKS, CODE_CHECKS, DEFAULT, NONE, levels, problems, ranks

__all__ = ["CHECKS", "CODE_CHECKS", "DEFAULT", "NONE", "levels", "measure", "problems", "ranks"]

CODE_FACTS = ("has_readme", "has_tests", "has_ci", "has_dependency_updates", "dependency_alerts",
              "last_change")  # fmt: skip
MET, NOT_MET, UNKNOWN, NOT_APPLICABLE = "met", "not_met", "unknown", "not_applicable"
# What is built here is measured; so is anything with a repository recorded. Code checks
# apply to every component that is code, whether or not its repository is recorded.
BUILT = {"built_here", "research_software", "low_code"}
CODE_KINDS = {"service", "web_frontend", "batch_job", "integration", "module", "library",
              "mobile_app", "pipeline"}  # fmt: skip
REPOSITORY_FACT = {
    "tests": "has_tests",
    "ci": "has_ci",
    "dependency_updates": "has_dependency_updates",
}


def _facts(session: Session, component_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Each component's facts from sources, as they hold (an override's where there is one)."""
    out: dict[int, dict[str, Any]] = defaultdict(dict)
    if not component_ids:
        return out
    for row in session.scalars(
        select(FactValue).where(
            FactValue.record_type == "component",
            among(FactValue.record_id, component_ids),
            FactValue.field.in_(CODE_FACTS),
        )
    ):
        out[row.record_id][row.field] = row.override_value if row.overridden else row.value
    return out


def _check(
    key: str, app: Application, part: Component, facts: Mapping[str, Any]
) -> tuple[str, str]:
    """A check's state and why, for one component."""
    has_code = bool(part.repo_url)
    if key == "monitoring":
        if app.monitoring is None:
            return UNKNOWN, "Monitoring is not recorded on the application"
        return (
            (NOT_MET, "None, says the application's record")
            if app.monitoring == "none"
            else (MET, "Recorded on the application")
        )
    if key == "backups":
        if app.backup is None:
            return UNKNOWN, "Backups are not recorded on the application"
        return (
            (NOT_MET, "None, says the application's record")
            if app.backup == "none"
            else (MET, "Recorded on the application")
        )
    if key == "documentation":
        if app.docs_url:
            return MET, "The application's documentation address"
        if facts.get("has_readme") is True:
            return MET, "A README in the repository"
        if facts.get("has_readme") is False:
            return NOT_MET, "No documentation address, and no README in the repository"
        return UNKNOWN, "No documentation address is recorded"
    if not has_code:
        if part.kind in CODE_KINDS:
            return UNKNOWN, "No repository is recorded"
        return NOT_APPLICABLE, "It is not code"
    if key == "no_critical_alerts":
        alerts = facts.get("dependency_alerts")
        if not isinstance(alerts, Mapping):
            return UNKNOWN, "Its dependency alerts are not known"
        critical = int(alerts.get("critical") or 0)
        return (MET, "None open") if critical == 0 else (NOT_MET, f"{critical} open")
    fact = {"tests": "has_tests", "ci": "has_ci", "dependency_updates": "has_dependency_updates"}[
        key
    ]
    value = facts.get(fact)
    if value is None:
        return UNKNOWN, "No source has read its repository"
    return (MET, "Found in the repository") if value else (NOT_MET, "Not found in the repository")


def _level(chain: list[dict[str, Any]], states: Mapping[str, str]) -> str:
    reached = NONE
    for level in chain:
        if all(states.get(check) in (MET, NOT_APPLICABLE) for check in level["checks"]):
            reached = level["key"]
        else:
            break
    return reached


def _next(chain: list[dict[str, Any]], reached: str) -> dict[str, Any] | None:
    keys = [NONE, *[level["key"] for level in chain]]
    index = keys.index(reached)
    return chain[index] if index < len(chain) else None


def measure(
    session: Session, apps: Iterable[Application], model: Mapping[str, Any] | None
) -> dict[int, dict[str, Any]]:
    """Each application's level, and each of its components' level and checks."""
    chain = levels(model)
    rank = {NONE: 0, **{level["key"]: index + 1 for index, level in enumerate(chain)}}
    labels = {
        NONE: "Below " + chain[0]["label"].lower(),
        **{lv["key"]: lv["label"] for lv in chain},
    }
    apps = list(apps)
    by_id = {app.id: app for app in apps}
    parts = session.scalars(
        select(Component)
        .where(Component.application_id.in_(by_id), Component.status == "active")
        .order_by(Component.ref)
    ).all() if by_id else []  # fmt: skip
    facts = _facts(session, [part.id for part in parts])
    out: dict[int, dict[str, Any]] = {
        app.id: {"level": None, "label": "Not measured", "components": [], "coded": False}
        for app in apps
    }
    measured = {app.id for app in apps if app.sourcing in BUILT}
    measured |= {part.application_id for part in parts if part.repo_url}
    for part in parts:
        app = by_id[part.application_id]
        if app.id not in measured:
            continue  # a bought product's engineering is its vendor's
        found = facts.get(part.id, {})
        checks = []
        states: dict[str, str] = {}
        for level in chain:
            for key in level["checks"]:
                state, why = _check(key, app, part, found)
                states[key] = state
                checks.append({"key": key, "label": CHECKS[key], "level": level["key"],
                               "state": state, "why": why})  # fmt: skip
        reached = _level(chain, states)
        following = _next(chain, reached)
        missing = [c for c in checks if following and c["level"] == following["key"]
                   and c["state"] not in (MET, NOT_APPLICABLE)]  # fmt: skip
        out[app.id]["components"].append({
            "id": part.id, "ref": part.ref, "name": part.name, "level": reached,
            "label": labels[reached], "checks": checks,
            "next": {"key": following["key"], "label": following["label"],
                     "missing": missing} if following else None,
        })  # fmt: skip
        out[app.id]["coded"] = out[app.id]["coded"] or any(key in found for key in CODE_FACTS)
    for item in out.values():
        if item["components"]:
            lowest = min(item["components"], key=lambda c: rank[c["level"]])
            item["level"], item["label"] = lowest["level"], labels[lowest["level"]]
            item["held_back_by"] = [c["ref"] for c in item["components"]
                                    if c["level"] == lowest["level"]]  # fmt: skip
    return out


def applications_at(session: Session, level: str) -> list[int]:
    """The applications at a level (or ``none``, or ``unmeasured``), for a list filter."""
    from appwren.assessment import current_model

    model = current_model(session).definition
    apps = session.scalars(select(Application).where(Application.status == "active")).all()
    found = measure(session, apps, model)
    if level == "unmeasured":
        return [app_id for app_id, item in found.items() if item["level"] is None]
    return [app_id for app_id, item in found.items() if item["level"] == level]


def of_record(session: Session, principal: Any, record_type: Any, record: Any) -> dict[str, Any]:
    """An application's maturity with each component's, or one component's."""
    from appwren.assessment import current_model

    model = current_model(session).definition
    application = record if record_type.key == "application" else session.get(
        Application, record.application_id
    )  # fmt: skip
    found = measure(session, [application], model)[application.id]
    if record_type.key == "component":
        mine = next((c for c in found["components"] if c["id"] == record.id), None)
        return {"component": mine, "application": {"level": found["level"],
                                                   "label": found["label"]},
                "levels": ranks(model)}  # fmt: skip
    return {**found, "levels": ranks(model)}


def report(session: Session, principal: Any, unit_id: int | None = None) -> dict[str, Any]:
    """How many applications the person may see are at each level, under each unit below the
    one chosen (the whole organization by default), each count including the units below."""
    from appwren.assessment import current_model
    from appwren.core.errors import NotFound
    from appwren.inventory import records
    from appwren.inventory.registry import APPLICATION
    from appwren.people import units

    model = current_model(session).definition
    found_units = units.all_units(session)
    below = units.children_map(found_units)
    by_id = {unit.id: unit for unit in found_units}
    if unit_id is None:
        roots = below.get(None, [])
        parent = roots[0] if len(roots) == 1 else None
    else:
        parent = by_id.get(unit_id)
        if parent is None:
            raise NotFound("There is no such unit.")
    rows_of = below.get(parent.id if parent else None, [])
    conditions = records.conditions_for(session, principal, APPLICATION, {})
    apps = session.scalars(
        select(Application).where(Application.status == "active", *conditions)
    ).all()
    measured = measure(session, apps, model)
    keys = [key for key, _ in ranks(model)] + ["unmeasured"]

    def counts(ids: frozenset[int] | None) -> dict[str, Any]:
        tally = dict.fromkeys(keys, 0)
        for app in apps:
            if ids is None or app.org_unit_id in ids:
                tally[measured[app.id]["level"] or "unmeasured"] += 1
        return {"counts": tally, "total": sum(tally.values())}

    rows = []
    for unit in sorted(rows_of, key=lambda u: u.name):
        if unit.status != "active":
            continue
        ids = units.with_descendants(session, [unit.id])
        rows.append({"unit": {"id": unit.id, "name": unit.name,
                              "has_children": bool(below.get(unit.id))},
                     **counts(ids)})  # fmt: skip
    whole = units.with_descendants(session, [parent.id]) if parent else None
    return {
        "unit": {"id": parent.id, "name": parent.name} if parent else None,
        "up": parent.parent_id if parent else None,
        "levels": [*ranks(model), ("unmeasured", "Not measured")],
        "rows": [row for row in rows if row["total"]],
        "all": counts(whole),
    }  # fmt: skip
