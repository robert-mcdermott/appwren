"""The landscape: where data travels between applications (and, later in the wave, what
depends on what, where things run, and what they cost)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from appwren.access.policy import current
from appwren.api.common import envelope, reading
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, find_any
from appwren.landscape import graph, interfaces

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
