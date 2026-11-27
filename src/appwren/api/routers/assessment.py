"""Assessments and scores: the question bank, the scoring model, an application's scores
with their working, a preview while answering, and assessments themselves."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from appwren import assessment
from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from appwren.oversight import attestation

router = APIRouter(prefix="/api/v1", tags=["assessment and scores"])


class AnswersBody(BaseModel):
    answers: dict[str, Any] = Field(
        description="Each question's key: a level from 1 to 5, null for don't know, or "
        "{level, note}"
    )
    note: str | None = Field(default=None, max_length=2000)


@router.get("/questionnaire", summary="The current question bank")
def questionnaire(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        row = assessment.current_questionnaire(session)
        return envelope({"version": row.version, **row.definition})


@router.get("/scoring-model", summary="The current scoring model")
def scoring_model(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        row = assessment.current_model(session)
        return envelope({"version": row.version, **row.definition})


@router.get("/applications/{ref}/scores", summary="An application's scores, with the working")
def scores(request: Request, ref: str) -> dict[str, Any]:
    """Business value, technical health, cost and burden, and risk exposure; data confidence;
    the recommendation with the rule that produced it; the flags; and what would raise
    confidence. Anything a sensitive field would reveal is withheld from those who may not
    see it."""
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        result = assessment.score_one(session, app)
        model = assessment.current_model(session).definition
        return envelope(
            {
                **assessment.shown(session, principal, app, result),
                "confirmation": attestation.state(session, principal, app, model),
            }
        )


class ConfirmBody(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.get("/applications/{ref}/confirmations", summary="Who has confirmed the record, and when")
def confirmations(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        model = assessment.current_model(session).definition
        return envelope(
            {
                **attestation.state(session, principal, app, model),
                "history": attestation.history(session, app),
            }
        )


@router.post(
    "/applications/{ref}/confirmations",
    summary="Confirm that the record is right",
    status_code=201,
)
def confirm(request: Request, ref: str, body: ConfirmBody) -> dict[str, Any]:
    """Anyone named on the application, its unit's stewards, and managers confirm that its
    record and its parts are right as of today (CUR-03)."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = attestation.confirm(session, principal, app, note=body.note)
        model = assessment.current_model(session).definition
        return envelope(
            {
                **attestation.state(session, principal, app, model),
                "confirmed": attestation.view(row),
            }
        )


@router.post("/applications/{ref}/score-preview", summary="What the scores would be")
def score_preview(request: Request, ref: str, body: AnswersBody) -> dict[str, Any]:
    """The scores these answers would give, from the same engine as the record. Nothing is
    saved."""
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        result = assessment.preview(session, principal, app, body.answers)
        return envelope(assessment.shown(session, principal, app, result))


@router.get("/applications/{ref}/assessments", summary="An application's assessments")
def list_assessments(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(assessment.history(session, app))


@router.post("/applications/{ref}/assessments", status_code=201, summary="Answer the assessment")
def add_assessment(request: Request, ref: str, body: AnswersBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = assessment.record(session, principal, app, body.answers, note=body.note)
        result = assessment.score_one(session, app)
        return envelope(
            {
                "assessment": assessment.view(row),
                "scores": assessment.shown(session, principal, app, result),
            }
        )
