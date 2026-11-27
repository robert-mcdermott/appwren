"""Who handles a class of data, and how well it is looked after (RPT-07).

The evidence other processes ask a portfolio for: the applications that handle a class of
data, each with who answers for it, where it comes from and runs, how people sign in, what it
is built on and whether that is supported, what carries the data in and out, and whether a
data agreement is in place. What a reader may not see of an application is withheld here as
it is on its record.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid
from appwren.db.models import (
    Component,
    Contract,
    ContractApplication,
    Deployment,
    HostingPlatform,
    OrgUnit,
    Vendor,
)
from appwren.inventory import access, parts, records
from appwren.inventory.registry import APPLICATION, INTERFACE
from appwren.landscape import costs
from appwren.program import catalog, vocab

MAX_ROWS = 5000
# The worst of what an application's components run on, and the worst agreement over it.
SUPPORT_ORDER = ("ended", "extended", "ending", "unknown", "supported")
AGREEMENT_ORDER = ("missing", "in_place", "not_needed")


def _active(session: Session, name: str) -> list[dict[str, Any]]:
    return [item for item in vocab.get(session, name) if not item.get("retired")]


def rows(session: Session, principal: Principal, data_class: str) -> list[dict[str, Any]]:
    """The applications in service that handle a class of data and that the person may see."""
    if data_class not in {item["key"] for item in _active(session, "data_classes")}:
        raise Invalid("There is no such class of data.", {"data_class": "Choose one of the list."})
    apps, _ = records.search(
        session, principal, APPLICATION,
        {"status": "active", "data_class": data_class}, sort="name", limit=MAX_ROWS,
    )  # fmt: skip
    ids = [app.id for app in apps]
    owners = records.owners_of(session, APPLICATION, ids)
    sensitive = set(catalog.sensitive_fields(session))
    units = {
        row.id: row.name
        for row in session.scalars(
            select(OrgUnit).where(OrgUnit.id.in_({app.org_unit_id for app in apps}))
        )
    }
    vendors = {
        row.id: row.name
        for row in session.scalars(
            select(Vendor).where(Vendor.id.in_({app.vendor_id for app in apps if app.vendor_id}))
        )
    }
    # What each is built on, through its components.
    components: dict[int, list[int]] = defaultdict(list)
    for component_id, application_id in session.execute(
        select(Component.id, Component.application_id).where(
            Component.application_id.in_(ids), Component.status == "active"
        )
    ):
        components[application_id].append(component_id)
    built_on = parts.technologies_of(
        session, [each for found in components.values() for each in found]
    )
    # Where each runs in production.
    platforms: dict[int, list[str]] = defaultdict(list)
    for application_id, name in session.execute(
        select(Deployment.application_id, HostingPlatform.name)
        .join(HostingPlatform, HostingPlatform.id == Deployment.platform_id)
        .where(
            Deployment.application_id.in_(ids),
            Deployment.status == "active",
            Deployment.environment == "production",
        )
        .order_by(HostingPlatform.name)
    ):
        if name not in platforms[application_id]:
            platforms[application_id].append(name)
    # What carries the class in and out, among the interfaces the person may see.
    flows, _ = records.search(
        session, principal, INTERFACE,
        {"status": "active", "data_class": data_class}, sort="name", limit=MAX_ROWS,
    )  # fmt: skip
    sends: dict[int, int] = defaultdict(int)
    receives: dict[int, int] = defaultdict(int)
    for flow in flows:
        sends[flow.source_id] += 1
        receives[flow.target_id] += 1
    # The standing of the data agreements over each.
    agreements: dict[int, set[str]] = defaultdict(set)
    for application_id, state in session.execute(
        select(ContractApplication.application_id, Contract.data_agreement)
        .join(Contract, Contract.id == ContractApplication.contract_id)
        .where(ContractApplication.application_id.in_(ids), Contract.status == "active")
    ):
        if state:
            agreements[application_id].add(state)
    out = []
    for app in apps:
        people = owners.get(app.id, [])
        is_named = principal.account_id is not None and any(
            person["account_id"] == principal.account_id for person in people
        )
        sees = access.sees_sensitive(session, principal, app, is_named=is_named)

        def shown(name: str, value: Any, sees: bool = sees) -> Any:
            return records.WITHHELD if name in sensitive and not sees else value

        technologies = [
            {"name": tech["name"], "release": tech["release"], "support": tech["support"]}
            for component_id in components.get(app.id, [])
            for tech in built_on.get(component_id, [])
        ]
        states = {tech["support"] for tech in technologies}
        standing = next((s for s in AGREEMENT_ORDER if s in agreements.get(app.id, ())), None)
        out.append(
            {
                **records.chip(APPLICATION, app),
                "unit": units.get(app.org_unit_id),
                "accountable": [p["name"] for p in records.accountable(people)],
                "tier": shown("tier", app.tier),
                "sourcing": shown("sourcing", app.sourcing),
                "vendor": vendors.get(app.vendor_id),
                "hosting": shown("hosting", app.hosting),
                "platforms": platforms.get(app.id, []),
                "sign_in": shown("sign_in", app.sign_in),
                "backup": shown("backup", app.backup),
                "data_classes": app.data_classes or [],
                "technologies": technologies,
                "support": next((s for s in SUPPORT_ORDER if s in states), None),
                "sends": sends.get(app.id, 0),
                "receives": receives.get(app.id, 0),
                # A contract's terms are shown to those who may see the application's cost.
                "data_agreement": standing
                if costs.sees_cost(session, principal, app)
                else records.WITHHELD,
            }
        )
    return out


def handling(session: Session, principal: Principal, data_class: str | None) -> dict[str, Any]:
    """How many applications in service handle each class of data; and, for the class chosen,
    those applications with what an analysis of risk asks about each."""
    classes = []
    for item in _active(session, "data_classes"):
        _, total = records.search(
            session, principal, APPLICATION,
            {"status": "active", "data_class": item["key"]}, limit=1,
        )  # fmt: skip
        classes.append(
            {"key": item["key"], "label": item["label"], "sensitivity": item.get("sensitivity"),
             "applications": total}
        )  # fmt: skip
    found = rows(session, principal, data_class) if data_class else []
    carried = 0
    if data_class:
        _, carried = records.search(
            session, principal, INTERFACE, {"status": "active", "data_class": data_class}, limit=1
        )
    return {
        "classes": classes,
        "data_class": data_class,
        "applications": found,
        "interfaces": carried,
        "unsupported": sum(1 for row in found if row["support"] in ("ended", "extended")),
        "no_agreement": sum(1 for row in found if row["data_agreement"] == "missing"),
    }


def export_rows(session: Session, principal: Principal, data_class: str) -> list[dict[str, Any]]:
    """The same, flat, for a spreadsheet."""
    out = []
    for row in rows(session, principal, data_class):
        flat = {key: value for key, value in row.items() if key not in ("type", "technologies")}
        flat["technologies"] = [
            " ".join(str(part) for part in (tech["name"], tech["release"]) if part)
            + f" ({tech['support']})"
            for tech in row["technologies"]
        ]
        out.append(flat)
    return out
