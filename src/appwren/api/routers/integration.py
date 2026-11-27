"""What other systems use: API tokens, webhooks, and the checkpoint (INT-02 to INT-04)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import database, envelope, reading, writing
from appwren.integration import checkpoint, suggestions, tokens, webhooks
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION

router = APIRouter(prefix="/api/v1", tags=["integration"])


@router.get("/checkpoint/{ref}", summary="Is this application approved, and for this data?")
def ask_checkpoint(
    request: Request, ref: str,
    data_class: str | None = Query(default=None, description="A data class's key, if asking"),
) -> dict[str, Any]:  # fmt: skip
    """Whether the application is approved for new use: in service and open to it, with a
    decision that keeps it, and nothing past its end of support; with ``data_class``,
    ``allowed`` says whether its record also says it handles that class. Every reason is
    given. A restricted application the asker may not see is answered 404."""
    principal = current(request)
    with reading(request) as session:
        return envelope(checkpoint.check(session, principal, ref, data_class))


class TokenBody(BaseModel):
    name: str = Field(max_length=80, description="What it is for, such as the system using it")
    role: str = Field(description="manager, architect, auditor, leader, steward, or member")
    org_unit_id: int | None = Field(default=None, description="The unit it is for, if any")
    read_only: bool = Field(default=True, description="Whether it may only read")
    expires_on: str | None = Field(default=None, description="YYYY-MM-DD; 90 days if none")


@router.get("/admin/tokens", summary="The API tokens, and when each was last used")
def list_tokens(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope({"tokens": tokens.listing(session, principal),
                         "roles": list(tokens.ROLES)})  # fmt: skip


@router.post("/admin/tokens", status_code=201, summary="Issue an API token")
def issue_token(request: Request, body: TokenBody) -> dict[str, Any]:
    """The token itself is in the answer, and never again: only its hash is kept."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, token = tokens.create(session, principal, body.model_dump())
        return envelope({**tokens.view(row, None, None), "token": token})


@router.delete("/admin/tokens/{token_id}", summary="Revoke an API token")
def revoke_token(request: Request, token_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        tokens.revoke(session, principal, token_id)
        return envelope({"tokens": tokens.listing(session, principal)})


class WebhookBody(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    url: str | None = Field(default=None, max_length=500, description="An https:// address")
    topics: list[str] | None = Field(default=None, description="What it is told of")
    active: bool | None = None


@router.get("/admin/webhooks", summary="The webhooks, and how their deliveries are going")
def list_webhooks(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope(webhooks.listing(session, principal))


@router.post("/admin/webhooks", status_code=201, summary="Add a webhook")
def add_webhook(request: Request, body: WebhookBody) -> dict[str, Any]:
    """Its signing secret is in the answer, and never again."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, secret = webhooks.create(session, principal, body.model_dump(exclude_none=True))
        return envelope({**webhooks.view(session, row), "secret": secret})


@router.patch("/admin/webhooks/{webhook_id}", summary="Change a webhook, or switch it off or on")
def change_webhook(request: Request, webhook_id: int, body: WebhookBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        row = webhooks.change(session, principal, webhooks.find(session, webhook_id),
                              body.model_dump(exclude_none=True))  # fmt: skip
        return envelope(webhooks.view(session, row))


@router.delete("/admin/webhooks/{webhook_id}", summary="Remove a webhook")
def remove_webhook(request: Request, webhook_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        webhooks.remove(session, principal, webhooks.find(session, webhook_id))
        return envelope(webhooks.listing(session, principal))


@router.post("/admin/webhooks/{webhook_id}/test", summary="Send a test delivery now")
def test_webhook(request: Request, webhook_id: int) -> dict[str, Any]:
    principal = current(request)
    send = getattr(request.app.state, "webhook_send", webhooks._post)
    return envelope({"result": webhooks.send_test(database(request), principal, webhook_id, send)})


class OwnTokenBody(BaseModel):
    name: str = Field(max_length=80, description="What it is for, such as an assistant")
    expires_on: str | None = Field(default=None, description="YYYY-MM-DD; 90 days if none")


@router.get("/tokens", summary="Your own API tokens")
def my_tokens(request: Request) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        return envelope({"tokens": tokens.mine(session, principal)})


@router.post("/tokens", status_code=201, summary="Make a token of your own")
def make_my_token(request: Request, body: OwnTokenBody) -> dict[str, Any]:
    """It acts as you: it reads what you may, and proposes changes for you to accept. The
    token is in the answer, and never again."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        row, token = tokens.create_personal(session, principal, body.model_dump())
        return envelope({**tokens.view(row, None, None), "token": token})


@router.delete("/tokens/{token_id}", summary="Revoke a token of your own")
def revoke_my_token(request: Request, token_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        tokens.revoke_mine(session, principal, token_id)
        return envelope({"tokens": tokens.mine(session, principal)})


class SuggestionBody(BaseModel):
    field: str = Field(max_length=60, description="The field, such as summary or users")
    value: Any = Field(description="The value proposed for it")
    note: str | None = Field(default=None, max_length=1000, description="Why")


@router.get("/applications/{ref}/suggestions", summary="Changes proposed to an application")
def list_suggestions(request: Request, ref: str) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        app = records.load(session, principal, APPLICATION, ref)
        return envelope(suggestions.of_application(session, principal, app))


@router.post("/applications/{ref}/suggestions", status_code=201, summary="Propose a change")
def propose_change(request: Request, ref: str, body: SuggestionBody) -> dict[str, Any]:
    """Nothing on the record changes: someone who keeps it accepts or dismisses it."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = suggestions.propose(session, principal, app, body.model_dump())
        return envelope(suggestions.view(row, suggestions._fields()))


@router.post("/suggestions/{suggestion_id}/accept", summary="Accept a proposed change")
def accept_suggestion(request: Request, suggestion_id: int) -> dict[str, Any]:
    """The change is made as yours, checked by the same rules as any edit."""
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = suggestions.accept(session, principal, suggestion_id)
        return envelope(suggestions.of_application(session, principal, app))


@router.post("/suggestions/{suggestion_id}/dismiss", summary="Dismiss a proposed change")
def dismiss_suggestion(request: Request, suggestion_id: int) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        app = suggestions.dismiss(session, principal, suggestion_id)
        return envelope(suggestions.of_application(session, principal, app))
