"""Interfaces: data passing from one application to another, and where each class of data
travels (LND-03).

An interface is seen by whoever may see both of its applications, and kept by whoever keeps
either. An application that receives data depends on the one that sends it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid
from appwren.db.models import Account, Application, Interface
from appwren.inventory import access, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION, INTERFACE, find
from appwren.program import vocab

MAX_FLOWS = 5000


def _ends(session: Session, record: Interface) -> list[Any]:
    ids = [value for value in (record.source_id, record.target_id) if value is not None]
    found = [session.get(Application, value) for value in ids]
    return [app for app in found if app is not None]


def _visible(seen: Any) -> Any:
    return and_(Interface.source_id.in_(seen), Interface.target_id.in_(seen))


def _apply(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if record.source_id is not None and record.source_id == record.target_id:
        errors.add("target_id", "An interface joins two different applications.")
    # Hidden with either of its applications, and shown as restricted where it is seen.
    record.restricted = any(app.restricted for app in _ends(session, record))


def _both_seen(session: Session, principal: Principal, record: Any) -> None:
    """An application the person may not see does not exist, as far as they can tell."""
    for name in ("source_id", "target_id"):
        app = next((a for a in _ends(session, record) if a.id == getattr(record, name)), None)
        if app is not None and not access.sees_application(session, principal, app):
            if record in session:
                session.expire(record)
            raise Invalid(
                "The interface was not saved.", {name: f"There is no application {app.ref}."}
            )


def _can_add(session: Session, principal: Principal, record: Any) -> bool:
    _both_seen(session, principal, record)
    return any(access.keeps(session, principal, app) for app in _ends(session, record))


def _changed(session: Session, principal: Principal, record: Any) -> None:
    _both_seen(session, principal, record)


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("application"):
        app = find(session, APPLICATION, str(filters["application"]))
        found.append(or_(Interface.source_id == app.id, Interface.target_id == app.id))
    if filters.get("data_class"):
        found.append(records.holds(Interface.data_classes, str(filters["data_class"])))
    return found


def undeclared(interface: Any, target: Any) -> list[str]:
    """The classes an interface carries that the receiving application's record does not
    list: either the interface or the record is wrong, and somebody should look."""
    held = set(target.data_classes or []) if target is not None else set()
    return [key for key in interface.data_classes or [] if key not in held]


def _cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
    ids = {row.source_id for row in rows} | {row.target_id for row in rows}
    apps = {
        app.id: app for app in session.scalars(select(Application).where(Application.id.in_(ids)))
    }
    owners = {
        account.id: account
        for account in session.scalars(
            select(Account).where(Account.id.in_({row.owner_id for row in rows if row.owner_id}))
        )
    }
    out = []
    for row in rows:
        source, target = apps.get(row.source_id), apps.get(row.target_id)
        owner = owners.get(row.owner_id)
        out.append(
            {
                "source": records.chip(APPLICATION, source) if source else None,
                "target": records.chip(APPLICATION, target) if target else None,
                "owner": {"id": owner.id, "name": owner.display_name} if owner else None,
                "undeclared": undeclared(row, target),
            }
        )
    return out


def _detail(
    session: Session, principal: Principal, record: Interface, shown: Mapping[str, Any]
) -> dict[str, Any]:
    return {}


INTERFACE.extra.update(
    applications=_ends,
    visible=_visible,
    apply=_apply,
    can_add=_can_add,
    changed=_changed,
    conditions=_conditions,
    cards=_cards,
    detail=_detail,
    add_refusal="Only the people who keep one of its two applications can add an interface.",
    moves=("source_id", "target_id"),
    move_refusal="An interface may join only applications one of which you keep.",
    history_vocabularies={"data_classes": "data_classes"},
)


def consumers(session: Session, application_ids: Iterable[int]) -> dict[int, set[int]]:
    """For each application, the active applications that receive its data through an active
    interface. They depend on it as surely as a recorded dependency says."""
    out: dict[int, set[int]] = defaultdict(set)
    rows = session.execute(
        select(Interface.source_id, Interface.target_id)
        .join(Application, Application.id == Interface.target_id)
        .where(
            Interface.source_id.in_(list(application_ids)),
            Interface.status == "active",
            Application.status == "active",
        )
    )
    for source, target in rows:
        out[source].add(target)
    return out


def flows(session: Session, principal: Principal, data_class: str | None) -> dict[str, Any]:
    """Where each class of data travels: how many interfaces carry each class, and, for a
    chosen class, every interface that carries it and every application that holds it."""
    classes = [item for item in vocab.get(session, "data_classes") if not item.get("retired")]
    keys = {item["key"] for item in classes}
    if data_class is not None and data_class not in keys:
        raise Invalid("There is no such class of data.", {"data_class": "Choose one of the list."})
    rows, _ = records.search(
        session, principal, INTERFACE, {"status": "active"}, sort="name", limit=MAX_FLOWS
    )
    cards = records.cards(session, principal, INTERFACE, rows)
    counts: dict[str, int] = defaultdict(int)
    for card in cards:
        for key in card["data_classes"] or []:
            counts[key] += 1
    chosen = [card for card in cards if data_class in (card["data_classes"] or [])]
    holders: list[dict[str, Any]] = []
    if data_class is not None:
        found, _ = records.search(
            session, principal, APPLICATION,
            {"status": "active", "data_class": data_class}, sort="name", limit=MAX_FLOWS,
        )  # fmt: skip
        holders = [records.chip(APPLICATION, app) for app in found]
    return {
        "classes": [
            {"key": item["key"], "label": item["label"], "sensitivity": item.get("sensitivity"),
             "interfaces": counts.get(item["key"], 0)}
            for item in classes
        ],
        "data_class": data_class,
        "interfaces": chosen,
        "undeclared": sum(1 for card in chosen if data_class in card["undeclared"]),
        "holders": holders,
        "total": len(cards),
    }  # fmt: skip
