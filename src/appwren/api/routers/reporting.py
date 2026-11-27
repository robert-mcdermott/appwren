"""What each person owes, where the portfolio stands, and lists in and out."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from appwren import reporting
from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.api.routers.people import _csv
from appwren.core.errors import Invalid
from appwren.reporting import exchange

router = APIRouter(prefix="/api/v1", tags=["reports, imports, and exports"])
DOWNLOAD_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
NOT_FILTERS = {"format", "limit", "cursor"}


def _filters(request: Request) -> dict[str, Any]:
    return {key: value for key, value in request.query_params.items() if key not in NOT_FILTERS}


@router.get("/home", summary="What the signed-in person owes")
def home(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(reporting.owed(session, principal))


@router.get("/dashboard", summary="Where the portfolio stands")
def dashboard(
    request: Request,
    unit: int | None = Query(default=None, description="A unit, with those beneath it"),
    domain: str | None = Query(default=None),
) -> dict[str, Any]:
    """Each figure carries the filters of the list that produces it, so it can only open
    exactly what it counted (RPT-03)."""
    principal = current(request)
    with reading(request) as session:
        return envelope(reporting.dashboard(session, principal, {"unit": unit, "domain": domain}))


@router.get("/data-quality", summary="How much of the portfolio can be trusted")
def data_quality(
    request: Request,
    unit: int | None = Query(default=None, description="A unit, with those beneath it"),
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(reporting.data_quality(session, principal, {"unit": unit}))


@router.get("/portfolio", summary="Every application with its scores and decision")
def portfolio(request: Request) -> dict[str, Any]:
    """The applications the person may see, each with its scores, recommendation, decision,
    flags, and what its record lacks; cost is withheld from those who may not see it.
    Filters: ``unit``, ``lifecycle``, ``sourcing``, ``domain``, ``tier``; and, worked out from
    the scores, ``recommendation``, ``decision`` (``none`` for undecided), ``flag``,
    ``confidence_min``, ``confidence_max``, ``eol`` (``past`` or ``ending``), ``quality``,
    ``unit_only``, ``mismatch``, ``decided``, ``review_due``, and ``in_service``."""
    principal = current(request)
    with reading(request) as session:
        rows = reporting.portfolio_list(session, principal, _filters(request))
    return envelope(rows, total=len(rows))


@router.get(
    "/exports/{kind}",
    summary="A list, as filtered, as CSV or JSON",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}, "application/json": {}}}},
)
def export_list(
    request: Request, kind: str, format: str = Query(default="csv", description="csv or json")
) -> Response:
    """``kind`` is ``applications``, ``components``, ``vendors``, ``technologies``,
    ``capabilities``, or ``portfolio``. Every other parameter is a filter that list takes.
    What comes back is what the asker may see, and taking it is recorded in the history."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        text, media_type, name = exchange.export(
            session, principal, kind, format, _filters(request)
        )
    return Response(
        content=text.encode("utf-8"),
        media_type=media_type,
        headers={**DOWNLOAD_HEADERS, "Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/imports/applications/fields", summary="What a file of applications may hold")
def import_fields(request: Request) -> dict[str, Any]:
    return envelope(exchange.fields())


@router.post(
    "/imports/applications",
    summary="Bring applications in from a CSV file",
    openapi_extra={"requestBody": {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
async def import_applications(
    request: Request,
    dry_run: bool = Query(default=True, description="Check everything and keep nothing"),
    mapping: str | None = Query(
        default=None, description="JSON: which column holds each field, where headings differ"
    ),
) -> dict[str, Any]:
    """Rows with a reference that is on record update that application; others are added. A
    dry run reports every problem by row; nothing is loaded unless every row can be."""
    principal = current(request)
    text = await _csv(request)
    chosen = None
    if mapping:
        try:
            chosen = json.loads(mapping)
        except ValueError as exc:
            raise Invalid("The mapping is not JSON.", {"mapping": str(exc)}) from exc

    def run() -> dict[str, Any]:
        db = request.app.state.db
        with db.write(principal.actor) as session:
            report = exchange.import_applications(
                session, principal, text, mapping=chosen, dry_run=dry_run
            )
            if not report.applied:
                session.rollback()
            return report.view()

    return envelope(await run_in_threadpool(run))
