"""Shaping the program in the app: vocabularies, the organization's own fields, the wording of
the questions, and the scoring model with its cadence, previewed before it is published
(CUR-09)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing
from appwren.program import editing

router = APIRouter(prefix="/api/v1", tags=["program"])


class VocabularyBody(BaseModel):
    items: list[dict[str, Any]] = Field(
        description="Every value in order: its key, label, and any description; new values "
        "may leave the key empty; retired values say so"
    )


class FieldsBody(BaseModel):
    fields: list[dict[str, Any]]
    sensitive_fields: list[str] | None = None


class DefinitionBody(BaseModel):
    definition: dict[str, Any]


@router.get("/program", summary="The program as it stands, and what may be changed")
def get_program(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        del principal
        return envelope(editing.current(session))


@router.put("/program/vocabularies/{name}", summary="Rename, reorder, add to, or retire a list")
def put_vocabulary(request: Request, name: str, body: VocabularyBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(editing.save_vocabulary(session, principal, name, body.items))


@router.put("/program/fields", summary="The organization's own fields, and which are sensitive")
def put_fields(request: Request, body: FieldsBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(editing.save_fields(session, principal, body.fields, body.sensitive_fields))


@router.put("/program/questionnaire", summary="Publish new wording of the questions")
def put_questionnaire(request: Request, body: DefinitionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(editing.save_questionnaire(session, principal, body.definition))


@router.post("/program/scoring/preview", summary="What a changed scoring model would change")
def preview_scoring(request: Request, body: DefinitionBody) -> dict[str, Any]:
    """Every application in service whose scores, confidence, recommendation, or flags would
    differ. Nothing is saved."""
    principal = current(request)
    with reading(request) as session:
        return envelope(editing.preview_model(session, principal, body.definition))


@router.put("/program/scoring", summary="Publish a new version of the scoring model")
def put_scoring(request: Request, body: DefinitionBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(editing.publish_model(session, principal, body.definition))
