"""Who may see and change a record, and who may see its sensitive fields (spec/security.md).

One rule for each question, used everywhere: single records, lists, counts, charts, links,
and exports all ask here, so they always agree.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from appwren.access import roles
from appwren.access.principal import Principal
from appwren.db.models import Application, RecordOwner
from appwren.inventory.registry import APPLICATION, COMPONENT, SHARED, RecordType
from appwren.program import catalog

# Roles that see a unit's restricted applications and their sensitive fields, and roles that
# may add and edit its applications.
TRUSTED = (roles.STEWARD, roles.LEADER, roles.MANAGER, roles.ARCHITECT)
KEEPERS = (roles.STEWARD, roles.MANAGER, roles.ARCHITECT)


def _in(units: frozenset[int] | None, org_unit_id: int | None) -> bool:
    return units is None or (org_unit_id is not None and org_unit_id in units)


def roles_on(
    session: Session, record_type: RecordType, record_id: int, account_id: int | None
) -> set[str]:
    """The roles a person holds on a record: accountable owner, technical owner, and so on."""
    if account_id is None:
        return set()
    return set(
        session.scalars(
            select(RecordOwner.kind).where(
                RecordOwner.record_type == record_type.key,
                RecordOwner.record_id == record_id,
                RecordOwner.account_id == account_id,
            )
        )
    )


def _application_of(session: Session, record_type: RecordType, record: Any) -> Any:
    """The application a record belongs to: itself, or a component's application."""
    if record_type is APPLICATION:
        return record
    if record_type is COMPONENT:
        return session.get(Application, record.application_id)
    return None


def named(session: Session, principal: Principal, application: Any) -> bool:
    return bool(roles_on(session, APPLICATION, application.id, principal.account_id))


def can_see(session: Session, principal: Principal, record_type: RecordType, record: Any) -> bool:
    """Whether the person may know this record exists. The catalog is open; a restricted
    application, and its components, are known only to those with a part in it."""
    application = _application_of(session, record_type, record)
    if application is None or not application.restricted:
        return True
    if principal.reads_all or _in(principal.units_for(*TRUSTED), application.org_unit_id):
        return True
    if application.created_by is not None and application.created_by == principal.account_id:
        return True
    return named(session, principal, application)


def visible(
    session: Session, principal: Principal, record_type: RecordType
) -> ColumnElement[bool] | None:
    """A condition that keeps only the records the person may see, or None for all of them."""
    if record_type in SHARED or principal.reads_all:
        return None
    trusted = principal.units_for(*TRUSTED)
    if trusted is None:
        return None
    me = principal.account_id
    owned = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == APPLICATION.key,
            RecordOwner.record_id == Application.id,
            RecordOwner.account_id == me,
        )
    )
    conditions: list[ColumnElement[bool]] = [
        Application.restricted.is_(False),
        owned,
        Application.created_by == me,
    ]
    if trusted:
        conditions.append(Application.org_unit_id.in_(trusted))
    seen = or_(*conditions)
    if record_type is APPLICATION:
        return seen
    model: Any = record_type.model
    return model.application_id.in_(select(Application.id).where(seen))


def can_add(principal: Principal, record_type: RecordType, org_unit_id: int | None) -> bool:
    """Applications are added by a unit's steward, an architect, or a manager; shared records
    by architects and managers."""
    if record_type in SHARED:
        return keeps_shared(principal)
    return any(principal.covers(role, org_unit_id) for role in KEEPERS)


def keeps_shared(principal: Principal) -> bool:
    return principal.architects or principal.manages_somewhere


def can_edit(session: Session, principal: Principal, record_type: RecordType, record: Any) -> bool:
    if record_type in SHARED:
        return keeps_shared(principal)
    application = _application_of(session, record_type, record)
    if any(principal.covers(role, application.org_unit_id) for role in KEEPERS):
        return True
    return named(session, principal, application)


def can_assess(session: Session, principal: Principal, application: Any) -> bool:
    """The people who keep an application answer its assessment."""
    return can_edit(session, principal, APPLICATION, application)


def can_decide(session: Session, principal: Principal, application: Any) -> bool:
    """A manager, or a leader of its unit, but never its own accountable owner."""
    if not (
        principal.manages_unit(application.org_unit_id)
        or principal.leads_unit(application.org_unit_id)
    ):
        return False
    return "accountable" not in roles_on(session, APPLICATION, application.id, principal.account_id)


def sees_sensitive(
    session: Session,
    principal: Principal,
    application: Any,
    *,
    is_named: bool | None = None,
) -> bool:
    """Whether the person may see this application's sensitive fields: the people named on
    it, those with a role over its unit, and those who read everything."""
    if principal.reads_all or _in(principal.units_for(*TRUSTED), application.org_unit_id):
        return True
    if is_named is None:
        is_named = named(session, principal, application)
    return is_named


def sees_all_sensitive(principal: Principal) -> bool:
    """Whether the person sees every application's sensitive fields, and so may filter and
    sort a list by them."""
    return principal.reads_all or principal.units_for(*TRUSTED) is None


def sensitive_fields(session: Session) -> list[str]:
    return catalog.sensitive_fields(session)
