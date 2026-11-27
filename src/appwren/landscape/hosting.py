"""Where things run: hosting platforms, and the deployments of applications and their
components on them (LND-05).

A platform is a shared record, kept by architects and managers. A deployment belongs to its
application: it is seen with it and kept by whoever keeps it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.db.models import Application, Component, Deployment, HostingPlatform, Vendor
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import (
    APPLICATION,
    COMPONENT,
    DEPLOYMENT,
    HOSTING_PLATFORM,
    VENDOR,
    find,
)
from appwren.landscape import graph
from appwren.program import vocab

MAX_SHOWN = 2000


# --- Deployments ----------------------------------------------------------------------------


def _application(session: Session, record: Any) -> list[Any]:
    found = session.get(Application, record.application_id) if record.application_id else None
    return [found] if found is not None else []


def _default_name(session: Session, values: Mapping[str, Any]) -> str | None:
    """A deployment is named for what runs and where: "Tracker API, production"."""
    errors = Errors()
    app_id = records.reference(session, "application", values.get("application_id"), "a", errors)
    part_id = records.reference(session, "component", values.get("component_id"), "c", errors)
    what = session.get(Component, part_id) if part_id else None
    what = what or (session.get(Application, app_id) if app_id else None)
    if what is None:
        return None
    labels = vocab.labels(session, "environments")
    where = labels.get(str(values.get("environment") or "production"), "")
    return f"{what.name}, {where.lower()}"[:200] if where else what.name


def _apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    application = session.get(Application, record.application_id) if record.application_id else None
    if application is not None:
        record.org_unit_id = application.org_unit_id
        record.restricted = application.restricted
    if record.component_id is not None:
        component = session.get(Component, record.component_id)
        if component is None or component.application_id != record.application_id:
            errors.add("component_id", "Choose one of this application's components.")
    platform = session.get(HostingPlatform, record.platform_id) if record.platform_id else None
    if (
        platform is not None
        and platform.status != "active"
        and (creating or "platform_id" in values)
    ):
        errors.add("platform_id", "That platform has been retired.")


def _can_add(session: Session, principal: Principal, record: Any) -> bool:
    return any(access.keeps(session, principal, app) for app in _application(session, record))


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    if not filters.get("application"):
        return []
    application = find(session, APPLICATION, str(filters["application"]))
    return [Deployment.application_id == application.id]


def _cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
    def load(model: Any, ids: Iterable[int | None]) -> dict[int, Any]:
        wanted = {value for value in ids if value is not None}
        return {row.id: row for row in session.scalars(select(model).where(model.id.in_(wanted)))}

    apps = load(Application, (row.application_id for row in rows))
    parts = load(Component, (row.component_id for row in rows))
    platforms = load(HostingPlatform, (row.platform_id for row in rows))
    return [
        {
            "application": records.chip(APPLICATION, apps[row.application_id])
            if row.application_id in apps else None,
            "component": records.chip(COMPONENT, parts[row.component_id])
            if row.component_id in parts else None,
            "platform": records.chip(HOSTING_PLATFORM, platforms[row.platform_id])
            if row.platform_id in platforms else None,
        }
        for row in rows
    ]  # fmt: skip


DEPLOYMENT.extra.update(
    applications=_application,
    default_name=_default_name,
    apply=_apply,
    can_add=_can_add,
    conditions=_conditions,
    cards=_cards,
    add_refusal="Only the people who keep an application can say where it runs.",
    history_vocabularies={"environment": "environments"},
)


# --- Platforms ------------------------------------------------------------------------------


def running_on(
    session: Session, principal: Principal, platform: HostingPlatform
) -> list[dict[str, Any]]:
    """Everything the person may see that runs on a platform."""
    rows, _ = records.search(
        session, principal, DEPLOYMENT,
        {"platform_id": platform.id, "status": "active"}, sort="name", limit=MAX_SHOWN,
    )  # fmt: skip
    return records.cards(session, principal, DEPLOYMENT, rows)


def _platform_detail(
    session: Session, principal: Principal, record: HostingPlatform, shown: Mapping[str, Any]
) -> dict[str, Any]:
    vendor = session.get(Vendor, record.vendor_id) if record.vendor_id else None
    running = running_on(session, principal, record)
    by_environment: dict[str, int] = defaultdict(int)
    for row in running:
        by_environment[row["environment"]] += 1
    applications = {row["application"]["ref"] for row in running if row["application"]}
    return {
        "vendor": records.chip(VENDOR, vendor) if vendor else None,
        "deployments": running,
        "by_environment": dict(by_environment),
        "application_count": len(applications),
    }


def _platform_cards(
    session: Session, principal: Principal, rows: list[Any]
) -> list[dict[str, Any]]:
    """How much runs on each platform, counting only what the person may see."""
    seen = access.visible(session, principal, DEPLOYMENT)
    conditions = [
        Deployment.platform_id.in_([row.id for row in rows]),
        Deployment.status == "active",
    ]
    if seen is not None:
        conditions.append(seen)
    found: dict[int, set[int]] = defaultdict(set)
    counts: dict[int, int] = defaultdict(int)
    for platform_id, application_id in session.execute(
        select(Deployment.platform_id, Deployment.application_id).where(*conditions)
    ):
        found[platform_id].add(application_id)
        counts[platform_id] += 1
    vendors = {
        vendor.id: vendor
        for vendor in session.scalars(
            select(Vendor).where(Vendor.id.in_({row.vendor_id for row in rows if row.vendor_id}))
        )
    }
    return [
        {
            "vendor": records.chip(VENDOR, vendors[row.vendor_id])
            if row.vendor_id in vendors else None,
            "deployment_count": counts.get(row.id, 0),
            "application_count": len(found.get(row.id, ())),
        }
        for row in rows
    ]  # fmt: skip


HOSTING_PLATFORM.extra.update(
    detail=_platform_detail,
    cards=_platform_cards,
    history_vocabularies={"kind": "platform_kinds"},
)


# --- What joins them, for the picture -------------------------------------------------------


def _edges(session: Session, key: str, record_id: int) -> list[graph.Edge]:
    found: list[graph.Edge] = []
    if key == "application":
        for platform_id in session.scalars(
            select(Deployment.platform_id)
            .where(Deployment.application_id == record_id, Deployment.status == "active")
            .order_by(Deployment.id)
        ):
            found.append(("runs_on", "Runs on", "hosting_platform", platform_id))
    elif key == "component":
        for platform_id in session.scalars(
            select(Deployment.platform_id)
            .where(Deployment.component_id == record_id, Deployment.status == "active")
            .order_by(Deployment.id)
        ):
            found.append(("runs_on", "Runs on", "hosting_platform", platform_id))
    elif key == "hosting_platform":
        platform = session.get(HostingPlatform, record_id)
        for application_id in session.scalars(
            select(Deployment.application_id)
            .where(Deployment.platform_id == record_id, Deployment.status == "active")
            .order_by(Deployment.id)
        ):
            found.append(("hosts", "Hosts", "application", application_id))
        if platform is not None and platform.vendor_id is not None:
            found.append(("provided_by", "Provided by", "vendor", platform.vendor_id))
    elif key == "vendor":
        for platform_id in session.scalars(
            select(HostingPlatform.id)
            .where(HostingPlatform.vendor_id == record_id)
            .order_by(HostingPlatform.name)
        ):
            found.append(("provides", "Provides", "hosting_platform", platform_id))
    elif key == "deployment":
        deployment = session.get(Deployment, record_id)
        if deployment is not None:
            found.append(("of", "Of", "application", deployment.application_id))
            if deployment.component_id is not None:
                found.append(("part", "Its part", "component", deployment.component_id))
            found.append(("on", "On", "hosting_platform", deployment.platform_id))
    return found


graph.MORE_EDGES.append(_edges)
