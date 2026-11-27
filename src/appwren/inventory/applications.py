"""What is particular to applications: the stage they are in, the data they handle, the
capabilities they serve, the units that use them, their components, and what their stage
still requires (INV-02 to INV-13, LND-01).

The generic parts (adding, editing, finding, links, history) are in ``records``; this module
adds what applications need through the registry's hooks.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import (
    Application,
    ApplicationCapability,
    ApplicationUnit,
    Capability,
    Component,
    ComponentTechnology,
    OrgUnit,
    RecordOwner,
    Vendor,
)
from appwren.db.models.inventory import ACCOUNTABLE
from appwren.events import audit
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION, CAPABILITY, COMPONENT, VENDOR
from appwren.program import catalog, vocab

RETIRED_STAGES = ("retired", "archived")


def sensitivity_of(session: Session, classes: Iterable[str] | None) -> int | None:
    """The highest sensitivity of the data classes, or None when none are recorded."""
    levels = {
        item["key"]: int(item.get("sensitivity", 0)) for item in vocab.get(session, "data_classes")
    }
    found = [levels.get(key, 0) for key in classes or []]
    return max(found) if found else None


def _apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if "data_classes" in values or creating:
        record.sensitivity = sensitivity_of(session, record.data_classes)
    if not creating and "lifecycle" in values and _moved(record, "lifecycle"):
        _gate(session, record, errors)
    if ("lifecycle" in values or creating) and record.lifecycle:
        changed = creating or _moved(record, "lifecycle")
        if changed and "lifecycle_since" not in values:
            record.lifecycle_since = today()
        record.status = "retired" if record.lifecycle in RETIRED_STAGES else "active"
    if "fields" in values or creating:
        kept, problems = catalog.clean_values(
            session, record.sourcing, values.get("fields"), record.fields or {}
        )
        for key, message in problems.items():
            errors.add(key, message)
        record.fields = kept
    if record.successor_id is not None and record.successor_id == record.id:
        errors.add("successor_id", "An application cannot replace itself.")
    if "annual_cost" in values and not creating and _moved(record, "annual_cost"):
        from appwren.landscape import costs

        if costs.has_lines(session, record):
            errors.add(
                "annual_cost",
                "Its annual cost is the sum of its cost lines. Change the lines instead.",
            )


REQUIRED = {"accountable": "an accountable owner", "capabilities": "the capabilities it serves",
            "components": "its components", "technologies": "what its components are built on",
            "assessment": "a current assessment", "decision": "a decision"}  # fmt: skip


def _gate(session: Session, record: Application, errors: Errors) -> None:
    """A move to a later stage needs what that stage, and those before it, require (DEC-06).
    A move back, and a retirement, need nothing: what is retired is not kept up."""
    if not catalog.decision_rules(session)["stage_gates"] or record.lifecycle in RETIRED_STAGES:
        return
    stages = vocab.keys(session, "lifecycle", active_only=False)
    before = inspect(record).attrs["lifecycle"].history.deleted
    was = before[0] if before else None
    if record.lifecycle not in stages or (
        was in stages and stages.index(record.lifecycle) <= stages.index(was)
    ):
        return  # fmt: skip
    lacking = missing(session, record)["now"]
    if not lacking:
        return
    labels = {field.name: field.label.lower() for field in APPLICATION.fields}
    labels.update({item["key"]: item["label"].lower() for item in catalog.fields(session)})
    said = ", ".join(REQUIRED.get(name) or labels.get(name, name) for name in lacking)
    stage = vocab.labels(session, "lifecycle").get(record.lifecycle, record.lifecycle)
    errors.add("lifecycle", f"Before it moves to {stage}, record {said}.")


def _moved(record: Any, name: str) -> bool:
    """Whether an attribute now holds a different value from the one loaded."""
    history = inspect(record).attrs[name].history
    before = history.deleted[0] if history.deleted else None
    after = history.added[0] if history.added else None
    return bool(history.added) and before != after


def _changed(session: Session, principal: Principal, record: Any) -> None:
    """A component belongs to its application's unit, wherever the application moves."""
    for component in session.scalars(
        select(Component).where(Component.application_id == record.id)
    ):
        if component.org_unit_id != record.org_unit_id:
            component.org_unit_id = record.org_unit_id


# --- Capabilities ---------------------------------------------------------------------------


def set_capabilities(
    session: Session,
    principal: Principal,
    application: Application,
    wanted: list[Mapping[str, Any]],
) -> None:
    """What the application does for the organization. At most one active application is the
    primary provider of any capability."""
    if not access.can_edit(session, principal, APPLICATION, application):
        raise PermissionDenied("You cannot edit this application.")
    errors = Errors()
    chosen: dict[int, tuple[bool, str | None]] = {}
    for index, item in enumerate(wanted):
        capability_id = records.reference(
            session, "capability", item.get("capability"), f"capabilities[{index}]", errors
        )
        if capability_id is None:
            continue
        note = records.text(item.get("note"))
        chosen[capability_id] = (bool(item.get("is_primary")), note[:300] if note else None)
    for capability_id, (primary, _) in chosen.items():
        if not primary:
            continue
        other = session.scalars(
            select(Application)
            .join(ApplicationCapability, ApplicationCapability.application_id == Application.id)
            .where(
                ApplicationCapability.capability_id == capability_id,
                ApplicationCapability.is_primary.is_(True),
                Application.id != application.id,
                Application.status == "active",
            )
        ).first()
        if other is not None:
            name = session.get(Capability, capability_id).name  # type: ignore[union-attr]
            seen = access.sees_application(session, principal, other)
            who = f"{other.name} ({other.ref})" if seen else "An application you may not see"
            errors.add(
                "capabilities",
                f"{who} is already the primary provider of {name}. Change that first.",
            )
    if errors:
        raise Invalid("The capabilities were not saved.", errors)
    have = {
        row.capability_id: row
        for row in session.scalars(
            select(ApplicationCapability).where(
                ApplicationCapability.application_id == application.id
            )
        )
    }
    with audit.operation(session, "application.capabilities"):
        for capability_id, row in have.items():
            if capability_id not in chosen:
                session.delete(row)
        for capability_id, (primary, note) in chosen.items():
            row = have.get(capability_id)
            if row is None:
                session.add(
                    ApplicationCapability(
                        application_id=application.id,
                        capability_id=capability_id,
                        is_primary=primary,
                        note=note,
                    )
                )
            else:
                row.is_primary, row.note = primary, note
        session.flush()


def capabilities_of(session: Session, application_ids: Iterable[int]) -> dict[int, list[dict]]:
    ids = list(application_ids)
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids:
        return found
    rows = session.execute(
        select(ApplicationCapability, Capability)
        .join(Capability, Capability.id == ApplicationCapability.capability_id)
        .where(ApplicationCapability.application_id.in_(ids))
        .order_by(Capability.name)
    )
    for link, capability in rows:
        found[link.application_id].append(
            {**records.chip(CAPABILITY, capability), "is_primary": link.is_primary,
             "note": link.note}
        )  # fmt: skip
    return found


# --- Units that use it ----------------------------------------------------------------------


def set_units(
    session: Session, principal: Principal, application: Application, unit_ids: list[int]
) -> None:
    if not access.can_edit(session, principal, APPLICATION, application):
        raise PermissionDenied("You cannot edit this application.")
    wanted = list(dict.fromkeys(int(value) for value in unit_ids))
    known = set(session.scalars(select(OrgUnit.id).where(OrgUnit.id.in_(wanted))))
    if missing := [value for value in wanted if value not in known]:
        raise Invalid("The units were not saved.", {"units": f"There is no unit {missing[0]}."})
    have = {
        row.org_unit_id: row
        for row in session.scalars(
            select(ApplicationUnit).where(ApplicationUnit.application_id == application.id)
        )
    }
    with audit.operation(session, "application.units"):
        for unit_id, row in have.items():
            if unit_id not in wanted:
                session.delete(row)
        for unit_id in wanted:
            if unit_id not in have:
                session.add(ApplicationUnit(application_id=application.id, org_unit_id=unit_id))
        session.flush()


def set_use(
    session: Session,
    principal: Principal,
    application: Application,
    values: Mapping[str, Any],
    *,
    version: int | None,
) -> None:
    """Who uses it, in one change: everyone in the organization, or the units that use it
    together with the kinds of people who use it wherever they work; about how many people;
    and whether people outside the organization do. Everyone includes every unit and kind,
    so naming everyone clears the units and kinds."""
    everyone = bool(values.get("org_wide"))
    records.update(
        session, principal, APPLICATION, application,
        {"org_wide": everyone,
         "audiences": [] if everyone else list(values.get("audiences") or []),
         "users": values.get("users"), "external_users": values.get("external_users")},
        version=version,
    )  # fmt: skip
    set_units(session, principal, application, [] if everyone else list(values.get("units") or []))


def units_of(session: Session, application_ids: Iterable[int]) -> dict[int, list[int]]:
    ids = list(application_ids)
    found: dict[int, list[int]] = defaultdict(list)
    if ids:
        for row in session.scalars(
            select(ApplicationUnit).where(ApplicationUnit.application_id.in_(ids))
        ):
            found[row.application_id].append(row.org_unit_id)
    return found


# --- What its stage still requires ----------------------------------------------------------


def _has(session: Session, application: Application, name: str) -> bool:
    if name == "accountable":
        return bool(
            session.scalar(
                select(func.count(RecordOwner.id)).where(
                    RecordOwner.record_type == APPLICATION.key,
                    RecordOwner.record_id == application.id,
                    RecordOwner.kind == ACCOUNTABLE,
                )
            )
        )
    if name == "capabilities":
        return bool(
            session.scalar(
                select(func.count(ApplicationCapability.id)).where(
                    ApplicationCapability.application_id == application.id
                )
            )
        )
    if name == "components":
        return bool(
            session.scalar(
                select(func.count(Component.id)).where(Component.application_id == application.id)
            )
        )
    if name == "technologies":
        if application.sourcing in ("saas", "vendor_custom"):
            return True  # the vendor runs the technology
        return bool(
            session.scalar(
                select(func.count(ComponentTechnology.id))
                .join(Component, Component.id == ComponentTechnology.component_id)
                .where(Component.application_id == application.id)
            )
        )
    if name in ("assessment", "decision"):
        checker = HAS.get(name)
        return True if checker is None else bool(checker(session, application))
    value = getattr(application, name, None)
    if value is None and name in {item["key"] for item in catalog.fields(session)}:
        value = (application.fields or {}).get(name)
    return value not in (None, "", [])


# Later slices say how to tell whether an application has an assessment or a decision.
HAS: dict[str, Any] = {}


def missing(session: Session, application: Application) -> dict[str, Any]:
    """What the application's stage requires that it lacks, and what the next stage would."""
    return missing_from(
        application,
        lambda name: _has(session, application, name),
        vocab.keys(session, "lifecycle", active_only=False),
        catalog.stage_requirements(session),
    )


def missing_from(
    application: Application,
    has: Callable[[str], bool],
    stages: list[str],
    rules: Mapping[str, list[str]],
) -> dict[str, Any]:
    """The same, from an answer to "does it have this?" that the caller already knows, so a
    whole portfolio can be checked without asking the database about each application."""
    position = stages.index(application.lifecycle) if application.lifecycle in stages else 0
    needed: list[str] = []
    for stage in stages[: position + 1]:
        needed += [name for name in rules.get(stage, []) if name not in needed]
    following = stages[position + 1] if position + 1 < len(stages) else None
    upcoming = (
        [name for name in rules.get(following, []) if name not in needed] if following else []
    )
    return {
        "now": [name for name in needed if not has(name)],
        "next_stage": following,
        "next": [name for name in upcoming if not has(name)],
    }


def field_present(application: Application, name: str, own: set[str]) -> bool:
    """Whether a field of the application, or one of the organization's own, has a value."""
    value = getattr(application, name, None)
    if value is None and name in own:
        value = (application.fields or {}).get(name)
    return value not in (None, "", [])


# --- Showing --------------------------------------------------------------------------------


def _cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
    vendors = {
        vendor.id: vendor
        for vendor in session.scalars(
            select(Vendor).where(Vendor.id.in_({row.vendor_id for row in rows if row.vendor_id}))
        )
    }
    return [
        {"vendor": records.chip(VENDOR, vendors[row.vendor_id]) if row.vendor_id in vendors
         else None}
        for row in rows
    ]  # fmt: skip


def _detail(
    session: Session, principal: Principal, record: Application, shown: Mapping[str, Any]
) -> dict[str, Any]:
    components = session.scalars(
        select(Component).where(Component.application_id == record.id).order_by(Component.name)
    ).all()
    successor = session.get(Application, record.successor_id) if record.successor_id else None
    replaces = session.scalars(
        select(Application).where(Application.successor_id == record.id)
    ).all()
    support = session.get(OrgUnit, record.support_unit_id) if record.support_unit_id else None
    hidden = set(shown.get("withheld", ()))
    own_fields = [
        item for item in catalog.fields(session)
        if not item.get("applies_to") or record.sourcing in item["applies_to"]
    ]  # fmt: skip
    return {
        "aliases": record.aliases or [],
        "lifecycle_since": record.lifecycle_since,
        "components": [
            {
                **records.chip(COMPONENT, component),
                "kind": component.kind,
                "repo_url": component.repo_url,
            }
            for component in components
        ],
        "capabilities": capabilities_of(session, [record.id]).get(record.id, []),
        "used_by": units_of(session, [record.id]).get(record.id, []),
        "support_unit": {"id": support.id, "name": support.name} if support else None,
        # An application the reader may not see is not named, here or anywhere.
        "successor": records.chip(APPLICATION, successor)
        if successor and access.sees_application(session, principal, successor)
        else None,
        "replaces": [
            records.chip(APPLICATION, other)
            for other in replaces
            if access.sees_application(session, principal, other)
        ],
        "fields": {key: value for key, value in (record.fields or {}).items() if key not in hidden},
        "own_fields": own_fields,
        "missing": missing(session, record),
        "sees_sensitive": not hidden,
        "has_cost_lines": _has_cost_lines(session, record),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    """What narrows a list of applications beyond its own columns."""
    found: list[Any] = []
    if filters.get("data_class"):
        found.append(records.holds(Application.data_classes, str(filters["data_class"])))
    if filters.get("audience") == "everyone":
        found.append(Application.org_wide.is_(True))
    elif filters.get("audience"):
        found.append(records.holds(Application.audiences, str(filters["audience"])))
    if filters.get("used_in"):
        # Everyone in a unit uses what the whole organization uses, and what any unit it is
        # part of uses. What kinds of people use wherever they work is not counted: who in
        # the unit is which kind is not recorded.
        from appwren.people import units

        within = [unit.id for unit in units.ancestors(session, int(filters["used_in"]))]
        within.append(int(filters["used_in"]))
        found.append(
            or_(
                Application.org_wide.is_(True),
                Application.id.in_(
                    select(ApplicationUnit.application_id).where(
                        ApplicationUnit.org_unit_id.in_(within)
                    )
                ),
            )
        )
    if filters.get("capability"):
        from appwren.inventory.registry import find

        capability = find(session, CAPABILITY, str(filters["capability"]))
        found.append(
            Application.id.in_(
                select(ApplicationCapability.application_id).where(
                    ApplicationCapability.capability_id == capability.id
                )
            )
        )
    if filters.get("maturity"):
        from appwren.inventory import maturity

        found.append(
            Application.id.in_(maturity.applications_at(session, str(filters["maturity"])))
        )
    from appwren.inventory.parts import built_on

    using = built_on(session, filters)
    if using is not None:  # any of its components built on it
        found.append(
            Application.id.in_(select(Component.application_id).where(Component.id.in_(using)))
        )
    return found


def _has_cost_lines(session: Session, record: Application) -> bool:
    from appwren.landscape import costs

    return costs.has_lines(session, record)


def _can_add(session: Session, principal: Principal, record: Application) -> bool:
    return access.can_add(principal, APPLICATION, record.org_unit_id)


APPLICATION.extra.update(
    apply=_apply,
    changed=_changed,
    cards=_cards,
    detail=_detail,
    can_add=_can_add,
    # The fields each filter beyond the columns reads, so a sensitive one is honoured.
    filter_fields={
        "data_class": ("data_classes",),
        "audience": ("audiences", "org_wide"),
        "used_in": ("org_wide",),
    },
    conditions=_conditions,
    add_refusal="Only a steward of the unit, an architect, or a manager can add an application "
    "to it.",
    history_vocabularies={"data_classes": "data_classes"},
    history_labels={"fields": "The organization's fields"},
    # Copies of the decision on record, kept for lists: the decision's own entry tells them.
    history_quiet=("disposition", "review_on"),
)
