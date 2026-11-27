"""Intake: a request for something new, checked against what is already there (PLN-03).

Anyone may ask for something new: the need, the capability it serves, the unit that asks, and
when it is needed. The request shows every application that already serves that capability and
any whose name is close to its own, so a duplicate is seen before it is bought. Those who add
applications to the unit weigh options (build, buy, partner, or reuse what is on record) and
end it: approved, which adds an application in the proposed stage named for it; met by an
application already on record; or declined. Each end has a reason, and a request ends once.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, PermissionDenied
from appwren.db.models import (
    Account,
    Application,
    ApplicationCapability,
    Capability,
    Request,
    RequestOption,
    Vendor,
)
from appwren.inventory import access, applications, duplicates, records
from appwren.inventory.records import Errors
from appwren.inventory.registry import APPLICATION, CAPABILITY, REQUEST, VENDOR

APPROACHES = {"build": "Build it", "buy": "Buy it", "partner": "Partner for it",
              "reuse": "Reuse what is on record"}  # fmt: skip
OPEN = ("submitted", "evaluating")
STATES = {"submitted": "Submitted", "evaluating": "Being weighed", "approved": "Approved",
          "met": "Met by one on record", "declined": "Declined"}  # fmt: skip


def works(principal: Principal, record: Request) -> bool:
    """Whoever adds applications to its unit weighs and ends it."""
    return any(principal.covers(role, record.org_unit_id) for role in access.KEEPERS)


def _mine(principal: Principal, record: Request) -> bool:
    return principal.account_id is not None and principal.account_id in (
        record.requested_by_id, record.created_by,
    )  # fmt: skip


def _can_edit(session: Session, principal: Principal, record: Request) -> bool:
    return record.state in OPEN and (works(principal, record) or _mine(principal, record))


def _new(record: Request) -> None:
    record.state = "submitted"


def _created(session: Session, principal: Principal, record: Request) -> None:
    if record.requested_by_id is None:
        record.requested_by_id = principal.account_id


def _apply(
    session: Session, record: Request, values: Mapping[str, Any], errors: Errors, creating: bool
) -> None:
    if not creating and record.state not in OPEN:
        errors.add("state", "The request has ended, and changes no more.")


def _require(principal: Principal, record: Request) -> None:
    if not works(principal, record):
        raise PermissionDenied("Only a steward of the unit, an architect, or a manager does this.")
    if record.state not in OPEN:
        raise Conflict("The request has ended.")


def set_options(
    session: Session, principal: Principal, record: Request, wanted: list[Mapping[str, Any]]
) -> None:
    """The ways to meet it, in order. Replaces those it had."""
    _require(principal, record)
    errors = Errors()
    rows: list[RequestOption] = []
    for index, item in enumerate(wanted):
        where = f"options[{index}]"
        approach = str(item.get("approach") or "")
        if approach not in APPROACHES:
            errors.add(where, "Say whether it is to build, buy, partner, or reuse.")
            continue
        name = " ".join(str(item.get("name") or "").split())[:200]
        vendor_id = records.reference(session, "vendor", item.get("vendor"), where, errors)
        app_id = records.reference(session, "application", item.get("application"), where, errors,
                                   principal=principal)  # fmt: skip
        if approach == "reuse" and app_id is None:
            errors.add(where, "Name the application on record it would reuse.")
            continue
        if not name and app_id is not None:
            name = session.get(Application, app_id).name  # type: ignore[union-attr]
        if not name:
            errors.add(where, "Give the option a name.")
            continue
        fit = item.get("fit")
        if fit not in (None, "") and (not str(fit).isdigit() or not 1 <= int(fit) <= 5):
            errors.add(where, "Its fit is 1 to 5.")
            continue
        cost = item.get("annual_cost")
        if cost not in (None, "") and (not str(cost).isdigit()):
            errors.add(where, "Its cost a year is a whole number.")
            continue
        notes = str(item.get("notes") or "").strip()[:2000] or None
        rows.append(RequestOption(
            request_id=record.id, position=index + 1, approach=approach, name=name,
            vendor_id=vendor_id, application_id=app_id,
            annual_cost=int(cost) if cost not in (None, "") else None,
            fit=int(fit) if fit not in (None, "") else None, notes=notes,
        ))  # fmt: skip
    if errors:
        raise Invalid("The options were not saved.", errors)
    for row in session.scalars(select(RequestOption).where(RequestOption.request_id == record.id)):
        session.delete(row)
    session.flush()
    for row in rows:
        session.add(row)
    if record.state == "submitted":
        record.state = "evaluating"
    records.touch(session, record)
    session.flush()


def _reason(text: str | None) -> str:
    said = " ".join((text or "").split())
    if not said:
        raise Invalid("The request was not ended.", {"reason": "Say why."})
    return said[:2000]


def _end(
    record: Request, principal: Principal, state: str, reason: str, app_id: int | None
) -> None:
    record.state, record.outcome_reason, record.application_id = state, reason, app_id
    record.outcome_by_name, record.outcome_at = principal.name, utc_now()


def approve(
    session: Session, principal: Principal, record: Request, reason: str | None,
    name: str | None = None,
) -> Application:  # fmt: skip
    """Approved: an application in the proposed stage, named for the request, serving its
    capability, in its unit. Nothing is built or bought by this."""
    _require(principal, record)
    said = _reason(reason)
    capability = session.get(Capability, record.capability_id)
    app = records.create(session, principal, APPLICATION, {
        "name": (name or "").strip() or record.name, "org_unit_id": record.org_unit_id,
        "lifecycle": "proposed", "summary": record.summary,
        "users": record.users_expected,
    })  # fmt: skip
    if capability is not None:
        serves = [{"capability": capability.ref, "is_primary": False}]
        applications.set_capabilities(session, principal, app, serves)
    _end(record, principal, "approved", said, app.id)
    records.touch(session, record)
    session.flush()
    return app


def meet(
    session: Session, principal: Principal, record: Request, ref: str, reason: str | None
) -> Application:
    """Met by an application already on record."""
    _require(principal, record)
    said = _reason(reason)
    app = records.load(session, principal, APPLICATION, ref)
    _end(record, principal, "met", said, app.id)
    records.touch(session, record)
    session.flush()
    return app


def decline(session: Session, principal: Principal, record: Request, reason: str | None) -> None:
    _require(principal, record)
    _end(record, principal, "declined", _reason(reason), None)
    records.touch(session, record)
    session.flush()


def serving(session: Session, principal: Principal, record: Request) -> list[dict[str, Any]]:
    """Every application on record that serves the request's capability, primary first."""
    rows = session.execute(
        select(Application, ApplicationCapability.is_primary)
        .join(ApplicationCapability, ApplicationCapability.application_id == Application.id)
        .where(ApplicationCapability.capability_id == record.capability_id,
               Application.status == "active",
               Application.lifecycle.not_in(("retired", "archived")))
        .order_by(ApplicationCapability.is_primary.desc(), Application.name)
    )  # fmt: skip
    return [
        {**records.chip(APPLICATION, app), "is_primary": primary, "lifecycle": app.lifecycle,
         "users": app.users, "disposition": app.disposition}
        for app, primary in rows if access.sees_application(session, principal, app)
    ]  # fmt: skip


def _detail(
    session: Session, principal: Principal, record: Request, shown: Mapping[str, Any]
) -> dict[str, Any]:
    asker = session.get(Account, record.requested_by_id) if record.requested_by_id else None
    capability = session.get(Capability, record.capability_id)
    options = list(session.scalars(
        select(RequestOption).where(RequestOption.request_id == record.id)
        .order_by(RequestOption.position)
    ))  # fmt: skip
    vendors = {
        row.id: row for row in session.scalars(
            select(Vendor).where(Vendor.id.in_({o.vendor_id for o in options if o.vendor_id}))
        )
    } if options else {}  # fmt: skip
    apps = {
        row.id: row for row in session.scalars(
            select(Application).where(Application.id.in_(
                {o.application_id for o in options if o.application_id}
                | ({record.application_id} if record.application_id else set())
            ))
        )
    }  # fmt: skip

    def chip(app_id: int | None) -> dict[str, Any] | None:
        app = apps.get(app_id) if app_id else None
        if app is None or not access.sees_application(session, principal, app):
            return None
        return records.chip(APPLICATION, app)

    seen_serving = serving(session, principal, record)
    serving_ids = {item["ref"] for item in seen_serving}
    similar = [item for item in duplicates.similar(session, principal, name=record.name)
               if item.get("ref") not in serving_ids]  # fmt: skip
    return {
        "state": record.state,
        "state_label": STATES[record.state],
        "requested_by": {"id": asker.id, "name": asker.display_name} if asker else None,
        "capability": records.chip(CAPABILITY, capability) if capability else None,
        "serving": seen_serving,
        "similar": similar,
        "options": [
            {"approach": o.approach, "approach_label": APPROACHES[o.approach], "name": o.name,
             "vendor": records.chip(VENDOR, vendors[o.vendor_id]) if o.vendor_id in vendors
             else None, "application": chip(o.application_id), "annual_cost": o.annual_cost,
             "fit": o.fit, "notes": o.notes}
            for o in options
        ],
        "outcome": {"reason": record.outcome_reason, "by": record.outcome_by_name,
                    "at": record.outcome_at, "application": chip(record.application_id)}
        if record.state not in OPEN else None,
        "may_work": works(principal, record) and record.state in OPEN,
    }  # fmt: skip


def _cards(session: Session, principal: Principal, rows: list[Request]) -> list[dict[str, Any]]:
    capabilities = {
        row.id: row for row in session.scalars(
            select(Capability).where(Capability.id.in_({r.capability_id for r in rows}))
        )
    } if rows else {}  # fmt: skip
    return [
        {"state": row.state, "state_label": STATES[row.state], "needed_by": row.needed_by,
         "capability": records.chip(CAPABILITY, capabilities[row.capability_id])
         if row.capability_id in capabilities else None}
        for row in rows
    ]  # fmt: skip


REQUEST.extra.update(
    can_add=lambda session, principal, record: principal.account_id is not None,
    can_edit=_can_edit,
    can_see=lambda session, principal, record: True,
    visible_to=lambda session, principal: None,
    new=_new,
    created=_created,
    apply=_apply,
    detail=_detail,
    cards=_cards,
    add_refusal="Sign in to ask for something new.",
)
