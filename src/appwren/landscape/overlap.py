"""Where the organization pays twice, and where it is thin (LND-06, LND-07).

Both views are drawn from the portfolio list, narrowed by capability: the applications shown
for a capability are exactly the ones that list gives for it, so the figures here open lists
of the same length.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren import reporting
from appwren.access.principal import Principal
from appwren.db.models import Application, ApplicationCapability, Capability
from appwren.inventory import records
from appwren.inventory.registry import CAPABILITY

SCORES = ("business_value", "technical_health", "cost_burden", "risk_exposure")
MEASURES = (*SCORES, "confidence", "applications", "weakest_health")


def _served(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, dict[str, Any]]]:
    """For each capability, the applications in service that serve it and the person may
    see, as rows of the portfolio list, the primary first."""
    base = {k: v for k, v in filters.items() if v not in (None, "")}
    base["in_service"] = "true"
    rows = {row["id"]: row for row in reporting.portfolio_list(session, principal, base)}
    users: dict[int, int | None] = {}
    for app_id, count in session.execute(
        select(Application.id, Application.users).where(Application.id.in_(rows))
    ):
        users[app_id] = count
    served: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for capability_id, application_id, is_primary in session.execute(
        select(
            ApplicationCapability.capability_id,
            ApplicationCapability.application_id,
            ApplicationCapability.is_primary,
        ).where(ApplicationCapability.application_id.in_(rows))
    ):
        row = rows[application_id]
        served[capability_id].append(
            {
                "ref": row["ref"],
                "name": row["name"],
                "type": "application",
                "status": row["status"],
                "is_primary": bool(is_primary),
                "scores": row["scores"],
                "confidence": row["confidence"],
                "recommendation": row["recommendation"],
                "decision": row["decision"],
                "users": users.get(application_id),
                "annual_cost": row["annual_cost"],
            }
        )
    for found in served.values():
        found.sort(key=lambda item: (not item["is_primary"], item["name"].lower()))
    return served, rows


def _total(values: list[Any]) -> int | None:
    """A sum, unless any part of it is withheld: a total with a part missing would say
    something untrue, and with a part hidden would give it away."""
    if any(value == records.WITHHELD for value in values):
        return None
    return sum(int(value) for value in values if value is not None)


def overlap(session: Session, principal: Principal, filters: Mapping[str, Any]) -> dict[str, Any]:
    """Every capability served by more than one application in service, with those
    applications side by side."""
    served, _ = _served(session, principal, filters)
    base = {k: v for k, v in filters.items() if v not in (None, "")}
    capabilities = {
        row.id: row for row in session.scalars(select(Capability).where(Capability.id.in_(served)))
    }
    found = []
    for capability_id, apps in served.items():
        capability = capabilities.get(capability_id)
        if capability is None or len(apps) < 2:
            continue
        primary = next((app for app in apps if app["is_primary"]), None)
        found.append(
            {
                **records.chip(CAPABILITY, capability),
                "domain": capability.domain,
                "applications": apps,
                "primary": primary["ref"] if primary else None,
                "users": sum(app["users"] or 0 for app in apps),
                "annual_cost": _total([app["annual_cost"] for app in apps]),
                "consolidate": sum(1 for app in apps if app["recommendation"] == "consolidate"),
                "filters": {**base, "in_service": "true", "capability": capability.ref},
            }
        )
    found.sort(key=lambda item: (-len(item["applications"]), item["name"].lower()))
    return {
        "capabilities": found,
        "applications": len({app["ref"] for item in found for app in item["applications"]}),
        "unnamed": sum(1 for item in found if item["primary"] is None),
    }


def _measure(apps: list[dict[str, Any]]) -> dict[str, Any]:
    """What a set of applications says about a capability: how many, their average scores
    and confidence, and the health of the weakest."""
    out: dict[str, Any] = {"applications": len(apps)}
    for key in SCORES:
        known = [app["scores"][key] for app in apps if app["scores"].get(key) is not None]
        out[key] = round(sum(known) / len(known), 1) if known else None
    confident = [app["confidence"] for app in apps if app["confidence"] is not None]
    out["confidence"] = round(sum(confident) / len(confident)) if confident else None
    health = [app["scores"]["technical_health"] for app in apps]
    health = [value for value in health if value is not None]
    out["weakest_health"] = min(health) if health else None
    return out


def heat(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The capability tree, each capability with what its applications measure. A capability
    with narrower ones beneath it is measured over all the applications beneath it."""
    served, _ = _served(session, principal, filters)
    base = {k: v for k, v in filters.items() if v not in (None, "")}
    rows = session.scalars(select(Capability).order_by(Capability.position, Capability.name)).all()
    nodes: dict[int, dict[str, Any]] = {}
    for row in rows:
        nodes[row.id] = {
            **records.chip(CAPABILITY, row),
            "domain": row.domain,
            "summary": row.summary,
            "applications": served.get(row.id, []),
            "children": [],
            "filters": {**base, "in_service": "true", "capability": row.ref},
        }
    roots = []
    for row in rows:
        node = nodes[row.id]
        (nodes[row.parent_id]["children"] if row.parent_id in nodes else roots).append(node)

    def measure(node: dict[str, Any]) -> list[dict[str, Any]]:
        beneath = {app["ref"]: app for app in node["applications"]}
        for child in node["children"]:
            for app in measure(child):
                beneath.setdefault(app["ref"], app)
        node["measures"] = _measure(list(beneath.values()))
        return list(beneath.values())

    for root in roots:
        measure(root)
    return roots
