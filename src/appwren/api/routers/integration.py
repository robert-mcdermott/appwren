"""What other systems use: API tokens an administrator issues, and webhooks (INT-02, INT-03)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from appwren.access.policy import current
from appwren.api.common import database, envelope, reading, writing
from appwren.integration import tokens, webhooks

router = APIRouter(prefix="/api/v1", tags=["integration"])


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
