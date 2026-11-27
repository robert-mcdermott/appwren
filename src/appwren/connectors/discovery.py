"""Applications a source knows that are not on record (SIG-05).

An identity provider knows every application people sign in to. Those that match no record are
listed here, once each, for someone who adds applications to add (with the name filled in, and
the provider's identifier kept as an external reference so the next run matches it) or to
dismiss, with a reason. A connector never makes a record itself.

An entry the source no longer lists, and nobody decided about, goes. One that a person later
records by hand is matched by the next run and leaves the list.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import utc_now
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.models import Connector, Discovered
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from appwren.program import vocab

SYSTEM = "identity_app"  # the external system an identity provider's identifier is kept as


def note(
    session: Session, connector_id: int, unknown: Iterable[tuple[str, str]],
    matched: dict[str, str], at: datetime,
) -> int:  # fmt: skip
    """Keep what one run found: ``unknown`` as (identifier, name) pairs, and ``matched`` as
    identifier to the reference of the record it matched. Returns how many are new."""
    rows = {
        row.external_id: row
        for row in session.scalars(
            select(Discovered).where(Discovered.connector_id == connector_id)
        )
    }
    seen: set[str] = set()
    new = 0
    for external_id, name in unknown:
        seen.add(external_id)
        row = rows.get(external_id)
        if row is None:
            session.add(Discovered(connector_id=connector_id, external_id=external_id,
                                   name=name[:200], first_seen_at=at, last_seen_at=at,
                                   status="new"))  # fmt: skip
            new += 1
        else:
            row.name, row.last_seen_at = name[:200], at
    for external_id, row in rows.items():
        if row.status != "new" or external_id in seen:
            continue
        if external_id in matched:  # recorded by hand since: it is on record now
            row.status, row.record_ref, row.decided_at = "added", matched[external_id], at
        else:  # gone from the source, and nobody decided about it
            session.delete(row)
    session.flush()
    return new


def _keeper(principal: Principal) -> None:
    if not (principal.stewards or principal.architects or principal.manages_somewhere):
        raise PermissionDenied("Only someone who adds applications decides about these.")


def view(row: Discovered, connector: Connector | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "external_id": row.external_id,
        "name": row.name,
        "source": connector.name if connector else None,
        "source_key": connector.key if connector else None,
        "first_seen_at": row.first_seen_at,
        "last_seen_at": row.last_seen_at,
        "status": row.status,
        "decided_by": row.decided_by_name,
        "decided_at": row.decided_at,
        "reason": row.reason,
        "record_ref": row.record_ref,
    }


def listing(session: Session, principal: Principal, *, show: str = "new") -> dict[str, Any]:
    _keeper(principal)
    connectors = {row.id: row for row in session.scalars(select(Connector))}
    rows = session.scalars(select(Discovered).order_by(Discovered.name, Discovered.id)).all()
    counts = {status: sum(1 for row in rows if row.status == status)
              for status in ("new", "dismissed", "added")}  # fmt: skip
    wanted = [row for row in rows if show == "all" or row.status == show]
    return {
        "items": [view(row, connectors.get(row.connector_id)) for row in wanted],
        "counts": counts,
    }


def load(session: Session, item_id: int) -> Discovered:
    row = session.get(Discovered, item_id)
    if row is None:
        raise NotFound("There is no such application in the list.")
    return row


def dismiss(session: Session, principal: Principal, row: Discovered, reason: str) -> Discovered:
    """Not an application the portfolio keeps: a test registration, a tool's own sign-in."""
    _keeper(principal)
    if row.status != "new":
        raise Conflict("Someone has already decided about it.")
    reason = " ".join((reason or "").split())
    if not reason:
        raise Invalid("It was not dismissed.", {"reason": "Say why it is not kept on record."})
    row.status, row.reason = "dismissed", reason[:300]
    row.decided_by_name, row.decided_at = principal.name, utc_now()
    session.flush()
    return row


def restore(session: Session, principal: Principal, row: Discovered) -> Discovered:
    _keeper(principal)
    if row.status != "dismissed":
        raise Conflict("It is not dismissed.")
    row.status, row.reason, row.decided_by_name, row.decided_at = "new", None, None, None
    session.flush()
    return row


def add(session: Session, principal: Principal, row: Discovered, values: dict[str, Any]) -> Any:
    """An application record for it, named as the source names it unless the person gives
    another name, with the source's identifier kept so that the next run matches it."""
    _keeper(principal)
    if row.status != "new":
        raise Conflict("Someone has already decided about it.")
    if not values.get("org_unit_id"):
        raise Invalid("It was not added.", {"org_unit_id": "Choose the unit that answers for it."})
    given = {"name": row.name, **{k: v for k, v in values.items() if v not in (None, "")}}
    if SYSTEM in vocab.keys(session, "external_systems"):
        given["external_refs"] = [{"system": SYSTEM, "value": row.external_id}]
    record = records.create(session, principal, APPLICATION, given)
    row.status, row.record_ref = "added", record.ref
    row.decided_by_name, row.decided_at = principal.name, utc_now()
    session.flush()
    return record
