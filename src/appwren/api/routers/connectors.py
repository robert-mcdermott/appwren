"""Connectors an administrator switches on, and the values sources supply to records, with a
person's override (SIG-01, SIG-02)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from appwren import connectors
from appwren.access.policy import current
from appwren.api.common import database, envelope, reading, writing
from appwren.connectors import discovery, push, sourced
from appwren.core.clock import utc_now
from appwren.core.errors import Invalid, NotFound
from appwren.db.models import PushKey, TechnologyRelease
from appwren.inventory import records
from appwren.inventory.registry import find_any

router = APIRouter(prefix="/api/v1", tags=["connectors"])


class ConnectorBody(BaseModel):
    key: str | None = Field(default=None, max_length=40, description="A short key, for a new one")
    kind: str | None = Field(default=None, max_length=24, description="The kind, for a new one")
    name: str | None = Field(default=None, max_length=120)
    settings: dict[str, Any] | None = None
    credential_env: str | None = Field(
        default=None, max_length=80,
        description="The environment variable that holds the credential; never the credential",
    )  # fmt: skip
    every_hours: int | None = None
    enabled: bool | None = None


class OverrideBody(BaseModel):
    value: Any = None
    reason: str = Field(default="", max_length=500)
    release: str | None = Field(
        default=None, max_length=40, description="For a technology: the release the field is of"
    )


@router.get("/connectors", summary="The kinds of source, and the connectors set up")
def list_connectors(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(
            {"kinds": connectors.kinds_view(), "connectors": connectors.listing(session)}
        )


@router.post("/connectors", summary="Add a connector, switched off", status_code=201)
def add_connector(request: Request, body: ConnectorBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = connectors.add(session, principal, body.model_dump(exclude_none=True))
        return envelope(connectors.view(session, row))


@router.get("/connectors/{key}", summary="A connector, and its recent runs")
def get_connector(request: Request, key: str) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(connectors.view(session, connectors.load(session, key)))


@router.patch("/connectors/{key}", summary="Change a connector, or switch it on or off")
def change_connector(request: Request, key: str, body: ConnectorBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = connectors.change(
            session, principal, connectors.load(session, key), body.model_dump(exclude_none=True)
        )
        return envelope(connectors.view(session, row))


@router.post("/connectors/{key}/check", summary="Whether the source answers")
def check_connector(request: Request, key: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        said = connectors.check(session, principal, connectors.load(session, key))
        return envelope({"ok": True, "said": said})


@router.post("/connectors/{key}/run", summary="Run a connector now")
def run_connector(request: Request, key: str) -> dict[str, Any]:
    """Reads the source and writes what it read, or, if anything fails, writes nothing. The
    run is recorded either way."""
    current(request)
    with reading(request) as session:
        connectors.load(session, key)
    return envelope(connectors.run(request.app.state.db, key))


class KeyBody(BaseModel):
    name: str = Field(default="", max_length=120, description="The tool that will post with it")


class FactsBody(BaseModel):
    facts: list[Any] | None = Field(
        default=None,
        description="Each with record (a reference), field, value, and optionally observed_at "
        "(a date and time with its zone) and release (for a technology's release)",
    )


@router.get("/push-keys", summary="Push keys, issued and revoked")
def list_push_keys(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(push.listing(session, principal))


@router.post("/push-keys", summary="Issue a push key, shown this once", status_code=201)
def issue_push_key(request: Request, body: KeyBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, key = push.issue(session, principal, body.name)
        return envelope({**push.view(row), "key": key})


@router.delete("/push-keys/{key_id}", summary="Revoke a push key")
def revoke_push_key(request: Request, key_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(push.view(push.revoke(session, principal, key_id)))


@router.post("/facts", summary="Post facts, with a push key")
def post_facts(request: Request, body: FactsBody) -> dict[str, Any]:
    """For a script holding a push key, sent as ``Authorization: Bearer <key>``. Each fact is
    kept with the key's name as its source. The batch is checked whole first: one bad fact
    and nothing is written, with each problem named by its place in the list."""
    said = request.headers.get("authorization", "")
    presented = said[7:].strip() if said.lower().startswith("bearer ") else None
    db = database(request)
    with db.read() as session:
        holder = push.holder(session, presented)
        key_id, actor = (holder.id, push.actor(holder)) if holder else (None, None)
    if key_id is None or actor is None:
        raise HTTPException(401, "Post facts with a push key an administrator issued.")
    with db.write(actor, action="facts.push") as session:
        row = session.get(PushKey, key_id)
        assert row is not None
        counts = push.take(session, row, body.facts)
        row.last_used_at = utc_now()
    return envelope(counts)


class AddBody(BaseModel):
    org_unit_id: int | None = Field(default=None, description="The unit that answers for it")
    name: str | None = Field(
        default=None, max_length=200, description="Its name, if not the source's"
    )


class DismissBody(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.get("/discovered", summary="Applications a source knows that are not on record")
def list_discovered(request: Request, show: str = "new") -> dict[str, Any]:
    """Those listed and waiting (``show=new``, the default), ``dismissed``, ``added``, or
    ``all``."""
    principal = current(request)
    with reading(request) as session:
        return envelope(discovery.listing(session, principal, show=show))


@router.post("/discovered/{item_id}/add", summary="Add it as an application", status_code=201)
def add_discovered(request: Request, item_id: int, body: AddBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = discovery.load(session, item_id)
        record = discovery.add(session, principal, row,
                               {"org_unit_id": body.org_unit_id, "name": body.name})  # fmt: skip
        return envelope({"ref": record.ref, "name": record.name})


@router.post("/discovered/{item_id}/dismiss", summary="It is not kept on record, and why")
def dismiss_discovered(request: Request, item_id: int, body: DismissBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = discovery.dismiss(session, principal, discovery.load(session, item_id), body.reason)
        return envelope(discovery.view(row, None))


@router.post("/discovered/{item_id}/restore", summary="List a dismissed one again")
def restore_discovered(request: Request, item_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = discovery.restore(session, principal, discovery.load(session, item_id))
        return envelope(discovery.view(row, None))


def _target(
    session: Any, principal: Any, ref: str, field: str, release: str | None
) -> tuple[Any, sourced.Field]:
    """The record a sourced field belongs to: the record itself, or one of a technology's
    releases."""
    record_type, _ = find_any(session, ref)
    record = records.load(session, principal, record_type, ref)
    key = record_type.key
    if release is not None:
        if key != "technology":
            raise Invalid("Nothing was changed.", {"release": "Only a technology has releases."})
        record = session.scalars(
            select(TechnologyRelease).where(
                TechnologyRelease.technology_id == record.id, TechnologyRelease.cycle == release
            )
        ).first()
        if record is None:
            raise NotFound(f"{ref} has no release {release}.")
        key = "technology_release"
    spec = sourced.spec_for(key, field)
    if spec is None:
        raise Invalid("Nothing was changed.", {"field": "No source supplies that field."})
    return record, spec


@router.get("/sourced/{ref}", summary="What sources supply for a record")
def sourced_values(request: Request, ref: str) -> dict[str, Any]:
    """Each value with its source and when it was read, and any override with its reason.
    For a technology, its releases' values too."""
    principal = current(request)
    with reading(request) as session:
        record_type, _ = find_any(session, ref)
        record = records.load(session, principal, record_type, ref)
        found: dict[str, Any] = {
            "values": sourced.of_record(session, principal, record_type.key, record)
        }
        if record_type.key == "technology":
            found["releases"] = sourced.of_technology(session, principal, record)
        if record_type.key == "application":
            found["components"] = sourced.of_components(session, principal, record)
        return envelope(found)


@router.post("/sourced/{ref}/{field}/override", summary="Override a sourced value, with why")
def override_value(request: Request, ref: str, field: str, body: OverrideBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor, context={"reason": body.reason}) as session:
        record, spec = _target(session, principal, ref, field, body.release)
        row = sourced.override(session, principal, record, spec, body.value, body.reason)
        return envelope(sourced.view(row, spec))


@router.delete("/sourced/{ref}/{field}/override", summary="Use the source's value again")
def restore_value(
    request: Request, ref: str, field: str, release: str | None = None
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record, spec = _target(session, principal, ref, field, release)
        row = sourced.restore(session, principal, record, spec)
        return envelope(sourced.view(row, spec))
