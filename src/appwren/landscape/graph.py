"""How one record connects to the others, and what breaks if an application goes (LND-04).

A record's neighbors, grouped by what joins them. Each neighbor is one the person may see;
the rest are counted. The picture and the list beside it are drawn from this one answer, so
they cannot disagree.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.db.models import (
    Application,
    ApplicationCapability,
    ApplicationUnit,
    Capability,
    Component,
    ComponentTechnology,
    Interface,
    OrgUnit,
    RecordLink,
    Technology,
)
from appwren.inventory import access, links, records
from appwren.inventory.registry import APPLICATION, CAPABILITY, INTERFACE, TYPES, RecordType

Edge = tuple[str, str, str, int]  # a group's key and label, and the neighbor's type and id

# Other modules add what joins their own records: (session, type key, record id) -> edges.
MORE_EDGES: list[Any] = []


def _edges(session: Session, key: str, record_id: int) -> list[Edge]:
    """Everything joined to a record, whatever it is, before anyone asks who may see it."""
    found: list[Edge] = []
    kinds = links.kinds(session)
    for row in session.scalars(
        select(RecordLink)
        .where(
            or_(
                (RecordLink.from_type == key) & (RecordLink.from_id == record_id),
                (RecordLink.to_type == key) & (RecordLink.to_id == record_id),
            )
        )
        .order_by(RecordLink.id)
    ):
        forward = row.from_type == key and row.from_id == record_id
        kind = kinds.get(row.relation, {})
        label = str(kind.get("label" if forward else "reverse", row.relation))
        other = (row.to_type, row.to_id) if forward else (row.from_type, row.from_id)
        found.append((f"{row.relation}:{'out' if forward else 'in'}", label, *other))

    def add(group: str, label: str, other_type: str, ids: Any) -> None:
        found.extend((group, label, other_type, int(each)) for each in ids if each is not None)

    if key == "application":
        app = session.get(Application, record_id)
        add("sends", "Sends data to", "application", session.scalars(
            select(Interface.target_id)
            .where(Interface.source_id == record_id, Interface.status == "active")
            .order_by(Interface.id)
        ))  # fmt: skip
        add("receives", "Receives data from", "application", session.scalars(
            select(Interface.source_id)
            .where(Interface.target_id == record_id, Interface.status == "active")
            .order_by(Interface.id)
        ))  # fmt: skip
        add("serves", "Serves", "capability", session.scalars(
            select(ApplicationCapability.capability_id)
            .where(ApplicationCapability.application_id == record_id)
            .order_by(ApplicationCapability.id)
        ))  # fmt: skip
        add("made_of", "Made of", "component", session.scalars(
            select(Component.id)
            .where(Component.application_id == record_id)
            .order_by(Component.name)
        ))  # fmt: skip
        add("built_on", "Built on", "technology", session.scalars(
            select(ComponentTechnology.technology_id)
            .join(Component, Component.id == ComponentTechnology.component_id)
            .where(Component.application_id == record_id, Component.status == "active")
            .order_by(ComponentTechnology.technology_id)
        ))  # fmt: skip
        if app is not None:
            add("supplied_by", "Supplied by", "vendor", [app.vendor_id])
            add("replaced_by", "Replaced by", "application", [app.successor_id])
        add("replaces", "Takes over from", "application", session.scalars(
            select(Application.id).where(Application.successor_id == record_id)
        ))  # fmt: skip
    elif key == "component":
        component = session.get(Component, record_id)
        if component is not None:
            add("part_of", "A part of", "application", [component.application_id])
        add("built_on", "Built on", "technology", session.scalars(
            select(ComponentTechnology.technology_id)
            .where(ComponentTechnology.component_id == record_id)
            .order_by(ComponentTechnology.id)
        ))  # fmt: skip
    elif key == "capability":
        capability = session.get(Capability, record_id)
        add("served_by", "Served by", "application", session.scalars(
            select(ApplicationCapability.application_id)
            .where(ApplicationCapability.capability_id == record_id)
            .order_by(ApplicationCapability.id)
        ))  # fmt: skip
        if capability is not None:
            add("within", "A part of", "capability", [capability.parent_id])
        add("includes", "Includes", "capability", session.scalars(
            select(Capability.id).where(Capability.parent_id == record_id).order_by(Capability.name)
        ))  # fmt: skip
    elif key == "technology":
        technology = session.get(Technology, record_id)
        add("used_by", "Used by", "component", session.scalars(
            select(ComponentTechnology.component_id)
            .where(ComponentTechnology.technology_id == record_id)
            .order_by(ComponentTechnology.id)
        ))  # fmt: skip
        if technology is not None:
            add("supplied_by", "Supplied by", "vendor", [technology.vendor_id])
    elif key == "vendor":
        add("supplies", "Supplies", "application", session.scalars(
            select(Application.id)
            .where(Application.vendor_id == record_id)
            .order_by(Application.name)
        ))  # fmt: skip
        add("makes", "Makes", "technology", session.scalars(
            select(Technology.id).where(Technology.vendor_id == record_id).order_by(Technology.name)
        ))  # fmt: skip
    elif key == "interface":
        interface = session.get(Interface, record_id)
        if interface is not None:
            add("from", "From", "application", [interface.source_id])
            add("to", "To", "application", [interface.target_id])
    for more in MORE_EDGES:
        found.extend(more(session, key, record_id))
    return found


def around(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> dict[str, Any]:
    """A record and its neighbors, in groups, cut to what the person may see."""
    groups: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str, int]] = set()
    hidden = 0
    for group, label, other_key, other_id in _edges(session, record_type.key, record.id):
        if (group, other_key, other_id) in seen:
            continue
        seen.add((group, other_key, other_id))
        other_type = TYPES.get(other_key)
        other = session.get(other_type.model, other_id) if other_type is not None else None
        if other is None or other_type is None:
            continue
        if not access.can_see(session, principal, other_type, other):
            hidden += 1
            continue
        entry = groups.setdefault(group, {"key": group, "label": label, "records": []})
        entry["records"].append(records.chip(other_type, other))
    found = list(groups.values())
    return {
        "center": records.chip(record_type, record),
        "groups": found,
        "count": sum(len(group["records"]) for group in found),
        "hidden": hidden,
    }


# --- What breaks if this goes ---------------------------------------------------------------


def _relying(session: Session, ids: set[int]) -> dict[int, set[int]]:
    """For each application, the active applications that depend on it: by a recorded
    dependency, or by receiving its data. The same rule the engine counts dependents by."""
    from appwren.landscape import interfaces

    out: dict[int, set[int]] = {app_id: set() for app_id in ids}
    for target, source in session.execute(
        select(RecordLink.to_id, RecordLink.from_id)
        .join(Application, Application.id == RecordLink.from_id)
        .where(
            RecordLink.from_type == "application",
            RecordLink.to_type == "application",
            RecordLink.relation == "depends_on",
            RecordLink.to_id.in_(ids),
            Application.status == "active",
        )
    ):
        out[target].add(source)
    for source, receivers in interfaces.consumers(session, ids).items():
        out[source] |= receivers
    return {app_id: found - {app_id} for app_id, found in out.items()}


def impact(session: Session, principal: Principal, application: Application) -> dict[str, Any]:
    """What would be touched if this application stopped: what depends on it, directly and
    beyond; the interfaces that would stop; the capabilities left with nothing, or without
    their primary; and the people who use any of it. Nothing the person may not see is named;
    it is counted."""
    # Whatever depends on it, ring by ring.
    depth: dict[int, int] = {}
    queue: deque[tuple[int, int]] = deque([(application.id, 0)])
    while queue:
        current, level = queue.popleft()
        for other in sorted(_relying(session, {current})[current]):
            if other != application.id and other not in depth:
                depth[other] = level + 1
                queue.append((other, level + 1))
    apps = {
        app.id: app for app in session.scalars(select(Application).where(Application.id.in_(depth)))
    }
    direct: list[dict[str, Any]] = []
    beyond: list[dict[str, Any]] = []
    hidden = 0
    people = int(application.users or 0)
    for app_id, level in sorted(depth.items(), key=lambda item: (item[1], apps[item[0]].name)):
        app = apps[app_id]
        if not access.sees_application(session, principal, app):
            hidden += 1
            continue
        people += int(app.users or 0)
        entry = {**records.chip(APPLICATION, app), "tier": app.tier, "users": app.users}
        (direct if level == 1 else beyond).append(entry)
    # The interfaces at either end of it.
    rows, _ = records.search(
        session, principal, INTERFACE,
        {"status": "active", "application": application.ref}, sort="name", limit=500,
    )  # fmt: skip
    interfaces_ = records.cards(session, principal, INTERFACE, rows)
    # The capabilities it serves, and who else does.
    left: list[dict[str, Any]] = []
    weakened: list[dict[str, Any]] = []
    mine = session.execute(
        select(ApplicationCapability.capability_id, ApplicationCapability.is_primary).where(
            ApplicationCapability.application_id == application.id
        )
    ).all()
    for capability_id, is_primary in mine:
        capability = session.get(Capability, capability_id)
        if capability is None:
            continue
        others = session.scalars(
            select(Application)
            .join(ApplicationCapability, ApplicationCapability.application_id == Application.id)
            .where(
                ApplicationCapability.capability_id == capability_id,
                Application.id != application.id,
                Application.status == "active",
            )
            .order_by(Application.name)
        ).all()
        shown = [
            records.chip(APPLICATION, other)
            for other in others
            if access.sees_application(session, principal, other)
        ]
        entry = {**records.chip(CAPABILITY, capability), "others": shown}
        if not others:
            left.append(entry)
        elif is_primary:
            weakened.append(entry)
    units = session.scalars(
        select(OrgUnit)
        .join(ApplicationUnit, ApplicationUnit.org_unit_id == OrgUnit.id)
        .where(ApplicationUnit.application_id == application.id)
        .order_by(OrgUnit.name)
    ).all()
    components = session.scalar(
        select(Component.id)
        .where(Component.application_id == application.id, Component.status == "active")
        .limit(1)
    )
    return {
        "application": records.chip(APPLICATION, application),
        "direct": direct,
        "beyond": beyond,
        "hidden": hidden,
        "interfaces": [
            {key: row[key] for key in ("ref", "name", "source", "target", "method", "data_classes")}
            for row in interfaces_
        ],
        "capabilities_left": left,
        "capabilities_weakened": weakened,
        "users": application.users,
        "external_users": bool(application.external_users),
        "people": people,
        "units": [{"id": unit.id, "name": unit.name} for unit in units],
        "research_continuity": bool(application.research_continuity),
        "regulated_record": bool(application.regulated_record),
        "records_retention": bool(application.records_retention),
        "has_components": components is not None,
    }
