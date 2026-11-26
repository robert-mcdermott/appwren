"""Decisions, the portfolio as a whole, and snapshots of it."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren import decisions
from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION

router = APIRouter(prefix="/api/v1", tags=["decisions and the portfolio"])


class DecisionBody(BaseModel):
    disposition: str = Field(description="From the dispositions vocabulary")
    rationale: str = Field(max_length=4000)
    review_on: date | None = Field(
        default=None, description="When to look again; a year by default"
    )
    target_on: date | None = Field(default=None, description="When it should be done")
    successor: str | None = Field(
        default=None, description="The application its users move to; needed to consolidate"
    )


class SnapshotBody(BaseModel):
    name: str = Field(max_length=200, description="Such as 2026 Q4 review")


FILTERS = {
    "unit": Query(default=None, description="A unit, with those beneath it"),
    "lifecycle": Query(default=None),
    "sourcing": Query(default=None),
    "domain": Query(default=None),
    "tier": Query(default=None),
}


@router.post("/applications/{ref}/decisions", status_code=201, summary="Record what to do with it")
def add_decision(request: Request, ref: str, body: DecisionBody) -> dict[str, Any]:
    """A manager, or a leader of its unit, records a disposition with a rationale; never the
    application's own accountable owner. The scores as they are now are kept with it."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = decisions.record(session, principal, app, body.model_dump())
        return envelope(decisions.view(session, row))


@router.get("/applications/{ref}/decisions", summary="An application's decisions")
def list_application_decisions(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(decisions.history(session, app))


@router.get("/portfolio", summary="Every application with its scores and decision")
def portfolio(
    request: Request,
    unit: int | None = FILTERS["unit"],
    lifecycle: str | None = FILTERS["lifecycle"],
    sourcing: str | None = FILTERS["sourcing"],
    domain: str | None = FILTERS["domain"],
    tier: str | None = FILTERS["tier"],
    mismatch: bool | None = Query(default=None, description="Only those with a mismatch"),
    review_due: bool | None = Query(default=None, description="Only decisions past review"),
    decided: bool | None = Query(default=None, description="Only those with a decision"),
) -> dict[str, Any]:
    """What the portfolio chart, the decisions list, and the dashboard are drawn from. Cost
    is withheld from those who may not see it."""
    principal = current(request)
    filters = {"unit": unit, "lifecycle": lifecycle, "sourcing": sourcing, "domain": domain,
               "tier": tier}  # fmt: skip
    with reading(request) as session:
        rows = decisions.portfolio(session, principal, filters)
    if mismatch is not None:
        rows = [row for row in rows if row["mismatch"] is mismatch]
    if decided is not None:
        rows = [row for row in rows if (row["decision"] is not None) is decided]
    if review_due is not None:
        today = date.today()
        rows = [
            row for row in rows if bool(row["review_on"] and row["review_on"] < today) is review_due
        ]
    return envelope(rows, total=len(rows))


@router.get("/score-snapshots/{snapshot_id}", summary="A score as it was kept")
def score_snapshot(request: Request, snapshot_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(decisions.snapshot_of(session, principal, snapshot_id))


@router.get("/portfolio-snapshots", summary="The portfolio snapshots taken")
def list_snapshots(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(decisions.portfolio_snapshots(session))


@router.post("/portfolio-snapshots", status_code=201, summary="Keep the portfolio's scores")
def take_snapshot(request: Request, body: SnapshotBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = decisions.take_portfolio_snapshot(session, principal, body.name)
        return envelope(decisions.portfolio_snapshot(session, principal, row.ref))


@router.get("/portfolio-snapshots/{ref}", summary="One portfolio snapshot")
def show_snapshot(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(decisions.portfolio_snapshot(session, principal, ref))
