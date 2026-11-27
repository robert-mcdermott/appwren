"""Components, technologies with their releases, and capabilities: what is particular to each
(INV-05, INV-07, LND-01).

A component belongs to one application and takes its unit, its visibility, and who may edit
it from that application. Technologies, their releases, vendors, and capabilities are shared
records kept by architects and managers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import (
    Application,
    ApplicationCapability,
    Capability,
    Component,
    ComponentTechnology,
    Technology,
    TechnologyRelease,
    Vendor,
)
from appwren.events import audit
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import (
    APPLICATION,
    CAPABILITY,
    COMPONENT,
    TECHNOLOGY,
    VENDOR,
    find,
)

WARNING_DAYS = 365  # end of support this close is a warning


# --- Releases and their support --------------------------------------------------------------


def support_state(release: TechnologyRelease | None, on: date | None = None) -> str:
    """Where a release stands on a day: supported, ending (within a year), extended (past
    its end but still under extended support), ended, or unknown (no dates recorded)."""
    on = on or today()
    if release is None or release.support_ends is None:
        return "unknown"
    if release.support_ends < on:
        if release.extended_ends is not None and release.extended_ends >= on:
            return "extended"
        return "ended"
    if (release.support_ends - on).days <= WARNING_DAYS:
        return "ending"
    return "supported"


def release_view(release: TechnologyRelease, on: date | None = None) -> dict[str, Any]:
    return {
        "id": release.id,
        "cycle": release.cycle,
        "released_on": release.released_on,
        "support_ends": release.support_ends,
        "extended_ends": release.extended_ends,
        "latest": release.latest,
        "support": support_state(release, on),
    }


def set_releases(
    session: Session,
    principal: Principal,
    technology: Technology,
    wanted: list[Mapping[str, Any]],
) -> None:
    """The technology's version lines and their support dates. A release in use by a
    component can have its dates changed, never be removed."""
    if not access.keeps_shared(principal):
        raise PermissionDenied("Only an architect or a manager can change a technology.")
    errors = Errors()
    cleaned: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(wanted):
        where = f"releases[{index}]"
        cycle = records.text(item.get("cycle"))
        if not cycle or len(cycle) > 40:
            errors.add(where, "Give the version line, such as 3.12, in up to 40 characters.")
            continue
        if cycle in cleaned:
            errors.add(where, f"The release {cycle} appears twice.")
            continue
        values = {
            name: records.day(item.get(name), where, errors)
            for name in ("released_on", "support_ends", "extended_ends")
        }
        latest = records.text(item.get("latest"))
        values["latest"] = latest[:40] if latest else None
        if (
            values["support_ends"] and values["extended_ends"]
            and values["extended_ends"] < values["support_ends"]
        ):  # fmt: skip
            errors.add(where, "Extended support cannot end before ordinary support.")
        cleaned[cycle] = values
    have = {
        row.cycle: row
        for row in session.scalars(
            select(TechnologyRelease).where(TechnologyRelease.technology_id == technology.id)
        )
    }
    used = set(
        session.scalars(
            select(ComponentTechnology.release_id).where(
                ComponentTechnology.release_id.in_([row.id for row in have.values()])
            )
        )
    )
    for cycle, row in have.items():
        if cycle not in cleaned and row.id in used:
            errors.add("releases", f"The release {cycle} is in use and cannot be removed.")
    if errors:
        raise Invalid("The releases were not saved.", errors)
    with audit.operation(session, "technology.releases"):
        for cycle, row in have.items():
            if cycle not in cleaned:
                from appwren.connectors import sourced

                sourced.forget(session, "technology_release", row.id)
                session.delete(row)
        for cycle, values in cleaned.items():
            row = have.get(cycle)
            if row is None:
                session.add(TechnologyRelease(technology_id=technology.id, cycle=cycle, **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)
        session.flush()


# --- A component's technologies ----------------------------------------------------------------


def set_technologies(
    session: Session,
    principal: Principal,
    component: Component,
    wanted: list[Mapping[str, Any]],
) -> None:
    """What a component is built on: each technology once, optionally with the release whose
    support dates apply and the exact version."""
    if not access.can_edit(session, principal, COMPONENT, component):
        raise PermissionDenied("You cannot edit this component.")
    errors = Errors()
    chosen: dict[int, tuple[int | None, str | None]] = {}
    for index, item in enumerate(wanted):
        where = f"technologies[{index}]"
        technology_id = records.reference(session, "technology", item.get("technology"), where,
                                          errors)  # fmt: skip
        if technology_id is None:
            continue
        release_id = None
        cycle = records.text(item.get("release"))
        if cycle:
            release = session.scalars(
                select(TechnologyRelease).where(
                    TechnologyRelease.technology_id == technology_id,
                    TechnologyRelease.cycle == cycle,
                )
            ).first()
            if release is None:
                errors.add(where, f"The technology has no release {cycle} on record.")
                continue
            release_id = release.id
        version = records.text(item.get("version"))
        chosen[technology_id] = (release_id, version[:80] if version else None)
    if errors:
        raise Invalid("The technologies were not saved.", errors)
    have = {
        row.technology_id: row
        for row in session.scalars(
            select(ComponentTechnology).where(ComponentTechnology.component_id == component.id)
        )
    }
    with audit.operation(session, "component.technologies"):
        for technology_id, row in have.items():
            if technology_id not in chosen:
                session.delete(row)
        for technology_id, (release_id, version) in chosen.items():
            row = have.get(technology_id)
            if row is None:
                session.add(
                    ComponentTechnology(
                        component_id=component.id,
                        technology_id=technology_id,
                        release_id=release_id,
                        version=version,
                    )
                )
            else:
                row.release_id, row.version = release_id, version
        session.flush()


def technologies_of(
    session: Session, component_ids: Iterable[int], on: date | None = None
) -> dict[int, list[dict[str, Any]]]:
    """Each component's technologies, with the release and where its support stands."""
    ids = list(component_ids)
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids:
        return found
    rows = session.execute(
        select(ComponentTechnology, Technology, TechnologyRelease)
        .join(Technology, Technology.id == ComponentTechnology.technology_id)
        .outerjoin(TechnologyRelease, TechnologyRelease.id == ComponentTechnology.release_id)
        .where(ComponentTechnology.component_id.in_(ids))
        .order_by(Technology.name)
    )
    for link, technology, release in rows:
        found[link.component_id].append(
            {
                **records.chip(TECHNOLOGY, technology),
                "kind": technology.kind,
                "radar": technology.radar,
                "release": release.cycle if release else None,
                "version": link.version,
                "support": support_state(release, on),
                "support_ends": release.support_ends if release else None,
                "extended_ends": release.extended_ends if release else None,
            }
        )
    return found


# --- Components ------------------------------------------------------------------------------


def _component_apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if record.application_id is not None:
        application = session.get(Application, record.application_id)
        if application is not None:
            record.org_unit_id = application.org_unit_id
            record.restricted = application.restricted


def _component_can_add(session: Session, principal: Principal, record: Any) -> bool:
    application = session.get(Application, record.application_id)
    return application is not None and access.can_edit(session, principal, APPLICATION, application)


def _component_detail(
    session: Session, principal: Principal, record: Component, shown: Mapping[str, Any]
) -> dict[str, Any]:
    application = session.get(Application, record.application_id)
    return {
        "application": records.chip(APPLICATION, application) if application else None,
        "technologies": technologies_of(session, [record.id]).get(record.id, []),
    }


def _component_cards(
    session: Session, principal: Principal, rows: list[Any]
) -> list[dict[str, Any]]:
    apps = {
        app.id: app
        for app in session.scalars(
            select(Application).where(Application.id.in_({row.application_id for row in rows}))
        )
    }
    return [
        {"application": records.chip(APPLICATION, apps[row.application_id])
         if row.application_id in apps else None}
        for row in rows
    ]  # fmt: skip


def built_on(session: Session, filters: Mapping[str, Any]) -> Any | None:
    """The components built on a technology, narrowed to one of its releases (``release``,
    or ``none`` for those that name no release) or to an exact version as written (``version``,
    such as 6.0.25, or its start, such as 6.0); None where the filters name no technology.
    Whatever is used with a technology counts, as on the technology's own page."""
    technology_ref = str(filters.get("technology") or "").strip()
    release = str(filters.get("release") or "").strip()
    version = str(filters.get("version") or "").strip()
    if not technology_ref:
        if release or version:
            raise Invalid("The list was not narrowed.",
                          {"technology": "Name the technology the release is of."})  # fmt: skip
        return None
    technology = find(session, TECHNOLOGY, technology_ref)
    statement = select(ComponentTechnology.component_id).where(
        ComponentTechnology.technology_id == technology.id
    )
    if release == "none":
        statement = statement.where(ComponentTechnology.release_id.is_(None))
    elif release:
        row = session.scalars(
            select(TechnologyRelease).where(
                TechnologyRelease.technology_id == technology.id,
                TechnologyRelease.cycle == release,
            )
        ).first()
        if row is None:
            raise Invalid("The list was not narrowed.",
                          {"release": f"{technology.name} has no release {release}."})  # fmt: skip
        statement = statement.where(ComponentTechnology.release_id == row.id)
    if version:
        statement = statement.where(
            func.lower(func.coalesce(ComponentTechnology.version, "")).like(f"{version.lower()}%")
        )
    return statement


def _component_conditions(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[Any]:
    found: list[Any] = []
    if filters.get("application"):
        application = find(session, APPLICATION, str(filters["application"]))
        found.append(Component.application_id == application.id)
    using = built_on(session, filters)
    if using is not None:
        found.append(Component.id.in_(using))
    return found


COMPONENT.extra.update(
    conditions=_component_conditions,
    apply=_component_apply,
    can_add=_component_can_add,
    detail=_component_detail,
    cards=_component_cards,
    add_refusal="Only the people who keep an application can add a component to it.",
    history_vocabularies={"kind": "component_kinds", "hosting": "hosting"},
)


# --- Technologies ----------------------------------------------------------------------------


def _technology_detail(
    session: Session, principal: Principal, record: Technology, shown: Mapping[str, Any]
) -> dict[str, Any]:
    releases = session.scalars(
        select(TechnologyRelease)
        .where(TechnologyRelease.technology_id == record.id)
        .order_by(TechnologyRelease.released_on.desc().nulls_last(), TechnologyRelease.cycle)
    ).all()
    uses = session.execute(
        select(ComponentTechnology, Component, Application)
        .join(Component, Component.id == ComponentTechnology.component_id)
        .join(Application, Application.id == Component.application_id)
        .where(ComponentTechnology.technology_id == record.id)
        .order_by(Application.name, Component.name)
    ).all()
    by_release: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for link, component, application in uses:
        if not access.can_see(session, principal, APPLICATION, application):
            continue
        by_release[link.release_id].append(
            {"component": records.chip(COMPONENT, component),
             "application": records.chip(APPLICATION, application), "version": link.version}
        )  # fmt: skip
    vendor = session.get(Vendor, record.vendor_id) if record.vendor_id else None
    return {
        "vendor": records.chip(VENDOR, vendor) if vendor else None,
        "releases": [
            {**release_view(release), "used_by": by_release.get(release.id, [])}
            for release in releases
        ],
        "unpinned": by_release.get(None, []),
        "use_count": sum(len(items) for items in by_release.values()),
    }


def _technology_cards(
    session: Session, principal: Principal, rows: list[Any]
) -> list[dict[str, Any]]:
    counts: dict[int, int] = defaultdict(int)
    for technology_id in session.scalars(
        select(ComponentTechnology.technology_id).where(
            ComponentTechnology.technology_id.in_([row.id for row in rows])
        )
    ):
        counts[technology_id] += 1
    soonest: dict[int, TechnologyRelease] = {}
    for release in session.scalars(
        select(TechnologyRelease).where(
            TechnologyRelease.technology_id.in_([row.id for row in rows])
        )
    ):
        used = session.scalar(
            select(ComponentTechnology.id).where(ComponentTechnology.release_id == release.id)
        )
        if used and release.support_ends is not None:
            best = soonest.get(release.technology_id)
            if best is None or release.support_ends < best.support_ends:  # type: ignore[operator]
                soonest[release.technology_id] = release
    return [
        {
            "use_count": counts.get(row.id, 0),
            "soonest_end": soonest[row.id].support_ends if row.id in soonest else None,
            "soonest_support": support_state(soonest.get(row.id)) if row.id in soonest else None,
        }
        for row in rows
    ]


TECHNOLOGY.extra.update(
    detail=_technology_detail,
    cards=_technology_cards,
    history_vocabularies={"kind": "technology_kinds", "radar": "radar"},
)


# --- Vendors ---------------------------------------------------------------------------------


def _vendor_detail(
    session: Session, principal: Principal, record: Vendor, shown: Mapping[str, Any]
) -> dict[str, Any]:
    applications = [
        app
        for app in session.scalars(
            select(Application).where(Application.vendor_id == record.id).order_by(Application.name)
        )
        if access.can_see(session, principal, APPLICATION, app)
    ]
    technologies = session.scalars(
        select(Technology).where(Technology.vendor_id == record.id).order_by(Technology.name)
    ).all()
    return {
        "applications": [records.chip(APPLICATION, app) for app in applications],
        "technologies": [records.chip(TECHNOLOGY, tech) for tech in technologies],
    }


VENDOR.extra.update(detail=_vendor_detail, history_vocabularies={"kind": "vendor_kinds"})


# --- Capabilities ----------------------------------------------------------------------------


def _capability_apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    parent = record.parent_id
    seen = {record.id} if record.id is not None else set()
    while parent is not None:
        if parent in seen:
            errors.add("parent_id", "A capability cannot be part of itself.")
            return
        seen.add(parent)
        parent = session.scalar(select(Capability.parent_id).where(Capability.id == parent))


def providers(
    session: Session, principal: Principal, capability_ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    """The applications that serve each capability, the primary first."""
    ids = list(capability_ids)
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids:
        return found
    rows = session.execute(
        select(ApplicationCapability, Application)
        .join(Application, Application.id == ApplicationCapability.application_id)
        .where(ApplicationCapability.capability_id.in_(ids))
        .order_by(ApplicationCapability.is_primary.desc(), Application.name)
    )
    for link, application in rows:
        if access.can_see(session, principal, APPLICATION, application):
            found[link.capability_id].append(
                {**records.chip(APPLICATION, application), "is_primary": link.is_primary,
                 "lifecycle": application.lifecycle}
            )  # fmt: skip
    return found


def _capability_detail(
    session: Session, principal: Principal, record: Capability, shown: Mapping[str, Any]
) -> dict[str, Any]:
    parent = session.get(Capability, record.parent_id) if record.parent_id else None
    children = session.scalars(
        select(Capability)
        .where(Capability.parent_id == record.id)
        .order_by(Capability.position, Capability.name)
    ).all()
    return {
        "parent": records.chip(CAPABILITY, parent) if parent else None,
        "children": [records.chip(CAPABILITY, child) for child in children],
        "applications": providers(session, principal, [record.id]).get(record.id, []),
    }


def _capability_cards(
    session: Session, principal: Principal, rows: list[Any]
) -> list[dict[str, Any]]:
    served = providers(session, principal, [row.id for row in rows])
    return [
        {"application_count": len(served.get(row.id, [])),
         "primary": next((app for app in served.get(row.id, []) if app["is_primary"]), None)}
        for row in rows
    ]  # fmt: skip


CAPABILITY.extra.update(
    apply=_capability_apply,
    detail=_capability_detail,
    cards=_capability_cards,
    history_vocabularies={"domain": "domains"},
)


def tree(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Every capability as a tree, each with how many applications serve it."""
    rows = session.scalars(select(Capability).order_by(Capability.position, Capability.name)).all()
    served = providers(session, principal, [row.id for row in rows])
    nodes = {
        row.id: {**records.chip(CAPABILITY, row), "domain": row.domain, "summary": row.summary,
                 "applications": served.get(row.id, []), "children": []}
        for row in rows
    }  # fmt: skip
    roots = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id in nodes:
            nodes[row.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def load_map(session: Session, principal: Principal, items: list[Mapping[str, Any]]) -> int:
    """Add a capability map from a pack. Capabilities already loaded (by key) are left as the
    organization has shaped them. Returns how many were added."""
    have = {row.key: row for row in session.scalars(select(Capability)) if row.key}
    added = 0

    def place(item: Mapping[str, Any], parent: Capability | None, position: int) -> None:
        nonlocal added
        row = have.get(item["key"])
        if row is None:
            row = records.create(
                session, principal, CAPABILITY,
                {"name": item["name"], "summary": item.get("description"),
                 "parent_id": parent.id if parent else None,
                 "domain": item.get("domain") or (parent.domain if parent else None)},
            )  # fmt: skip
            row.key, row.position = item["key"], position
            have[item["key"]] = row
            added += 1
        for index, child in enumerate(item.get("children", [])):
            place(child, row, index)

    with audit.operation(session, "program.capabilities"):
        for index, item in enumerate(items):
            place(item, None, index)
        session.flush()
    return added
