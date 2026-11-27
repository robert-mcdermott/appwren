"""Connectors an administrator switches on, and the values sources supply to records, with a
person's override (SIG-01, SIG-02)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from appwren import connectors
from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.connectors import sourced
from appwren.core.errors import Invalid, NotFound
from appwren.db.models import TechnologyRelease
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
