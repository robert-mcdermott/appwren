"""Insight: trends between portfolio snapshots, scores over time, and shares of the
portfolio (RPT-04, SCR-14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from appwren.access.policy import current
from appwren.api.common import envelope, reading
from appwren.insight import shares, trends
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION

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
