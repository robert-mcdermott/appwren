"""The landscape: where data travels between applications (and, later in the wave, what
depends on what, where things run, and what they cost)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, CONTRACT, find_any
from appwren.landscape import costs, graph, handling, interfaces, lifecycle, overlap

router = APIRouter(prefix="/api/v1", tags=["landscape"])


@router.get("/data-flows", summary="Where a class of data travels")
def data_flows(
    request: Request,
    data_class: str | None = Query(default=None, description="A class of data, by its key"),
) -> dict[str, Any]:
    """How many interfaces carry each class of data; and, for the class chosen, every
    interface that carries it and every application that holds it. ``undeclared`` on an
    interface lists the classes it carries that the receiving application does not record."""
    principal = current(request)
    with reading(request) as session:
        return envelope(interfaces.flows(session, principal, data_class))


@router.get("/graph/{ref}", summary="A record and what it is connected to, in groups")
def graph_around(request: Request, ref: str) -> dict[str, Any]:
    """The neighbors of any record, grouped by what joins them: dependencies, interfaces,
    capabilities, components, technologies, and vendors. ``hidden`` counts those the reader
    may not see."""
    principal = current(request)
    with reading(request) as session:
        record_type, found = find_any(session, ref)
        record = records.load(session, principal, record_type, found.ref)
        return envelope(graph.around(session, principal, record_type, record))


@router.get("/applications/{ref}/impact", summary="What breaks if an application goes")
def application_impact(request: Request, ref: str) -> dict[str, Any]:
    """What depends on it, directly and beyond; the interfaces that would stop; the
    capabilities left with no provider, or without their primary; and the people affected."""
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, APPLICATION, ref)
        return envelope(graph.impact(session, principal, record))


# --- Cost and contracts ---------------------------------------------------------------------


class CostLineBody(BaseModel):
    category: str = Field(description="From the cost_categories vocabulary")
    amount: int = Field(ge=0, description="A year")
    funding_source: str | None = Field(default=None, description="A funding source's reference")
    contract: str | None = Field(default=None, description="A contract's reference")
    note: str | None = Field(default=None, max_length=300)


class CostLinesBody(BaseModel):
    lines: list[CostLineBody]


class CoveredBody(BaseModel):
    application: str = Field(description="An application's reference")
    licenses_used: int | None = Field(default=None, ge=0)


class CoveredListBody(BaseModel):
    applications: list[CoveredBody]


@router.get("/applications/{ref}/costs", summary="What an application costs, line by line")
def application_costs(request: Request, ref: str) -> dict[str, Any]:
    """Its cost lines, what they add up to by category, cost per user, and the contracts that
    cover it. ``withheld`` is true, and nothing else is given, for a reader who may not see
    its cost."""
    principal = current(request)
    with reading(request) as session:
        record = records.load(session, principal, APPLICATION, ref)
        return envelope(costs.costs(session, principal, record))


@router.put("/applications/{ref}/cost-lines", summary="Set an application's cost lines")
def set_cost_lines(request: Request, ref: str, body: CostLinesBody) -> dict[str, Any]:
    """Replaces the lines. Once an application has any, its annual cost is their sum. A line
    that names a contract makes the contract cover the application."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, APPLICATION, ref)
        costs.set_lines(session, principal, record, [line.model_dump() for line in body.lines])
        return envelope(costs.costs(session, principal, record))


@router.put("/contracts/{ref}/applications", summary="Set the applications a contract covers")
def set_covered(request: Request, ref: str, body: CoveredListBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, CONTRACT, ref)
        costs.set_applications(
            session, principal, record, [item.model_dump() for item in body.applications]
        )
        return envelope(records.detail(session, principal, CONTRACT, record))


# --- Overlap and the heat map ---------------------------------------------------------------


@router.get("/overlap", summary="Capabilities served more than once")
def capability_overlap(
    request: Request,
    unit: int | None = Query(default=None, description="A unit, with those beneath it"),
    domain: str | None = Query(default=None),
) -> dict[str, Any]:
    """Every capability with more than one application in service, its applications side by
    side with their scores, recommendation, decision, users, and cost where the reader may
    see it. ``filters`` on each gives the same applications from ``/portfolio``."""
    principal = current(request)
    with reading(request) as session:
        return envelope(overlap.overlap(session, principal, {"unit": unit, "domain": domain}))


@router.get("/capability-heat", summary="The capability map, measured")
def capability_heat(request: Request) -> dict[str, Any]:
    """The capability tree, each capability with how many applications in service serve it,
    their average scores and confidence, and the technical health of the weakest."""
    principal = current(request)
    with reading(request) as session:
        return envelope(overlap.heat(session, principal, {}))


# --- The technology lifecycle ---------------------------------------------------------------


@router.get("/lifecycle", summary="Technology releases to their end of support")
def technology_lifecycle(
    request: Request,
    every: bool = Query(default=False, description="Releases nothing runs on as well"),
) -> dict[str, Any]:
    """The releases in use, soonest end of support first, each with how many components and
    applications are on it; and the applications with a planned retirement."""
    principal = current(request)
    with reading(request) as session:
        return envelope(lifecycle.timeline(session, principal, every=every))


@router.get("/radar", summary="The technologies in use, by ring")
def technology_radar(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(lifecycle.radar(session, principal))


@router.post("/imports/end-of-life", summary="Bring support dates in from a file")
def import_end_of_life(
    request: Request,
    body: dict[str, Any],
    dry_run: bool = Query(default=True, description="Say what would change, and change nothing"),
) -> dict[str, Any]:
    """The body is one object: each product's key, with its list of release cycles (``cycle``,
    ``releaseDate``, ``eol``, ``extendedSupport``, ``latest``). A product is matched to the
    technology whose end-of-life key it is. Releases are added and dates updated; nothing is
    removed."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(lifecycle.import_end_of_life(session, principal, body, dry_run=dry_run))


# --- Evidence for other processes -----------------------------------------------------------


@router.get("/data-handling", summary="The applications that handle a class of data")
def data_handling(
    request: Request,
    data_class: str | None = Query(default=None, description="A class of data, by its key"),
) -> dict[str, Any]:
    """How many applications in service handle each class of data; and, for the class
    chosen, each of them with its owner, sourcing, hosting, sign-in, technologies and their
    support, the interfaces that carry the class, and the standing of its data agreement.
    The same rows are exported by ``/exports/data-handling``."""
    principal = current(request)
    with reading(request) as session:
        return envelope(handling.handling(session, principal, data_class))


@router.get("/history", summary="Every change, newest first, for those who read everything")
def whole_history(
    request: Request,
    actor: int | None = Query(default=None, description="An account's id"),
    about: str | None = Query(default=None, description="A record's reference"),
    kind: str | None = Query(default=None, description="A kind of record, records, or other"),
    since: str | None = Query(default=None, description="From this date, year-month-day"),
    until: str | None = Query(default=None, description="Up to and including this date"),
    before: int | None = Query(default=None, description="The `next` of the page before"),
) -> dict[str, Any]:
    from datetime import UTC, date, datetime, timedelta

    from appwren.core.errors import Invalid
    from appwren.inventory import history

    def day(value: str | None, field: str, *, end: bool = False) -> datetime | None:
        if not value:
            return None
        try:
            found = date.fromisoformat(value)
        except ValueError:
            raise Invalid(
                "The dates were not understood.", {field: "Give a date, as year-month-day."}
            ) from None
        moment = datetime(found.year, found.month, found.day, tzinfo=UTC)
        return moment + timedelta(days=1) if end else moment

    with reading(request) as session:
        return envelope(
            history.everywhere(
                session,
                actor=actor,
                about=find_any(session, about) if about else None,
                kind=kind or None,
                since=day(since, "since"),
                until=day(until, "until", end=True),
                before=before,
            )
        )
