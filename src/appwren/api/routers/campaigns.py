"""Campaigns: the owners of the applications in a unit asked to confirm or to assess by a
date (CUR-05)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.oversight import campaigns

router = APIRouter(prefix="/api/v1", tags=["keeping current"])


class CampaignBody(BaseModel):
    name: str = Field(default="", max_length=200)
    kind: str = Field(default="", description="confirm or assess")
    org_unit_id: int | None = Field(default=None, description="Omit for the whole organization")
    tiers: list[str] = Field(default_factory=list, description="Only these tiers; all if empty")
    stages: list[str] = Field(default_factory=list, description="Only these stages; all if empty")
    due_on: str = Field(default="", description="The date it is due by")
    message: str | None = Field(default=None, max_length=2000)


class ExcuseBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


@router.get("/campaigns", summary="Campaigns, newest first, with their progress")
def list_campaigns(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        rows = campaigns.listing(session, principal)
        return envelope(rows, total=len(rows))


@router.post("/campaigns/preview", summary="What a campaign would ask, and of whom")
def preview_campaign(request: Request, body: CampaignBody) -> dict[str, Any]:
    """How many applications it would cover and how many people it would ask, and which
    applications have nobody to ask. Nothing is saved."""
    principal = current(request)
    with reading(request) as session:
        return envelope(campaigns.preview(session, principal, body.model_dump()))


@router.post("/campaigns", summary="Start a campaign", status_code=201)
def start_campaign(request: Request, body: CampaignBody) -> dict[str, Any]:
    """Makes an item for each application in service in the unit and beneath it, of the tiers
    and stages named, and tells each person asked once, with a count."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.start(session, principal, body.model_dump())
        return envelope(campaigns.detail(session, principal, campaign, {}))


@router.get("/campaigns/{ref}", summary="A campaign, its coverage by unit, and its items")
def get_campaign(
    request: Request,
    ref: str,
    unit: str | None = Query(default=None, description="Only this unit's items"),
    status: str | None = Query(default=None, description="pending, done, or excused"),
    mine: bool = Query(default=False, description="Only what was asked of you"),
) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.load(session, ref)
        campaigns.refresh(session, campaign)  # what has been done since is shown as done
        return envelope(
            campaigns.detail(session, principal, campaign, {"unit": unit, "status": status,
                                                            "mine": mine})
        )  # fmt: skip


@router.post("/campaigns/{ref}/remind", summary="Remind whoever still owes something")
def remind_campaign(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.load(session, ref)
        return envelope({"told": campaigns.remind(session, principal, campaign)})


@router.post("/campaigns/{ref}/close", summary="Close a campaign, keeping what it found")
def close_campaign(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.end(session, principal, campaigns.load(session, ref), "close")
        return envelope(campaigns.detail(session, principal, campaign, {}))


@router.post("/campaigns/{ref}/cancel", summary="Cancel a campaign")
def cancel_campaign(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.end(session, principal, campaigns.load(session, ref), "cancel")
        return envelope(campaigns.detail(session, principal, campaign, {}))


@router.post(
    "/campaigns/{ref}/items/{item_id}/excuse", summary="Excuse one application, with a reason"
)
def excuse_item(request: Request, ref: str, item_id: int, body: ExcuseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        campaign = campaigns.load(session, ref)
        campaigns.excuse(session, principal, campaign, item_id, body.reason)
        return envelope(campaigns.detail(session, principal, campaign, {}))
