"""Initiatives and the roadmap: what the decisions commit the organization to, with dates
(PLN-02).

An initiative is a planned change (a modernization, a migration, a consolidation, a
replacement, a retirement, or another) with the applications it changes and what it does to
each: changes it, retires it, or moves work onto it. It has an owner, a stage, and dates, and
shows the decision on record for each of its applications. The roadmap puts initiatives on a
timeline. An application's page lists every initiative that names it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import Account, Application, Decision, Initiative, InitiativeApplication
from appwren.inventory import access, records
from appwren.inventory import applications as _first  # noqa: F401  (its detail is wrapped)
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION, INITIATIVE
from appwren.people import units
from appwren.program import vocab

ACTIONS = {"changes": "Changes it", "retires": "Retires it", "receives": "Moves work onto it"}
CLOSED = {"done", "cancelled"}


def _keeps(principal: Principal, record: Initiative) -> bool:
    return (principal.account_id is not None and principal.account_id == record.owner_id) or any(
        principal.covers(role, record.org_unit_id) for role in access.KEEPERS
    )


def _apply(
    session: Session, record: Initiative, values: Mapping[str, Any], errors: Errors,
    creating: bool,
) -> None:  # fmt: skip
    if record.starts_on and record.ends_on and record.ends_on < record.starts_on:
        errors.add("ends_on", "It cannot end before it starts.")


def set_applications(
    session: Session, principal: Principal, record: Initiative, wanted: list[Mapping[str, Any]]
) -> None:
    """The applications it changes, and what it does to each. Replaces those it had."""
    if not _keeps(principal, record):
        raise PermissionDenied("Only whoever keeps the initiative changes what it names.")
    errors = Errors()
    chosen: dict[int, tuple[str, str | None]] = {}
    for index, item in enumerate(wanted):
        where = f"applications[{index}]"
        ref = str(item.get("application") or "").strip()
        try:
            app = records.load(session, principal, APPLICATION, ref)
        except Exception:
            errors.add(where, f"There is no application {ref or '(none given)'}.")
            continue
        action = str(item.get("action") or "changes")
        if action not in ACTIONS:
            errors.add(where, "Say whether it changes, retires, or moves work onto it.")
            continue
        if app.id in chosen:
            errors.add(where, f"{app.name} appears twice.")
            continue
        note = " ".join(str(item.get("note") or "").split())[:500] or None
        chosen[app.id] = (action, note)
    if errors:
        raise Invalid("The applications were not saved.", errors)
    have = {
        row.application_id: row
        for row in session.scalars(
            select(InitiativeApplication).where(InitiativeApplication.initiative_id == record.id)
        )
    }
    for app_id, row in have.items():
        if app_id not in chosen:
            app = session.get(Application, app_id)
            # One the person may not see stays as it was: it is not theirs to remove.
            if app is not None and access.sees_application(session, principal, app):
                session.delete(row)
    for app_id, (action, note) in chosen.items():
        row = have.get(app_id)
        if row is None:
            session.add(InitiativeApplication(initiative_id=record.id, application_id=app_id,
                                              action=action, note=note))  # fmt: skip
        else:
            row.action, row.note = action, note
    records.touch(session, record)
    session.flush()


def _decisions(session: Session, app_ids: list[int]) -> dict[int, Decision]:
    if not app_ids:
        return {}
    return {
        row.application_id: row
        for row in session.scalars(
            select(Decision).where(
                Decision.application_id.in_(app_ids), Decision.superseded_by.is_(None)
            )
        )
    }


def _applications(
    session: Session, principal: Principal, record: Initiative
) -> tuple[list[dict[str, Any]], int]:
    rows = list(session.execute(
        select(InitiativeApplication, Application)
        .join(Application, Application.id == InitiativeApplication.application_id)
        .where(InitiativeApplication.initiative_id == record.id)
        .order_by(Application.name)
    ))  # fmt: skip
    seen = [(link, app) for link, app in rows if access.sees_application(session, principal, app)]
    decided = _decisions(session, [app.id for _, app in seen])
    out = []
    for link, app in seen:
        decision = decided.get(app.id)
        out.append({
            **records.chip(APPLICATION, app),
            "lifecycle": app.lifecycle,
            "action": link.action,
            "action_label": ACTIONS[link.action],
            "note": link.note,
            "decision": {"ref": decision.ref, "disposition": decision.disposition,
                         "decided_on": decision.decided_on, "target_on": decision.target_on,
                         "by": decision.decided_by_name} if decision else None,
        })  # fmt: skip
    return out, len(rows) - len(seen)


def _detail(
    session: Session, principal: Principal, record: Initiative, shown: Mapping[str, Any]
) -> dict[str, Any]:
    owner = session.get(Account, record.owner_id) if record.owner_id else None
    applications, hidden = _applications(session, principal, record)
    return {
        "owner": {"id": owner.id, "name": owner.display_name} if owner else None,
        "applications": applications,
        "hidden_applications": hidden,
        "may_keep": _keeps(principal, record),
    }


def _cards(session: Session, principal: Principal, rows: list[Initiative]) -> list[dict[str, Any]]:
    counts: dict[int, int] = defaultdict(int)
    if rows:
        for (initiative_id,) in session.execute(
            select(InitiativeApplication.initiative_id).where(
                InitiativeApplication.initiative_id.in_([row.id for row in rows])
            )
        ):
            counts[initiative_id] += 1
    owners = {
        account.id: account.display_name
        for account in session.scalars(
            select(Account).where(Account.id.in_({row.owner_id for row in rows if row.owner_id}))
        )
    } if rows else {}  # fmt: skip
    return [
        {"kind": row.kind, "stage": row.stage, "starts_on": row.starts_on, "ends_on": row.ends_on,
         "applications": counts.get(row.id, 0), "owner": owners.get(row.owner_id)}
        for row in rows
    ]  # fmt: skip


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("application"):
        app = records.load(session, principal, APPLICATION, str(filters["application"]))
        found.append(
            Initiative.id.in_(
                select(InitiativeApplication.initiative_id).where(
                    InitiativeApplication.application_id == app.id
                )
            )
        )
    return found


def of_application(
    session: Session, principal: Principal, app: Application
) -> list[dict[str, Any]]:
    """Every initiative that names an application, and what it does to it."""
    rows = session.execute(
        select(Initiative, InitiativeApplication)
        .join(InitiativeApplication, InitiativeApplication.initiative_id == Initiative.id)
        .where(InitiativeApplication.application_id == app.id, Initiative.status == "active")
        .order_by(Initiative.ends_on.is_(None), Initiative.ends_on, Initiative.name)
    )
    return [
        {**records.chip(INITIATIVE, initiative), "kind": initiative.kind,
         "stage": initiative.stage, "ends_on": initiative.ends_on,
         "action": link.action, "action_label": ACTIONS[link.action]}
        for initiative, link in rows
    ]  # fmt: skip


def roadmap(session: Session, principal: Principal, filters: Mapping[str, Any]) -> dict[str, Any]:
    """Initiatives with their dates, for a timeline: those in a unit and the units beneath it,
    of a kind, or at a stage; finished and cancelled ones only when asked for."""
    statement = select(Initiative).where(Initiative.status == "active")
    if filters.get("unit"):
        statement = statement.where(
            Initiative.org_unit_id.in_(units.with_descendants(session, [int(filters["unit"])]))
        )
    if filters.get("kind"):
        statement = statement.where(Initiative.kind == str(filters["kind"]))
    if filters.get("stage"):
        statement = statement.where(Initiative.stage == str(filters["stage"]))
    elif not filters.get("closed"):
        statement = statement.where(Initiative.stage.not_in(CLOSED))
    rows = list(session.scalars(statement))
    cards = _cards(session, principal, rows)
    names = {unit.id: unit.name for unit in units.all_units(session)}
    out = []
    for row, card in zip(rows, cards, strict=True):
        unit = {"id": row.org_unit_id, "name": names.get(row.org_unit_id)}
        out.append({**records.chip(INITIATIVE, row), **card, "unit": unit})
    out.sort(key=lambda item: (item["starts_on"] or item["ends_on"] or date.max, item["name"]))
    dated = [d for item in out for d in (item["starts_on"], item["ends_on"]) if d]
    on = today()
    return {
        "today": on,
        "from": min([*dated, on]).replace(month=1, day=1),
        "to": max([*dated, on]).replace(month=12, day=31),
        "initiatives": out,
        "undated": sum(1 for item in out if not item["starts_on"] and not item["ends_on"]),
        "kinds": [item["key"] for item in vocab.get(session, "initiative_kinds")],
    }


INITIATIVE.extra.update(
    can_edit=lambda session, principal, record: _keeps(principal, record),
    can_see=lambda session, principal, record: True,
    visible_to=lambda session, principal: None,
    apply=_apply,
    detail=_detail,
    cards=_cards,
    conditions=_conditions,
    add_refusal="Only a steward of the unit, an architect, or a manager can add an initiative "
    "for it.",
)


def _with_initiatives() -> None:
    """An application's page lists the initiatives that change it."""
    original = APPLICATION.extra.get("detail")

    def detail(
        session: Session, principal: Principal, record: Application, shown: Mapping[str, Any]
    ) -> dict[str, Any]:
        out = original(session, principal, record, shown) if original else {}
        return {**out, "initiatives": of_application(session, principal, record)}

    APPLICATION.extra["detail"] = detail


_with_initiatives()
