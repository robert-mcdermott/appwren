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
from appwren.landscape import costs, graph, interfaces

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
