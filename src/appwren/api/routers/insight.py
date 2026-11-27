"""Insight: trends between portfolio snapshots, scores over time, and shares of the
portfolio (RPT-04, SCR-14), leadership reports (RPT-05), the record as of a day (RPT-06),
and scenarios (PLN-04)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.insight import asof, reports, scenarios, shares, trends
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, INITIATIVE, SCENARIO

router = APIRouter(prefix="/api/v1", tags=["insight"])


@router.get("/trends", summary="How the portfolio moved between two snapshots")
def compare_snapshots(
    request: Request,
    before: str = Query(description="The earlier portfolio snapshot's reference"),
    after: str | None = Query(default=None, description="The later one; today if none"),
) -> dict[str, Any]:
    """The figures each held, the applications whose recommendation changed, whose scores
    moved by half a point or more, and whose flags came or went, and the decisions recorded
    between them."""
    principal = current(request)
    with reading(request) as session:
        return envelope(trends.compare(session, principal, before, after))


@router.get("/applications/{ref}/score-history", summary="An application's scores over time")
def score_history(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(trends.over_time(session, principal, app))


@router.get("/shares", summary="Shares of the portfolio: the costliest tenth, and others")
def portfolio_shares(request: Request) -> dict[str, Any]:
    """Which applications are at one end of the portfolio. A share never feeds a score."""
    principal = current(request)
    with reading(request) as session:
        return envelope(shares.shares(session, principal))


class ReportBody(BaseModel):
    title: str = Field(max_length=200, description="What the report is called")
    period_from: str = Field(description="The first day of the period, YYYY-MM-DD")
    period_to: str = Field(description="Its last day, today or earlier")


@router.get("/reports", summary="Leadership reports, the latest period first")
def list_reports(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(reports.listing(session, principal))


@router.post("/reports", summary="Make a leadership report for a period", status_code=201)
def make_report(request: Request, body: ReportBody) -> dict[str, Any]:
    """Works the report out from the records as they are now, and keeps it whole. Reopening it
    reads what was kept."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = reports.make(session, principal, body.model_dump())
        return envelope(reports.view(row))


@router.get("/reports/{ref}", summary="A leadership report, as it was made")
def get_report(request: Request, ref: str) -> dict[str, Any]:
    """The report as stored, with its digest and whether it still matches."""
    principal = current(request)
    with reading(request) as session:
        return envelope(reports.view(reports.load(session, principal, ref)))


@router.get("/as-of", summary="The portfolio as it stood on a day")
def portfolio_as_of(
    request: Request, on: str = Query(description="The day, YYYY-MM-DD, today or earlier")
) -> dict[str, Any]:
    """The applications in service at the end of that day, each with its stage, unit, tier,
    and decision then, beside its stage and decision now. Read from the history."""
    principal = current(request)
    with reading(request) as session:
        return envelope(asof.portfolio(session, principal, asof.day(on)))


@router.get("/applications/{ref}/as-of", summary="An application as it stood on a day")
def application_as_of(
    request: Request, ref: str,
    on: str = Query(description="The day, YYYY-MM-DD, today or earlier"),
) -> dict[str, Any]:  # fmt: skip
    """Each of its values at the end of that day beside its value now, its decision then, and
    its scores in the nearest portfolio snapshot taken on or before it."""
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(asof.application(session, principal, app, asof.day(on)))


class ScenarioChangeBody(BaseModel):
    application: str = Field(description="The application's reference")
    action: str = Field(description="retire, consolidate, or replace")
    into: str | None = Field(default=None, description="What it moves into, or is replaced by")
    note: str | None = Field(default=None, max_length=500)


class ScenarioChangesBody(BaseModel):
    changes: list[ScenarioChangeBody]


class ScenarioInitiativeBody(BaseModel):
    name: str | None = Field(default=None, max_length=200, description="The scenario's, if none")
    org_unit_id: int | None = Field(default=None, description="The first application's, if none")


@router.put("/scenarios/{ref}/changes", summary="Say what a scenario would change")
def set_scenario_changes(request: Request, ref: str, body: ScenarioChangesBody) -> dict[str, Any]:
    """Replaces the applications it names, each retired, consolidated into another, or
    replaced by another. Its effect is worked out again. No application changes."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, SCENARIO, ref)
        scenarios.set_changes(
            session, principal, record, [item.model_dump() for item in body.changes]
        )
        return envelope(records.detail(session, principal, SCENARIO, record))


@router.post("/scenarios/{ref}/initiative", summary="Make an initiative of a scenario",
             status_code=201)  # fmt: skip
def scenario_to_initiative(
    request: Request, ref: str, body: ScenarioInitiativeBody
) -> dict[str, Any]:
    """A proposed initiative naming the same applications. The scenario changes no more."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, SCENARIO, ref)
        made = scenarios.to_initiative(session, principal, record, body.model_dump())
        return envelope(records.detail(session, principal, INITIATIVE, made))
