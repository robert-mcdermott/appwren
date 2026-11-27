"""Keeping current: campaigns that ask the owners in a unit to confirm or assess by a date
(CUR-05), tasks raised by what happens (CUR-06), passing on what a person holds (CUR-07),
search and saved views (CUR-08), likely duplicates (INV-15), and contested scores (SCR-13)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import duplicates, find, records
from appwren.inventory.registry import APPLICATION
from appwren.oversight import campaigns, contests, handover, tasks, views

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


# --- Tasks ------------------------------------------------------------------------------------


class CloseBody(BaseModel):
    how: str = Field(default="done", description="done, or dismissed")
    note: str = Field(default="", max_length=2000)


@router.get("/tasks", summary="Tasks: open ones by default")
def list_tasks(
    request: Request,
    status: str | None = Query(default=None, description="open, done, dismissed, or all"),
    kind: str | None = Query(default=None),
    mine: bool = Query(default=False, description="Only yours"),
    unassigned: bool = Query(default=False, description="Only those with nobody to do them"),
) -> dict[str, Any]:
    """Each person sees their own tasks; stewards, leaders, and managers those about the
    applications in their units; those who read everything, all of them."""
    principal = current(request)
    with reading(request) as session:
        rows = tasks.listing(
            session, principal,
            {"status": status, "kind": kind, "mine": mine, "unassigned": unassigned},
        )  # fmt: skip
        return envelope(rows, total=len(rows))


@router.get("/tasks/{task_id}", summary="One task")
def get_task(request: Request, task_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(tasks.view(session, principal, tasks.load(session, principal, task_id)))


@router.post("/tasks/{task_id}/close", summary="Mark a task done, or dismiss it")
def close_task(request: Request, task_id: int, body: CloseBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        task = tasks.load(session, principal, task_id)
        tasks.close(session, principal, task, how=body.how, note=body.note)
        return envelope(tasks.view(session, principal, task))


# --- What a person holds ----------------------------------------------------------------------


class HandOverBody(BaseModel):
    to: int = Field(description="The account to pass everything to")


@router.get("/accounts/{account_id}/holdings", summary="Everything a person holds")
def holdings(request: Request, account_id: int) -> dict[str, Any]:
    """The records they are named on, the contracts and interfaces they own, their open
    tasks, and what open campaigns still ask of them."""
    principal = current(request)
    with reading(request) as session:
        if not (handover.may_hand_over(principal) or principal.account_id == account_id):
            from appwren.core.errors import PermissionDenied

            raise PermissionDenied("Only an administrator or a manager sees what someone holds.")
        return envelope(handover.holdings(session, account_id))


@router.post("/accounts/{account_id}/hand-over", summary="Pass everything a person holds on")
def hand_over(request: Request, account_id: int, body: HandOverBody) -> dict[str, Any]:
    """Each role on each record, each contract and interface owned, each open task, and each
    pending campaign item goes to one person, in one step."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        moved = handover.hand_over(session, principal, account_id, body.to)
        return envelope({"moved": moved, "left": handover.holdings(session, account_id)})


# --- Finding, and keeping the record in order ------------------------------------------------


class ViewBody(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    path: str | None = Field(default=None, max_length=80, description="The list: /applications")
    query: str | None = Field(default=None, max_length=1000, description="Its filters")
    shared: bool | None = None


class ContestBody(BaseModel):
    factor: str = Field(default="", max_length=60, description="The factor's key")
    level_claimed: int | None = Field(default=None, description="What it should be, 1 to 5")
    note: str = Field(default="", max_length=4000)
    evidence_url: str | None = Field(default=None, max_length=500)


class AnswerBody(BaseModel):
    accept: bool
    answer: str = Field(default="", max_length=4000)


@router.get("/search", summary="One search across every kind of record")
def search(
    request: Request,
    q: str = Query(default="", description="A name, a reference, or a few words"),
    type: str | None = Query(default=None, description="Only this kind of record"),
    limit: int = Query(default=6, ge=1, le=50, description="How many of each kind"),
) -> dict[str, Any]:
    """Grouped by kind, the best answer first. It finds only what the searcher may open,
    because it asks each kind's own list."""
    principal = current(request)
    with reading(request) as session:
        return envelope(find.everywhere(session, principal, q, only=type, each=limit))


@router.get("/views", summary="Your saved views, and the shared ones")
def list_views(request: Request, path: str | None = Query(default=None)) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        rows = views.listed(session, principal, path)
        return envelope(rows, total=len(rows))


@router.post("/views", summary="Save a list's filters under a name", status_code=201)
def save_view(request: Request, body: ViewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = views.create(session, principal, body.model_dump(exclude_none=True))
        return envelope(views.view(row, principal))


@router.patch("/views/{view_id}", summary="Rename, change, or share a saved view")
def change_view(request: Request, view_id: int, body: ViewBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = views.get(session, principal, view_id, to_change=True)
        views.update(session, principal, row, body.model_dump(exclude_none=True))
        return envelope(views.view(row, principal))


@router.delete("/views/{view_id}", summary="Delete a saved view")
def delete_view(request: Request, view_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        views.delete(session, principal, views.get(session, principal, view_id, to_change=True))
        return envelope({"deleted": view_id})


@router.get("/similar-applications", summary="Applications a new one may be already")
def similar_applications(
    request: Request,
    name: str = Query(default=""),
    aliases: str = Query(default="", description="Other names it goes by, separated by commas"),
    vendor: str | None = Query(default=None, description="A vendor's reference"),
    product: str | None = Query(default=None),
    exclude: str | None = Query(default=None, alias="except", description="This one's reference"),
) -> dict[str, Any]:
    """Those already on record whose name or alias is close to this name or its aliases, or
    that are the same product from the same vendor (INV-15)."""
    principal = current(request)
    with reading(request) as session:
        vendor_id = None
        if vendor:
            from appwren.inventory.registry import VENDOR
            from appwren.inventory.registry import find as find_record

            try:
                vendor_id = find_record(session, VENDOR, vendor).id
            except Exception:  # an unknown vendor matches nothing by product
                vendor_id = None
        found = duplicates.similar(
            session, principal, name=name,
            aliases=[each.strip() for each in aliases.split(",") if each.strip()],
            vendor_id=vendor_id,
            product=product, except_ref=exclude,
        )  # fmt: skip
        return envelope(found, total=len(found))


@router.get("/applications/{ref}/contests", summary="Contests of an application's scores")
def list_contests(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(
            {
                "contests": contests.of_application(session, principal, app),
                "can_raise": contests.may_raise(session, principal, app),
            }
        )


@router.post(
    "/applications/{ref}/contests", summary="Say one factor is wrong, and why", status_code=201
)
def raise_contest(request: Request, ref: str, body: ContestBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = contests.raise_contest(session, principal, app, body.model_dump())
        return envelope(contests.view(row, principal, app))


@router.get("/contests", summary="Contests waiting for your answer")
def waiting_contests(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        rows = contests.waiting(session, principal)
        return envelope(rows, total=len(rows))


@router.post("/contests/{contest_id}/answer", summary="Accept a contest, or answer it")
def answer_contest(request: Request, contest_id: int, body: AnswerBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = contests.load(session, principal, contest_id)
        contests.answer(session, principal, row, accept=body.accept, text=body.answer)
        from appwren.db.models import Application

        app = session.get(Application, row.application_id)
        assert app is not None
        return envelope(contests.view(row, principal, app))
