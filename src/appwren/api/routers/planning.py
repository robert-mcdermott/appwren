"""Planning change: portfolio reviews and their agendas (PLN-01), and initiatives and the
roadmap (PLN-02)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import records
from appwren.inventory.registry import INITIATIVE, REVIEW
from appwren.planning import initiatives, reviews

router = APIRouter(prefix="/api/v1", tags=["planning"])


class ItemBody(BaseModel):
    application: str = Field(description="The application's reference")
    note: str | None = Field(default=None, max_length=2000, description="What to decide")


def _shown(session: Any, principal: Any, review: Any) -> dict[str, Any]:
    return envelope(records.detail(session, principal, REVIEW, review))


@router.post("/reviews/{ref}/draw", summary="Draw the agenda from the review's scope")
def draw_agenda(request: Request, ref: str) -> dict[str, Any]:
    """Adds the applications in scope whose decision differs from today's recommendation,
    whose decision is due for review by the review's date, or that have no decision. What
    is already on the agenda stays."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = reviews.load(session, principal, ref)
        added = reviews.draw(session, principal, review)
        shown = _shown(session, principal, review)
        shown["meta"]["added"] = added
        return shown


@router.post("/reviews/{ref}/items", summary="Put an application on the agenda", status_code=201)
def add_item(request: Request, ref: str, body: ItemBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = reviews.load(session, principal, ref)
        reviews.add_item(session, principal, review, body.application, body.note)
        return _shown(session, principal, review)


@router.delete("/reviews/{ref}/items/{item_id}", summary="Take an application off the agenda")
def remove_item(request: Request, ref: str, item_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = reviews.load(session, principal, ref)
        reviews.remove_item(session, principal, review, item_id)
        return _shown(session, principal, review)


@router.post("/reviews/{ref}/open", summary="Open the review")
def open_review(request: Request, ref: str) -> dict[str, Any]:
    """From now until it is closed, a decision recorded for an application on the agenda is
    shown on its item."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = reviews.open_review(session, principal, reviews.load(session, principal, ref))
        return _shown(session, principal, review)


@router.post("/reviews/{ref}/close", summary="Close the review, keeping what was decided")
def close_review(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        review = reviews.close_review(session, principal, reviews.load(session, principal, ref))
        return _shown(session, principal, review)


class InitiativeApplicationBody(BaseModel):
    application: str = Field(description="The application's reference")
    action: str = Field(default="changes", description="changes, retires, or receives")
    note: str | None = Field(default=None, max_length=500)


class InitiativeApplicationsBody(BaseModel):
    applications: list[InitiativeApplicationBody]


@router.put("/initiatives/{ref}/applications", summary="Say which applications it changes")
def set_initiative_applications(
    request: Request, ref: str, body: InitiativeApplicationsBody
) -> dict[str, Any]:
    """Replaces the applications it names, each with what it does to it. One the person may
    not see is left as it was."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = records.load(session, principal, INITIATIVE, ref)
        initiatives.set_applications(
            session, principal, record, [item.model_dump() for item in body.applications]
        )
        return envelope(records.detail(session, principal, INITIATIVE, record))


@router.get("/roadmap", summary="Initiatives on a timeline")
def roadmap(
    request: Request,
    unit: int | None = Query(default=None, description="A unit, with those beneath it"),
    kind: str | None = Query(default=None, description="From initiative_kinds"),
    stage: str | None = Query(default=None, description="From initiative_stages"),
    closed: bool = Query(default=False, description="Include those done or cancelled"),
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        filters = {"unit": unit, "kind": kind, "stage": stage, "closed": closed}
        return envelope(initiatives.roadmap(session, principal, filters))
