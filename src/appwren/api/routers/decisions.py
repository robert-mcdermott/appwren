"""Decisions, the portfolio as a whole, and snapshots of it."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Request
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
