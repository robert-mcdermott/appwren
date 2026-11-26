"""The inventory: applications, components, vendors, technologies, and capabilities.

The routes every record type shares (find, add, show, change, link, history) are made once
from the registry, so that each type's list documents exactly the filters it takes. What is
particular to a type has routes of its own below.
"""

from __future__ import annotations

import inspect
from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import clamp_limit, decode_cursor, encode_cursor, envelope, reading, writing
from appwren.core.errors import PermissionDenied
from appwren.inventory import access, applications, history, links, parts, records
from appwren.inventory.registry import (
    APPLICATION,
    CAPABILITY,
    COMPONENT,
    TECHNOLOGY,
    TYPES,
    VENDOR,
    RecordType,
    find_any,
)
from appwren.program import catalog, vocab

router = APIRouter(prefix="/api/v1", tags=["inventory"])


class ExternalRefBody(BaseModel):
    """What a record is called in another system."""

    system: str = Field(description="From the external_systems vocabulary")
    value: str = Field(max_length=200)


class RecordBody(BaseModel):
    """What every record has. On a change, send only what changes, with the ``version`` you
    were editing."""

    version: int | None = None
    name: str | None = Field(default=None, max_length=400)
    summary: str | None = None
    status: str | None = Field(default=None, description="active or retired")
    tags: list[str] | None = None
    external_refs: list[ExternalRefBody] | None = None


class ApplicationBody(RecordBody):
    """An application. Vocabulary fields take a key from ``/vocabularies``; ``vendor_id`` and
    ``successor_id`` take a reference such as ``VEN-0003``; dates are ``YYYY-MM-DD``.
    Sensitive fields are only shown to, and only taken from, those who may see them."""

    org_unit_id: int | None = Field(default=None, description="The unit that answers for it")
    restricted: bool | None = None
    lifecycle: str | None = None
    lifecycle_since: date | None = None
    sourcing: str | None = None
    purpose: str | None = None
    pace: str | None = None
    domain: str | None = None
    tier: str | None = Field(default=None, description="1 (mission critical) to 5 (minimal)")
    aliases: list[str] | None = None
    vendor_id: str | None = None
    product: str | None = None
    edition: str | None = None
    hosting: str | None = None
    home_url: str | None = None
    docs_url: str | None = None
    users: int | None = Field(default=None, ge=0)
    external_users: bool | None = None
    maintainers: int | None = Field(default=None, ge=0)
    support_unit_id: int | None = None
    sign_in: str | None = None
    data_classes: list[str] | None = None
    monitoring: str | None = None
    backup: str | None = None
    last_restore_test: date | None = None
    annual_cost: int | None = Field(default=None, ge=0)
    funding: str | None = None
    grant_ref: str | None = None
    grant_end: date | None = None
    research_continuity: bool | None = None
    regulated_record: bool | None = None
    records_retention: bool | None = None
    go_live: date | None = None
    retire_planned: date | None = None
    successor_id: str | None = None
    fields: dict[str, Any] | None = Field(
        default=None, description="The organization's own fields, by key"
    )
    accountable_id: int | None = Field(
        default=None, description="On adding: the accountable owner, if not yourself"
    )


class ComponentBody(RecordBody):
    application_id: str | None = Field(default=None, description="Its application's reference")
    kind: str | None = None
    repo_url: str | None = None
    hosting: str | None = None


class VendorBody(RecordBody):
    kind: str | None = None
    website: str | None = None


class TechnologyBody(RecordBody):
    kind: str | None = None
    radar: str | None = None
    vendor_id: str | None = None
    homepage: str | None = None
    eol_key: str | None = None


class CapabilityBody(RecordBody):
    parent_id: str | None = Field(default=None, description="The broader capability's reference")
    domain: str | None = None


BODIES: dict[str, type[RecordBody]] = {
    "application": ApplicationBody,
    "component": ComponentBody,
    "vendor": VendorBody,
    "technology": TechnologyBody,
    "capability": CapabilityBody,
}


class PeopleBody(BaseModel):
    owners: list[dict[str, Any]] = Field(
        description="Each with an account_id and a kind from application_roles; exactly one "
        "accountable"
    )


class CapabilityLink(BaseModel):
    capability: str = Field(description="A capability's reference")
    is_primary: bool = False
    note: str | None = Field(default=None, max_length=300)


class CapabilitiesBody(BaseModel):
    capabilities: list[CapabilityLink]


class UnitsBody(BaseModel):
    units: list[int] = Field(description="The ids of the units that use it")


class TechnologyUse(BaseModel):
    technology: str = Field(description="A technology's reference")
    release: str | None = Field(default=None, description="A release's cycle, such as 3.12")
    version: str | None = Field(default=None, max_length=80)


class TechnologiesBody(BaseModel):
    technologies: list[TechnologyUse]


class Release(BaseModel):
    cycle: str = Field(max_length=40)
    released_on: date | None = None
    support_ends: date | None = None
    extended_ends: date | None = None
    latest: str | None = Field(default=None, max_length=40)


class ReleasesBody(BaseModel):
    releases: list[Release]


class LinkBody(BaseModel):
    relation: str = Field(description="The key of a kind of link, such as depends_on")
    to: str = Field(description="The reference of the record it reaches, such as APP-0003")
    note: str | None = None


# --- The program, as the forms need it --------------------------------------------------------


@router.get("/vocabularies", summary="The lists of values records choose from")
def vocabularies(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(vocab.all_(session))


@router.get("/catalog", summary="What the program says about applications")
def show_catalog(request: Request) -> dict[str, Any]:
    """The organization's own fields, what each lifecycle stage requires, the sensitive
    fields, the definition of an application, and the fields of every record type."""
    with reading(request) as session:
        return envelope(
            {
                "fields": catalog.fields(session),
                "stage_requirements": catalog.stage_requirements(session),
                "sensitive_fields": catalog.sensitive_fields(session),
                "definition": catalog.definition(session),
                "types": {
                    key: {
                        "prefix": record_type.prefix,
                        "path": record_type.path,
                        "label": record_type.label,
                        "plural": record_type.plural,
                        "has_unit": record_type.has_unit,
                        "has_people": record_type.has_people,
                        "sorts": list(record_type.sorts),
                        "filters": list(record_type.filters),
                        "fields": [
                            {
                                "name": f.name,
                                "label": f.label,
                                "kind": f.kind,
                                "vocab": f.vocab,
                                "target": f.target,
                                "section": f.section,
                                "help": f.help,
                                "required": f.required,
                                "default": f.default,
                            }
                            for f in record_type.fields
                        ],
                    }
                    for key, record_type in TYPES.items()
                },
            }
        )


# --- What every record type's routes do ---------------------------------------------------


def values_of(body: BaseModel) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    values.pop("version", None)
    values.pop("accountable_id", None)
    return values


def paging(total: int, offset: int, size: int, shown: int) -> dict[str, Any]:
    """Where a page sits in its list, and the cursors of the pages either side."""
    following = offset + shown
    return {
        "total": total,
        "offset": offset,
        "next_cursor": encode_cursor({"offset": following}) if following < total else None,
        "prev_cursor": encode_cursor({"offset": max(0, offset - size)}) if offset > 0 else None,
    }


def list_records(
    request: Request, record_type: RecordType, filters: dict[str, Any], sort: str,
    limit: int | None, cursor: str | None,
) -> dict[str, Any]:  # fmt: skip
    principal = current(request)
    size = clamp_limit(limit)
    offset = int((decode_cursor(cursor) or {}).get("offset", 0))
    with reading(request) as session:
        rows, total = records.search(
            session, principal, record_type, filters, sort=sort, limit=size, offset=offset
        )
        data = records.cards(session, principal, record_type, rows)
    return envelope(data, **paging(total, offset, size, len(rows)))


def show_record(request: Request, record_type: RecordType, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, record_type, ref)
        data = records.detail(session, principal, record_type, record)
        data["links"] = links.of(session, principal, record_type, record)
        return envelope(data)


def _sensitive_given(session: Any, values: dict[str, Any]) -> list[str]:
    return [name for name in catalog.sensitive_fields(session) if name in values]


def create_record(request: Request, record_type: RecordType, body: RecordBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        accountable = getattr(body, "accountable_id", None)
        record = records.create(
            session, principal, record_type, values_of(body), accountable=accountable
        )
        return envelope(records.detail(session, principal, record_type, record))


def update_record(
    request: Request, record_type: RecordType, ref: str, body: RecordBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        values = values_of(body)
        if (
            record_type is APPLICATION
            and _sensitive_given(session, values)
            and not access.sees_sensitive(session, principal, record)
        ):
            raise PermissionDenied("You cannot change this application's sensitive fields.")
        records.update(session, principal, record_type, record, values, version=body.version)
        return envelope(records.detail(session, principal, record_type, record))


def add_record_link(
    request: Request, record_type: RecordType, ref: str, body: LinkBody
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        to_type, to_record = find_any(session, body.to)
        links.add(
            session, principal, record_type, record, body.relation, to_type, to_record,
            note=body.note,
        )  # fmt: skip
        return envelope(links.of(session, principal, record_type, record))


def remove_record_link(
    request: Request, record_type: RecordType, ref: str, link_id: int
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, record_type, ref)
        links.remove(session, principal, record_type, record, link_id)
        session.flush()
        return envelope(links.of(session, principal, record_type, record))


def record_history(request: Request, record_type: RecordType, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, record_type, ref)
        hidden: frozenset[str] = frozenset()
        if record_type is APPLICATION and not access.sees_sensitive(session, principal, record):
            hidden = frozenset(catalog.sensitive_fields(session))
        return envelope(history.for_record(session, record_type, record, withheld=hidden))


def _filter_parameter(name: str) -> inspect.Parameter:
    described = {
        "vendor_id": "A vendor's id",
        "application_id": "An application's id",
        "parent_id": "A broader capability's id",
        "sensitivity": "The highest sensitivity of its data: 0 public to 3 restricted",
    }
    annotation: Any = int | None if name.endswith("_id") or name == "sensitivity" else str | None
    return inspect.Parameter(
        name,
        inspect.Parameter.KEYWORD_ONLY,
        annotation=annotation,
        default=Query(default=None, description=described.get(name)),
    )


def _install(record_type: RecordType) -> None:
    """Make the routes every record type has."""
    path, label, body_type = f"/{record_type.path}", record_type.label, BODIES[record_type.key]
    article = "an" if label[0] in "aeiou" else "a"
    sorts = ", ".join(record_type.sorts)
    common = [
        ("q", str | None, Query(default=None, description="Words in the name or reference")),
        ("unit", int | None, Query(default=None, description="A unit, with those beneath it")),
        ("owner", int | None, Query(default=None, description="An account named on it")),
        ("mine", bool, Query(default=False, description="Only those I am named on")),
        ("sort", str, Query(default="-updated_at", description=f"One of {sorts}; - descends")),
        ("limit", int | None, Query(default=None, ge=1, le=200)),
        ("cursor", str | None, Query(default=None)),
    ]
    if not record_type.has_people:
        common = [item for item in common if item[0] not in ("owner", "mine")]
    if not record_type.has_unit and record_type is not COMPONENT:
        common = [item for item in common if item[0] != "unit"]
    parameters = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
        *[
            inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=kind, default=dflt)
            for name, kind, dflt in common
        ],
        *[_filter_parameter(name) for name in record_type.filters],
    ]

    def find(request: Request, **given: Any) -> dict[str, Any]:
        sort, limit, cursor = given.pop("sort"), given.pop("limit"), given.pop("cursor")
        return list_records(request, record_type, given, sort, limit, cursor)

    find.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]

    def add(request: Request, body: body_type) -> dict[str, Any]:  # type: ignore[valid-type]
        return create_record(request, record_type, body)

    def one(request: Request, ref: str) -> dict[str, Any]:
        return show_record(request, record_type, ref)

    def change(request: Request, ref: str, body: body_type) -> dict[str, Any]:  # type: ignore[valid-type]
        return update_record(request, record_type, ref, body)

    def link(request: Request, ref: str, body: LinkBody) -> dict[str, Any]:
        return add_record_link(request, record_type, ref, body)

    def unlink(request: Request, ref: str, link_id: int) -> dict[str, Any]:
        return remove_record_link(request, record_type, ref, link_id)

    def told(request: Request, ref: str) -> dict[str, Any]:
        return record_history(request, record_type, ref)

    for endpoint in (add, change):
        signature = inspect.signature(endpoint)
        endpoint.__signature__ = signature.replace(  # type: ignore[attr-defined]
            parameters=[
                param.replace(annotation=body_type) if param.name == "body"
                else param.replace(annotation={"request": Request, "ref": str}[param.name])
                for param in signature.parameters.values()
            ]
        )  # fmt: skip
    for endpoint in (one, link, unlink, told):
        signature = inspect.signature(endpoint)
        hints = {"request": Request, "ref": str, "body": LinkBody, "link_id": int}
        endpoint.__signature__ = signature.replace(  # type: ignore[attr-defined]
            parameters=[p.replace(annotation=hints[p.name]) for p in signature.parameters.values()]
        )
    key = record_type.key
    plural = record_type.plural
    routes = [
        ("", find, "GET", 200, "list", f"Find {plural}"),
        ("", add, "POST", 201, "add", f"Add {article} {label}"),
        ("/{ref}", one, "GET", 200, "show", f"One {label}, with what it is linked to"),
        ("/{ref}", change, "PATCH", 200, "change", f"Change {article} {label}"),
        ("/{ref}/links", link, "POST", 201, "link", f"Link {article} {label} to a record"),
        ("/{ref}/links/{link_id}", unlink, "DELETE", 200, "unlink", "Remove a link"),
        ("/{ref}/history", told, "GET", 200, "history", f"What has happened to {article} {label}"),
    ]
    for suffix, endpoint, method, status, verb, summary in routes:
        router.add_api_route(
            path + suffix, endpoint, methods=[method], status_code=status,
            name=f"{verb}_{key}", summary=summary,
        )  # fmt: skip


for _type in TYPES.values():
    _install(_type)


# --- Applications ---------------------------------------------------------------------------


@router.put("/applications/{ref}/people", summary="Name the people in each role")
def set_people(request: Request, ref: str, body: PeopleBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, APPLICATION, ref)
        records.set_owners(session, principal, APPLICATION, record, body.owners)
        return envelope(records.detail(session, principal, APPLICATION, record))


@router.put("/applications/{ref}/capabilities", summary="Say which capabilities it serves")
def set_capabilities(request: Request, ref: str, body: CapabilitiesBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, APPLICATION, ref)
        applications.set_capabilities(
            session, principal, record, [item.model_dump() for item in body.capabilities]
        )
        return envelope(records.detail(session, principal, APPLICATION, record))


@router.put("/applications/{ref}/units", summary="Say which units use it")
def set_units(request: Request, ref: str, body: UnitsBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, APPLICATION, ref)
        applications.set_units(session, principal, record, body.units)
        return envelope(records.detail(session, principal, APPLICATION, record))


# --- Components and technologies ------------------------------------------------------------


@router.put("/components/{ref}/technologies", summary="Say what a component is built on")
def set_technologies(request: Request, ref: str, body: TechnologiesBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, COMPONENT, ref)
        parts.set_technologies(
            session, principal, record, [item.model_dump() for item in body.technologies]
        )
        return envelope(records.detail(session, principal, COMPONENT, record))


@router.put("/technologies/{ref}/releases", summary="A technology's releases and their support")
def set_releases(request: Request, ref: str, body: ReleasesBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, TECHNOLOGY, ref)
        parts.set_releases(
            session, principal, record, [item.model_dump() for item in body.releases]
        )
        return envelope(records.detail(session, principal, TECHNOLOGY, record))


@router.get("/capability-map", summary="Every capability as a tree, with what serves it")
def capability_map(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(parts.tree(session, principal))


__all__ = ["CAPABILITY", "VENDOR", "router"]
