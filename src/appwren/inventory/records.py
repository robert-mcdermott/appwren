"""Creating, changing, finding, and showing records.

Written once for every record type: what differs between them is data, in the registry, and
the hooks a type's own module adds to ``RecordType.extra``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any
from urllib.parse import quote

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import Account, ExternalRef, OrgUnit, RecordOwner
from appwren.db.models.inventory import ACCOUNTABLE, RECORD_STATUSES
from appwren.db.refs import claim_ref, next_ref, parse_ref
from appwren.events import audit
from appwren.inventory import access
from appwren.inventory.registry import TYPES, Field, RecordType
from appwren.people import units
from appwren.program import vocab

WITHHELD = "withheld"


class Errors(dict[str, str]):
    def add(self, field: str, message: str) -> None:
        self.setdefault(field, message)


def text(value: Any) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def url(value: Any, field: str, errors: Errors, *, max_length: int = 300) -> str | None:
    cleaned = text(value)
    if cleaned and not cleaned.lower().startswith(("https://", "http://")):
        errors.add(field, "Start the address with https://")
        return None
    if cleaned and len(cleaned) > max_length:
        errors.add(field, f"Keep the address to {max_length} characters.")
        return None
    return cleaned


def choice(
    session: Session, name: str, value: Any, field: str, errors: Errors, *, required: bool = False
) -> str | None:
    key = text(value)
    if key is None:
        if required:
            errors.add(field, "Choose a value.")
        return None
    if key not in vocab.keys(session, name):
        errors.add(field, f"{key!r} is not one of the choices.")
        return None
    return key


def many(
    session: Session, name: str | None, values: Any, field: str, errors: Errors
) -> list[str] | None:
    """A list of values: of a vocabulary, or free words (such as aliases) when there is none."""
    if values is None or values == "":
        return None
    if isinstance(values, str):
        values = list(values.split(","))
    if not isinstance(values, list | tuple):
        errors.add(field, "Give a list.")
        return None
    cleaned = list(dict.fromkeys(v for v in (str(item).strip() for item in values) if v))
    if name is not None:
        allowed = set(vocab.keys(session, name))
        unknown = [value for value in cleaned if value not in allowed]
        if unknown:
            errors.add(field, f"{unknown[0]!r} is not one of the choices.")
            return None
    elif len(cleaned) > 20 or any(len(value) > 120 for value in cleaned):
        errors.add(field, "Use at most 20 values of up to 120 characters each.")
        return None
    return cleaned or None


def whole(value: Any, field: str, errors: Errors, *, minimum: int | None = 0) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        errors.add(field, "Give a whole number.")
        return None
    try:
        number = int(str(value).replace(",", "").strip())
    except ValueError:
        errors.add(field, "Give a whole number.")
        return None
    if minimum is not None and number < minimum:
        errors.add(field, f"Give a number of at least {minimum}.")
        return None
    if number > 2_000_000_000:
        errors.add(field, "That number is too large.")
        return None
    return number


def day(value: Any, field: str, errors: Errors) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        errors.add(field, "Give a date as YYYY-MM-DD.")
        return None


def flag(value: Any, field: str, errors: Errors) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower()
    if word in ("yes", "true", "y", "1"):
        return True
    if word in ("no", "false", "n", "0"):
        return False
    errors.add(field, "Answer yes or no.")
    return None


def tags(values: Any, errors: Errors) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list | tuple):
        errors.add("tags", "Give a list of tags.")
        return []
    cleaned = list(dict.fromkeys(t for t in (str(v).strip().lower() for v in values) if t))
    if len(cleaned) > 20 or any(len(tag) > 40 for tag in cleaned):
        errors.add("tags", "Use at most 20 tags of up to 40 characters each.")
    return cleaned


def active_unit(session: Session, value: Any, field: str, errors: Errors) -> int | None:
    found = session.get(OrgUnit, int(value)) if str(value).isdigit() else None
    if found is None or found.status != "active":
        errors.add(field, "Choose a unit that is active.")
        return None
    return found.id


def reference(session: Session, target: str, value: Any, field: str, errors: Errors) -> int | None:
    """Another record, given by its reference (or its id). Stored as its id."""
    if value is None or value == "":
        return None
    record_type = TYPES[target]
    model: Any = record_type.model
    if isinstance(value, int) or str(value).isdigit():
        found = session.get(model, int(value))
    else:
        found = session.scalars(
            select(model).where(model.ref == str(value).strip().upper())
        ).first()
    if found is None:
        errors.add(field, f"There is no {record_type.label} {value}.")
        return None
    return found.id


def person(session: Session, value: Any, field: str, errors: Errors) -> int | None:
    """Someone with an account that is not disabled, by its id."""
    if value is None or value == "":
        return None
    found = session.get(Account, int(value)) if str(value).isdigit() else None
    if found is None or found.status == "disabled":
        errors.add(field, "Choose a person whose account is not disabled.")
        return None
    return found.id


def holds(column: Any, key: str) -> Any:
    """A condition that a stored list of vocabulary keys includes this one. Lists are kept as
    JSON text on both databases, and a key is only letters, digits, and underscores."""
    if not re.fullmatch(r"[a-z0-9_]{1,40}", key):
        raise Invalid("The list could not be narrowed.", {"filter": f"{key!r} is not a key."})
    return cast(column, String).like(f'%"{key}"%')


def apply_header(
    session: Session,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    errors: Errors,
    *,
    creating: bool,
) -> None:
    """The facts every record has: a name, a summary, tags, a status, and whether it is
    restricted; and, for a type that has one, the unit that answers for it."""
    if "name" in values or creating:
        name = text(values.get("name"))
        named = record_type.extra.get("default_name")
        if not name and creating and named is not None:
            name = named(session, values)  # a deployment is named for where and what it runs
        if not name:
            errors.add("name", "Give it a name.")
        elif len(name) > 200:
            errors.add("name", "Keep the name to 200 characters.")
        else:
            record.name = name
    if "summary" in values:
        record.summary = text(values["summary"])
    if "tags" in values:
        record.tags = tags(values["tags"], errors)
    if "restricted" in values and values["restricted"] is not None:
        record.restricted = bool(values["restricted"])
    if "status" in values and values["status"] is not None:
        if values["status"] not in RECORD_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            record.status = values["status"]
    if record_type.has_unit and ("org_unit_id" in values or creating):
        if values.get("org_unit_id") in (None, ""):
            errors.add("org_unit_id", "Say which unit answers for it.")
        else:
            unit_id = active_unit(session, values["org_unit_id"], "org_unit_id", errors)
            if unit_id is not None:
                record.org_unit_id = unit_id
    record.__dict__.pop("_external_refs", None)  # nothing left over from an earlier attempt
    if values.get("external_refs") is not None:
        # Checked here with everything else, and written once the record is.
        record._external_refs = external_refs(session, values["external_refs"], errors)


def value_of(session: Session, field: Field, given: Any, errors: Errors) -> Any:
    """A value for a field, checked and cleaned; errors are added under the field's name."""
    name = field.name
    if field.kind == "choice":
        assert field.vocab is not None
        return choice(session, field.vocab, given, name, errors, required=field.required)
    if field.kind == "many":
        return many(session, field.vocab, given, name, errors)
    if field.kind == "url":
        return url(given, name, errors, max_length=field.max_length)
    if field.kind == "int":
        return whole(given, name, errors, minimum=field.minimum)
    if field.kind == "date":
        return day(given, name, errors)
    if field.kind == "bool":
        return flag(given, name, errors)
    if field.kind == "ref":
        assert field.target is not None
        return reference(session, field.target, given, name, errors)
    if field.kind == "unit":
        return None if given in (None, "") else active_unit(session, given, name, errors)
    if field.kind == "person":
        return person(session, given, name, errors)
    cleaned = text(given)
    if cleaned and field.kind == "text" and len(cleaned) > field.max_length:
        errors.add(name, f"Keep this to {field.max_length} characters.")
        return None
    return cleaned


def apply_fields(
    session: Session,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    errors: Errors,
    *,
    creating: bool,
) -> None:
    """The facts particular to a record type, as its registry entry describes them."""
    for field in record_type.fields:
        if field.name not in values and not creating:
            continue
        given = values.get(field.name)
        if given in (None, "") and creating and field.default is not None:
            given = field.default
        before = len(errors)
        cleaned = value_of(session, field, given, errors)
        if len(errors) > before:
            continue
        if field.required and cleaned in (None, "", []):
            errors.add(field.name, "This is needed.")
            continue
        setattr(record, field.name, cleaned)


def _apply(
    session: Session,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    *,
    creating: bool,
) -> Errors:
    errors = Errors()
    apply_header(session, record_type, record, values, errors, creating=creating)
    apply_fields(session, record_type, record, values, errors, creating=creating)
    hook = record_type.extra.get("apply")
    if hook is not None:
        hook(session, record, values, errors, creating)
    return errors


def create(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    values: Mapping[str, Any],
    *,
    accountable: int | None = None,
) -> Any:
    """Add a record. On an application, whoever adds it is its accountable owner until they
    name someone else, unless another person is named as ``accountable``."""
    now = utc_now()
    record: Any = record_type.model(created_by=principal.account_id, created_at=now, updated_at=now)
    record.tags, record.restricted, record.version, record.status = [], False, 1, "active"
    starting = record_type.extra.get("new")
    if starting is not None:
        starting(record)
    errors = _apply(session, record_type, record, values, creating=True)
    if errors:
        raise Invalid(f"The {record_type.label} was not saved.", errors)
    may_add = record_type.extra.get("can_add")
    allowed = (
        may_add(session, principal, record)
        if may_add is not None
        else access.can_add(principal, record_type, record.org_unit_id)
    )
    if not allowed:
        raise PermissionDenied(
            record_type.extra.get("add_refusal") or f"You cannot add a {record_type.label} there."
        )
    # An import may bring the reference a record had where it came from.
    wanted = text(values.get("_ref"))
    if wanted is not None:
        model: Any = record_type.model
        parsed = parse_ref(wanted)
        if parsed is None or parsed[0] != record_type.prefix:
            raise Invalid(
                f"The {record_type.label} was not saved.",
                {"ref": f"{wanted} is not a reference for {record_type.plural}."},
            )
        if session.scalars(select(model.id).where(model.ref == wanted.upper())).first():
            raise Invalid(
                f"The {record_type.label} was not saved.",
                {"ref": f"{wanted.upper()} is already on record."},
            )
    with audit.operation(session, f"{record_type.key}.create"):
        record.ref = (
            claim_ref(session, record_type.prefix, wanted)
            if wanted is not None
            else next_ref(session, record_type.prefix)
        )
        session.add(record)
        session.flush()
        _save_external_refs(session, record_type, record)
        owner = accountable if accountable is not None else principal.account_id
        if record_type.has_people and owner is not None:
            session.add(
                RecordOwner(
                    record_type=record_type.key,
                    record_id=record.id,
                    account_id=owner,
                    kind=ACCOUNTABLE,
                )
            )
        created = record_type.extra.get("created")
        if created is not None:
            created(session, principal, record)
    return record


def require_version(record_type: RecordType, record: Any, version: int | None) -> None:
    """Refuse a change made against an older version, so nothing is silently overwritten."""
    if version != record.version:
        raise Conflict(
            f"This {record_type.label} was changed by someone else while you were editing. "
            "Reload it, then make your change again."
        )


def update(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    *,
    version: int | None,
) -> Any:
    """Change a record. ``version`` is the one the editor was looking at."""
    if not access.can_edit(session, principal, record_type, record):
        raise PermissionDenied(f"You cannot edit this {record_type.label}.")
    require_version(record_type, record, version)
    with audit.operation(session, f"{record_type.key}.edit"):
        with session.no_autoflush:
            errors = _apply(session, record_type, record, values, creating=False)
        if errors:
            session.expire(record)  # put back what was there
            raise Invalid(f"The {record_type.label} was not saved.", errors)
        if (
            record_type.has_unit
            and "org_unit_id" in values
            and not access.can_add(principal, record_type, record.org_unit_id)
        ):
            session.expire(record)
            raise PermissionDenied("You can move an application only to a unit you look after.")
        if getattr(record, "_external_refs", None) is not None:
            _save_external_refs(session, record_type, record)
            record.updated_at = utc_now()
        touch(session, record)
        changed = record_type.extra.get("changed")
        if changed is not None:
            changed(session, principal, record)
    return record


def touch(session: Session, record: Any) -> None:
    """Mark a record as changed, if it was."""
    if session.is_modified(record):
        record.version += 1
        record.updated_at = utc_now()


# --- What a record is called elsewhere ------------------------------------------------------


def external_refs(session: Session, given: Any, errors: Errors) -> list[tuple[str, str]]:
    """Check a list of ``{"system", "value"}`` and return it as pairs, without repeats."""
    systems = vocab.keys(session, "external_systems")
    found: list[tuple[str, str]] = []
    for item in given or []:
        system, value = text(item.get("system")), text(item.get("value"))
        if system not in systems:
            errors.add("external_refs", f"{system!r} is not one of the systems on record.")
        elif not value or len(value) > 200:
            errors.add("external_refs", "Give the identifier, in up to 200 characters.")
        elif (system, value) not in found:
            found.append((system, value))
    return found


def _save_external_refs(session: Session, record_type: RecordType, record: Any) -> None:
    wanted = record.__dict__.pop("_external_refs", None)
    if wanted is None:
        return
    have = {
        (row.system, row.value): row
        for row in session.scalars(
            select(ExternalRef).where(
                ExternalRef.record_type == record_type.key, ExternalRef.record_id == record.id
            )
        )
    }
    for key, row in have.items():
        if key not in wanted:
            session.delete(row)
    for system, value in wanted:
        if (system, value) not in have:
            session.add(
                ExternalRef(
                    record_type=record_type.key, record_id=record.id, system=system, value=value
                )
            )
    session.flush()


def external_refs_of(
    session: Session, record_type: RecordType, record_ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    """Each record's identifiers elsewhere, with a link where the system has a pattern."""
    ids = list(record_ids)
    systems = {item["key"]: item for item in vocab.get(session, "external_systems")}
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids:
        return found
    for row in session.scalars(
        select(ExternalRef)
        .where(ExternalRef.record_type == record_type.key, ExternalRef.record_id.in_(ids))
        .order_by(ExternalRef.id)
    ):
        system = systems.get(row.system, {})
        pattern = str(system.get("url") or "")
        link = (
            pattern.replace("{id}", quote(row.value, safe=""))
            if pattern.startswith(("https://", "http://")) and "{id}" in pattern
            else None
        )
        found[row.record_id].append(
            {"system": row.system, "label": system.get("label", row.system), "value": row.value,
             "url": link}
        )  # fmt: skip
    return found


# --- People in roles ----------------------------------------------------------------------


def owners_of(
    session: Session, record_type: RecordType, ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    """The people named on each record, the accountable owner first."""
    ids = list(ids)
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids or not record_type.has_people:
        return found
    order = {key: position for position, key in enumerate(vocab.keys(session, "application_roles"))}
    rows = session.execute(
        select(RecordOwner, Account)
        .join(Account, Account.id == RecordOwner.account_id)
        .where(RecordOwner.record_type == record_type.key, RecordOwner.record_id.in_(ids))
        .order_by(Account.display_name)
    )
    for owner, account in rows:
        found[owner.record_id].append(
            {
                "account_id": account.id,
                "name": account.display_name,
                "email": account.email,
                "kind": owner.kind,
                "active": account.status != "disabled",
            }
        )
    for people in found.values():
        people.sort(key=lambda person: order.get(person["kind"], 99))
    return found


def accountable(owners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [owner for owner in owners if owner["kind"] == ACCOUNTABLE]


def orphaned(owners: list[dict[str, Any]]) -> bool:
    """Nobody who can sign in answers for this record."""
    return not any(owner["active"] for owner in accountable(owners))


def set_owners(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    owners: list[Mapping[str, Any]],
) -> None:
    """Name the people in each role. There is always exactly one accountable owner; only the
    accountable owner, or someone with a role over the unit, may change who that is."""
    if not access.can_edit(session, principal, record_type, record):
        raise PermissionDenied(f"You cannot edit this {record_type.label}.")
    kinds = vocab.keys(session, "application_roles")
    wanted: set[tuple[int, str]] = set()
    for owner in owners:
        identifier = owner.get("account_id")
        account = session.get(Account, int(identifier)) if str(identifier).isdigit() else None
        kind = str(owner.get("kind", ""))
        if account is None or account.status == "disabled":
            raise Invalid(
                "The people were not saved.",
                {"owners": "Choose people whose accounts are not disabled."},
            )
        if kind not in kinds:
            raise Invalid("The people were not saved.", {"owners": f"{kind!r} is not a role."})
        wanted.add((account.id, kind))
    chosen = [account_id for account_id, kind in wanted if kind == ACCOUNTABLE]
    if len(chosen) != 1:
        raise Invalid(
            "The people were not saved.",
            {"owners": "Name exactly one accountable owner."},
        )
    existing = session.scalars(
        select(RecordOwner).where(
            RecordOwner.record_type == record_type.key, RecordOwner.record_id == record.id
        )
    ).all()
    have = {(row.account_id, row.kind): row for row in existing}
    current = [row.account_id for row in existing if row.kind == ACCOUNTABLE]
    if current != chosen and not (
        principal.account_id in current
        or any(principal.covers(role, record.org_unit_id) for role in access.TRUSTED)
    ):
        raise PermissionDenied(
            "Only the accountable owner, or someone with a role over its unit, can hand it on."
        )
    with audit.operation(session, f"{record_type.key}.people"):
        for key, row in have.items():
            if key not in wanted:
                session.delete(row)
        session.flush()  # the old accountable owner goes before the new one arrives
        for account_id, kind in sorted(wanted - set(have)):
            session.add(
                RecordOwner(
                    record_type=record_type.key,
                    record_id=record.id,
                    account_id=account_id,
                    kind=kind,
                )
            )
        session.flush()


# --- Finding ------------------------------------------------------------------------------


def conditions_for(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    filters: Mapping[str, Any],
) -> list[Any]:
    """What narrows a list: what the person may see, and what they asked for."""
    model: Any = record_type.model
    conditions: list[Any] = []
    seen = access.visible(session, principal, record_type)
    if seen is not None:
        conditions.append(seen)
    query = text(filters.get("q"))
    if query:
        like = f"%{query.lower()}%"
        elsewhere = exists(
            select(ExternalRef.id).where(
                ExternalRef.record_type == record_type.key,
                ExternalRef.record_id == model.id,
                func.lower(ExternalRef.value).like(like),
            )
        )
        conditions.append(
            or_(
                func.lower(model.name).like(like),
                func.lower(model.ref).like(like),
                func.lower(func.coalesce(model.summary, "")).like(like),
                elsewhere,  # what it is called in another system
            )
        )
    if filters.get("unit"):
        conditions.append(
            model.org_unit_id.in_(units.with_descendants(session, [int(filters["unit"])]))
        )
    sensitive = set(access.sensitive_fields(session)) | {"sensitivity"}
    for name in record_type.filters:
        value = filters.get(name)
        if value in (None, ""):
            continue
        if (
            record_type.has_people
            and name in sensitive
            and not access.sees_all_sensitive(principal)
        ):
            raise PermissionDenied(f"You cannot narrow the list by {name}.")
        conditions.append(getattr(model, name) == value)
    more = record_type.extra.get("conditions")
    if more is not None:
        conditions += more(session, principal, filters)
    owner = filters.get("owner")
    if filters.get("mine"):
        owner = principal.account_id
    if owner and record_type.has_people:
        owned = select(RecordOwner.record_id).where(
            RecordOwner.record_type == record_type.key, RecordOwner.account_id == int(owner)
        )
        conditions.append(model.id.in_(owned))
    return conditions


def ordering(
    session: Session, principal: Principal, record_type: RecordType, sort: str
) -> list[Any]:
    model: Any = record_type.model
    descending = sort.startswith("-")
    name = sort.lstrip("-")
    if name not in record_type.sorts:
        raise Invalid(
            "The list could not be sorted.",
            {"sort": f"Sort by one of: {', '.join(record_type.sorts)}."},
        )
    if (
        record_type.has_people
        and name in access.sensitive_fields(session)
        and not access.sees_all_sensitive(principal)
    ):
        raise PermissionDenied(f"You cannot sort the list by {name}.")
    column = getattr(model, name)
    special = record_type.extra.get("sort_columns", {}).get(name)
    if special is not None:
        column = special(session, model)
    elif name in ("lifecycle",):
        # An ordered vocabulary sorts by its order, not by its spelling.
        from sqlalchemy import case

        ranks = {key: rank for rank, key in enumerate(vocab.keys(session, "lifecycle"))}
        column = case(ranks, value=model.lifecycle, else_=-1)
    return [
        column.desc().nulls_last() if descending else column.asc().nulls_last(),
        model.id.desc(),
    ]


def search(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    filters: Mapping[str, Any],
    *,
    sort: str = "-updated_at",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Any], int]:
    """Records the person may see that match the filters, and how many there are in all."""
    model: Any = record_type.model
    conditions = conditions_for(session, principal, record_type, filters)
    order = ordering(session, principal, record_type, sort)
    total = session.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()
    rows = list(
        session.scalars(
            select(model).where(*conditions).order_by(*order).limit(limit).offset(offset)
        )
    )
    return rows, total


# --- Showing ------------------------------------------------------------------------------


def chip(record_type: RecordType, record: Any) -> dict[str, Any]:
    """A record as it appears wherever another record refers to it."""
    return {
        "type": record_type.key,
        "ref": record.ref,
        "name": record.name,
        "status": record.status,
    }


def _plain(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value


def card(
    record_type: RecordType,
    record: Any,
    owners: list[dict[str, Any]],
    *,
    withheld: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """A record as a row of a list, with any sensitive field the reader may not see left out."""
    out: dict[str, Any] = {
        "type": record_type.key,
        "ref": record.ref,
        "name": record.name,
        "summary": record.summary,
        "status": record.status,
        "org_unit_id": record.org_unit_id,
        "restricted": record.restricted,
        "updated_at": record.updated_at,
    }
    if record_type.has_people:
        out.update(owners=accountable(owners), orphaned=orphaned(owners))
    for field in record_type.fields:
        out[field.name] = (
            WITHHELD if field.name in withheld else _plain(getattr(record, field.name))
        )
    if withheld:
        out["withheld"] = sorted(withheld)
    return out


def withheld_from(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    owners: list[dict[str, Any]],
    sensitive: list[str],
) -> frozenset[str]:
    """The sensitive fields this reader may not see on this record."""
    if not record_type.has_people or not sensitive:
        return frozenset()
    is_named = principal.account_id is not None and any(
        owner["account_id"] == principal.account_id for owner in owners
    )
    if access.sees_sensitive(session, principal, record, is_named=is_named):
        return frozenset()
    return frozenset(name for name in sensitive if record_type.field(name) is not None)


def cards(
    session: Session, principal: Principal, record_type: RecordType, rows: list[Any]
) -> list[dict[str, Any]]:
    owners = owners_of(session, record_type, [row.id for row in rows])
    sensitive = access.sensitive_fields(session)
    out = []
    for row in rows:
        people = owners.get(row.id, [])
        hidden = withheld_from(session, principal, record_type, row, people, sensitive)
        out.append(card(record_type, row, people, withheld=hidden))
    more = record_type.extra.get("cards")
    if more is not None:
        for item, extra in zip(out, more(session, principal, rows), strict=True):
            item.update({k: v for k, v in extra.items() if k not in item.get("withheld", ())})
    return out


def detail(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> dict[str, Any]:
    """One record in full. Raises NotFound if the person may not see it: a record they may
    not see does not exist, as far as they can tell."""
    if not access.can_see(session, principal, record_type, record):
        raise NotFound(f"There is no {record_type.label} {record.ref}.")
    out = cards(session, principal, record_type, [record])[0]
    if record_type.has_people:
        out["owners"] = owners_of(session, record_type, [record.id]).get(record.id, [])
    editable = access.can_edit(session, principal, record_type, record)
    out.update(
        tags=record.tags,
        version=record.version,
        created_at=record.created_at,
        external_refs=external_refs_of(session, record_type, [record.id]).get(record.id, []),
        can={"edit": editable},
    )
    more = record_type.extra.get("detail")
    if more is not None:
        out.update(more(session, principal, record, out))
    return out


def load(session: Session, principal: Principal, record_type: RecordType, ref: str) -> Any:
    """Find a record the person may see, or raise NotFound."""
    from appwren.inventory.registry import find

    record = find(session, record_type, ref)
    if not access.can_see(session, principal, record_type, record):
        raise NotFound(f"There is no {record_type.label} {ref}.")
    return record
