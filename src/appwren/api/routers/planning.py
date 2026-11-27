"""Planning change: portfolio reviews and their agendas (PLN-01), and initiatives and the
roadmap (PLN-02), requests for something new (PLN-03), and retirements (DEC-07)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, INITIATIVE, REQUEST, REVIEW
from appwren.planning import initiatives, intake, retirements, reviews

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


class OptionBody(BaseModel):
    approach: str = Field(description="build, buy, partner, or reuse")
    name: str | None = Field(default=None, max_length=200)
    vendor: str | None = Field(default=None, description="A vendor's reference")
    application: str | None = Field(default=None, description="For reuse: an application")
    annual_cost: int | None = Field(default=None, ge=0)
    fit: int | None = Field(default=None, ge=1, le=5, description="How well it fits, 1 to 5")
    notes: str | None = Field(default=None, max_length=2000)


class OptionsBody(BaseModel):
    options: list[OptionBody]


class EndBody(BaseModel):
    reason: str = Field(default="", max_length=2000)
    name: str | None = Field(default=None, max_length=200, description="To approve: its name")
    application: str | None = Field(default=None, description="To say it is met: by which")


def _request(session: Any, principal: Any, ref: str) -> Any:
    return records.load(session, principal, REQUEST, ref)


@router.put("/requests/{ref}/options", summary="The ways to meet a request")
def set_request_options(request: Request, ref: str, body: OptionsBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        record = _request(session, principal, ref)
        intake.set_options(session, principal, record,
                           [item.model_dump() for item in body.options])  # fmt: skip
        return envelope(records.detail(session, principal, REQUEST, record))


@router.post("/requests/{ref}/approve", summary="Approve it: add a proposed application")
def approve_request(request: Request, ref: str, body: EndBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor, context={"reason": body.reason}) as session:
        record = _request(session, principal, ref)
        intake.approve(session, principal, record, body.reason, body.name)
        return envelope(records.detail(session, principal, REQUEST, record))


@router.post("/requests/{ref}/meet", summary="Say an application on record meets it")
def meet_request(request: Request, ref: str, body: EndBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor, context={"reason": body.reason}) as session:
        record = _request(session, principal, ref)
        intake.meet(session, principal, record, body.application or "", body.reason)
        return envelope(records.detail(session, principal, REQUEST, record))


@router.post("/requests/{ref}/decline", summary="Decline it, with why")
def decline_request(request: Request, ref: str, body: EndBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor, context={"reason": body.reason}) as session:
        record = _request(session, principal, ref)
        intake.decline(session, principal, record, body.reason)
        return envelope(records.detail(session, principal, REQUEST, record))


class RetirementBody(BaseModel):
    planned_on: str | None = Field(default=None, description="To be retired by: YYYY-MM-DD")
    note: str | None = Field(default=None, max_length=2000)


class StepBody(BaseModel):
    done: bool = True
    note: str | None = Field(default=None, max_length=1000)


def _application(session: Any, principal: Any, ref: str) -> Any:
    return records.load(session, principal, APPLICATION, ref)


@router.get("/applications/{ref}/retirement", summary="An application's retirement plan")
def get_retirement(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = _application(session, principal, ref)
        return envelope(retirements.view(session, principal, app))


@router.post("/applications/{ref}/retirement", summary="Start its retirement plan",
             status_code=201)  # fmt: skip
def start_retirement(request: Request, ref: str, body: RetirementBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = _application(session, principal, ref)
        retirements.start(session, principal, app, body.planned_on, body.note)
        return envelope(retirements.view(session, principal, app))


@router.put("/applications/{ref}/retirement/steps/{step}", summary="Mark a step done, or not")
def mark_retirement_step(request: Request, ref: str, step: str, body: StepBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = _application(session, principal, ref)
        retirements.mark(session, principal, app, step, body.done, body.note)
        return envelope(retirements.view(session, principal, app))


@router.post("/applications/{ref}/retirement/complete", summary="Retire it, every step done")
def complete_retirement(request: Request, ref: str) -> dict[str, Any]:
    """Retires the application and keeps its annual cost then as the savings."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = _application(session, principal, ref)
        retirements.complete(session, principal, app)
        return envelope(retirements.view(session, principal, app))


@router.delete("/applications/{ref}/retirement", summary="Cancel its retirement plan")
def cancel_retirement(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = _application(session, principal, ref)
        retirements.cancel(session, principal, app)
        return envelope(retirements.view(session, principal, app))


@router.get("/retirements", summary="Retirements under way and done, with the savings")
def retirement_report(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(retirements.report(session, principal))
