"""Sourced values: a field of a record as a source last read it, and a person's override of it
(SIG-02).

The record's own field holds whichever wins, so every list, filter, export, and the engine go
on reading one place. A source's reading is written there unless a person has overridden it;
an override is written there by the person, under their name and with their reason, and the
source's later readings wait beside it until the override is removed. Someone who changes a
sourced field by hand on the record has overridden it too: the next reading sees the change
and keeps it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.among import among
from appwren.db.models import FactValue
from appwren.inventory import access, records
from appwren.inventory.registry import TYPES


@dataclass(frozen=True)
class Field:
    """A fact a source may supply: which record and field, what kind of value, its words."""

    record_type: str
    name: str
    label: str
    kind: str  # count, date, words (a list of short words), counts (a map to counts), yes, text
    column: bool  # the record has a field of its own for it


FIELDS: dict[tuple[str, str], Field] = {}


def field(record_type: str, name: str, label: str, kind: str, *, column: bool = False) -> Field:
    spec = Field(record_type, name, label, kind, column)
    FIELDS[(record_type, name)] = spec
    return spec


def _order(record_type: str, name: str) -> int:
    """Where a field comes among those a source supplies: in the order its kind gives them."""
    keys = list(FIELDS)
    return keys.index((record_type, name)) if (record_type, name) in FIELDS else len(keys)


def spec_for(record_type: str, name: str) -> Field | None:
    """The field a source may supply, once every kind, and the push sources, have said which
    they supply."""
    import appwren.connectors.kinds
    import appwren.connectors.push  # noqa: F401

    return FIELDS.get((record_type, name))


def clean(spec: Field, value: Any) -> Any:
    """A value from outside, checked against the field it fills. What a source sends is
    untrusted: anything that does not fit is refused, never stored."""
    if value is None:
        return None
    if spec.kind == "count":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10**9:
            raise ValueError(f"{spec.label} is a whole number of 0 or more")
        return value
    if spec.kind == "date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return date.fromisoformat(str(value)[:10]).isoformat()
    if spec.kind == "words":
        if not isinstance(value, list | tuple) or len(value) > 50:
            raise ValueError(f"{spec.label} is a list of up to 50 words")
        return [str(item)[:60] for item in value]
    if spec.kind == "counts":
        if not isinstance(value, dict) or len(value) > 20:
            raise ValueError(f"{spec.label} is a short map of names to counts")
        out = {}
        for key, count in value.items():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"{spec.label}: each count is a whole number of 0 or more")
            out[str(key)[:40]] = count
        return out
    if spec.kind == "yes":
        if not isinstance(value, bool):
            raise ValueError(f"{spec.label} is true or false")
        return value
    return str(value)[:300]


def _column_value(spec: Field, value: Any) -> Any:
    if spec.kind == "date" and isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _same(spec: Field, one: Any, other: Any) -> bool:
    if spec.kind == "date":
        return str(one)[:10] == str(other)[:10] if one and other else one == other
    return one == other


def _row(session: Session, spec: Field, record_id: int) -> FactValue | None:
    return session.scalars(
        select(FactValue).where(
            FactValue.record_type == spec.record_type,
            FactValue.record_id == record_id,
            FactValue.field == spec.name,
        )
    ).first()


def write(
    session: Session, *, source: str, source_name: str, record: Any, spec: Field, value: Any,
    read_at: datetime | None = None,
) -> str:  # fmt: skip
    """Keep what a source read. Returns ``changed`` when the record's field moved,
    ``unchanged``, or ``kept`` when a person's override holds it."""
    value = clean(spec, value)
    read_at = read_at or utc_now()
    row = _row(session, spec, record.id)
    before = row.value if row is not None else None
    if row is None:
        row = FactValue(record_type=spec.record_type, record_id=record.id, field=spec.name,
                        source=source, source_name=source_name, read_at=read_at,
                        overridden=False, value=None)  # fmt: skip
        session.add(row)
    elif spec.column and not row.overridden and row.value is not None:
        # Changed by hand on the record since the source last wrote it: that is an override.
        current = getattr(record, spec.name)
        if not _same(spec, current, row.value):
            row.overridden, row.override_value = True, _plain(current)
            row.override_reason, row.override_by_name = "Changed by hand on the record", None
            row.override_at = utc_now()
    row.value, row.source, row.source_name, row.read_at = value, source, source_name, read_at
    session.flush()
    if row.overridden:
        return "kept"
    if not spec.column:
        return "unchanged" if _same(spec, before, value) else "changed"
    current = getattr(record, spec.name)
    if _same(spec, current, value):
        return "unchanged"
    setattr(record, spec.name, _column_value(spec, value))
    records.touch(session, record)
    session.flush()
    return "changed"


def _plain(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value


def _editable(session: Session, principal: Principal, spec: Field, record: Any) -> bool:
    """Whoever may edit the record: for a technology's release, whoever keeps technologies."""
    if spec.record_type == "technology_release":
        from appwren.db.models import Technology

        technology = session.get(Technology, record.technology_id)
        return access.can_edit(session, principal, TYPES["technology"], technology)
    return access.can_edit(session, principal, TYPES[spec.record_type], record)


def override(
    session: Session, principal: Principal, record: Any, spec: Field, value: Any, reason: str
) -> FactValue:
    """A person's value for a sourced field, with why. It wins until they remove it."""
    if not _editable(session, principal, spec, record):
        raise PermissionDenied("Only someone who keeps this record overrides its values.")
    reason = (reason or "").strip()
    if not reason:
        raise Invalid("The value was not overridden.", {"reason": "Say why the source is wrong."})
    try:
        value = clean(spec, value)
    except ValueError as exc:
        raise Invalid("The value was not overridden.", {"value": str(exc)}) from exc
    row = _row(session, spec, record.id)
    if row is None:
        raise Invalid("The value was not overridden.", {"field": "No source supplies it."})
    row.overridden, row.override_value, row.override_reason = True, value, reason[:500]
    row.override_by_name, row.override_at = principal.name, utc_now()
    if spec.column:
        setattr(record, spec.name, _column_value(spec, value))
        records.touch(session, record)
    session.flush()
    return row


def restore(session: Session, principal: Principal, record: Any, spec: Field) -> FactValue:
    """Remove an override: the source's latest reading holds the field again."""
    if not _editable(session, principal, spec, record):
        raise PermissionDenied("Only someone who keeps this record changes its values.")
    row = _row(session, spec, record.id)
    if row is None or not row.overridden:
        raise Invalid("Nothing was changed.", {"field": "The value is not overridden."})
    row.overridden, row.override_value = False, None
    row.override_reason, row.override_by_name, row.override_at = None, None, None
    if spec.column:
        setattr(record, spec.name, _column_value(spec, row.value))
        records.touch(session, record)
    session.flush()
    return row


def view(row: FactValue, spec: Field) -> dict[str, Any]:
    return {
        "field": row.field,
        "label": spec.label,
        "kind": spec.kind,
        "value": row.value,
        "source": row.source,
        "source_name": row.source_name,
        "read_at": row.read_at,
        "overridden": row.overridden,
        "override_value": row.override_value,
        "override_reason": row.override_reason,
        "override_by": row.override_by_name,
        "override_at": row.override_at,
        "shown": row.override_value if row.overridden else row.value,
    }


def of_record(
    session: Session, principal: Principal, record_type: str, record: Any
) -> list[dict[str, Any]]:
    """What sources supply for a record the person may see, sensitive fields withheld."""
    hidden: set[str] = set()
    if record_type == "application" and not access.sees_sensitive(session, principal, record):
        from appwren.program import catalog

        hidden = set(catalog.sensitive_fields(session))
    rows = session.scalars(
        select(FactValue)
        .where(FactValue.record_type == record_type, FactValue.record_id == record.id)
        .order_by(FactValue.field)
    )
    out = []
    for row in rows:
        spec = spec_for(record_type, row.field)
        if spec is None or row.field in hidden:
            continue
        out.append(view(row, spec))
    return sorted(out, key=lambda item: _order(record_type, item["field"]))


def of_components(session: Session, principal: Principal, record: Any) -> list[dict[str, Any]]:
    """An application's components, each with what sources supply for it."""
    from appwren.db.models import Component

    components = session.scalars(
        select(Component).where(Component.application_id == record.id).order_by(Component.name)
    ).all()
    found = {component.id: component.ref for component in components}
    out: dict[str, list[dict[str, Any]]] = {}
    if not found:
        return []
    for row in session.scalars(
        select(FactValue)
        .where(FactValue.record_type == "component", among(FactValue.record_id, found))
        .order_by(FactValue.field)
    ):
        spec = spec_for("component", row.field)
        if spec is not None:
            out.setdefault(found[row.record_id], []).append(view(row, spec))
    return [
        {"ref": ref,
         "values": sorted(values, key=lambda item: _order("component", item["field"]))}
        for ref, values in out.items()
    ]  # fmt: skip


def forget(session: Session, record_type: str, record_id: int) -> None:
    """A record is going: what sources supplied for it goes with it."""
    for row in session.scalars(
        select(FactValue).where(
            FactValue.record_type == record_type, FactValue.record_id == record_id
        )
    ):
        session.delete(row)


def of_technology(session: Session, principal: Principal, record: Any) -> list[dict[str, Any]]:
    """A technology's releases, each with what sources supply for it."""
    from appwren.db.models import TechnologyRelease

    releases = session.scalars(
        select(TechnologyRelease).where(TechnologyRelease.technology_id == record.id)
    ).all()
    found = {release.id: release.cycle for release in releases}
    out: dict[str, list[dict[str, Any]]] = {}
    if not found:
        return []
    for row in session.scalars(
        select(FactValue)
        .where(FactValue.record_type == "technology_release", among(FactValue.record_id, found))
        .order_by(FactValue.field)
    ):
        spec = spec_for("technology_release", row.field)
        if spec is not None:
            out.setdefault(found[row.record_id], []).append(view(row, spec))
    return [
        {"cycle": cycle,
         "values": sorted(values, key=lambda item: _order("technology_release", item["field"]))}
        for cycle, values in sorted(out.items())
    ]  # fmt: skip


def values(
    session: Session, record_type: str, ids: Iterable[int], names: Iterable[str]
) -> dict[int, dict[str, Any]]:
    """For the engine and the pages: each record's sourced values that hold (an override's
    where there is one), by field."""
    wanted, keys = list(ids), list(names)
    found: dict[int, dict[str, Any]] = {}
    if not wanted or not keys:
        return found
    for row in session.scalars(
        select(FactValue).where(
            FactValue.record_type == record_type,
            among(FactValue.record_id, wanted),
            FactValue.field.in_(keys),
        )
    ):
        found.setdefault(row.record_id, {})[row.field] = (
            row.override_value if row.overridden else row.value
        )
    return found
