"""The landscape: where data travels between applications (and, later in the wave, what
depends on what, where things run, and what they cost)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from appwren.access.policy import current
from appwren.api.common import envelope, reading
from appwren.landscape import interfaces

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
