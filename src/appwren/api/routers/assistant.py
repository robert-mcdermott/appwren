"""The optional assistant: drafting an application, and answering questions (INT-06)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from appwren import assistant
from appwren.access.policy import current
from appwren.api.common import envelope, reading, writing

router = APIRouter(prefix="/api/v1", tags=["assistant"])


def _ask(request: Request) -> assistant.Ask:
    return getattr(request.app.state, "assistant_ask", assistant.ask_server)


class DraftBody(BaseModel):
    text: str = Field(max_length=20_000, description="A document describing the application")


class QuestionBody(BaseModel):
    question: str = Field(max_length=2_000, description="A question about the portfolio")


@router.post("/assistant/draft", summary="Draft an application from a document")
def draft(request: Request, body: DraftBody) -> dict[str, Any]:
    """Values for the form to add an application, from the document's text. Nothing is
    saved: the person reads, corrects, and adds it themselves. 404 if there is no
    assistant."""
    principal = current(request)
    config = request.app.state.config.assistant
    with reading(request) as session:
        prepared = assistant.prepare_draft(session, principal, config, body.text)
    answer, error = assistant.call(config, prepared, _ask(request))  # no session open
    with writing(request, principal.actor) as session:
        return envelope(assistant.finish_draft(session, principal, config, prepared, answer,
                                               error))  # fmt: skip


@router.post("/assistant/ask", summary="Ask a question about the portfolio")
def ask(request: Request, body: QuestionBody) -> dict[str, Any]:
    """An answer from the applications the person may see, with links to the records it
    cites. 404 if there is no assistant."""
    principal = current(request)
    config = request.app.state.config.assistant
    with reading(request) as session:
        prepared = assistant.prepare_question(session, principal, config, body.question)
    answer, error = assistant.call(config, prepared, _ask(request))  # no session open
    with writing(request, principal.actor) as session:
        return envelope(assistant.finish_question(session, principal, config, prepared, answer,
                                                  error))  # fmt: skip


@router.get("/assistant/exchanges", summary="What has been asked of the assistant")
def exchanges(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(assistant.exchanges(session, principal))
