"""Catalog files: an application and its components, imported from a file kept beside their
code, with a dry run, and exported as one (INV-17)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from appwren.access.policy import current
from appwren.api.common import envelope, reading
from appwren.core.errors import Invalid
from appwren.inventory import catalogfile, records
from appwren.inventory.registry import APPLICATION

router = APIRouter(prefix="/api/v1", tags=["catalog files"])
YAML = "application/yaml"


@router.get(
    "/applications/{ref}/catalog",
    summary="An application and its components, as a catalog file",
    response_class=Response,
    responses={200: {"content": {YAML: {}}}},
)
def export_catalog(request: Request, ref: str) -> Response:
    principal = current(request)
    with reading(request) as session:
        application = records.load(session, principal, APPLICATION, ref)
        text = catalogfile.export_file(session, principal, application)
    name = f"{catalogfile.slug(application.name)}.catalog-info.yaml"
    return Response(content=text.encode("utf-8"), media_type=YAML, headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="{name}"',
    })  # fmt: skip


@router.post(
    "/applications/{ref}/catalog",
    summary="Bring a catalog file into an application and its components",
    openapi_extra={"requestBody": {"content": {YAML: {"schema": {"type": "string"}}}}},
)
async def import_catalog(
    request: Request, ref: str,
    dry_run: bool = Query(default=True, description="Say what would change, and keep nothing"),
) -> dict[str, Any]:  # fmt: skip
    """Send the file as the request body. Only what it says is changed; nothing is removed."""
    principal = current(request)
    body = await request.body()
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid("The file was not read.", {"file": "Save it as UTF-8."}) from exc

    def run() -> dict[str, Any]:
        db = request.app.state.db
        with db.write(principal.actor, action="application.catalog_import") as session:
            application = records.load(session, principal, APPLICATION, ref)
            report = catalogfile.import_file(session, principal, application, text)
            if dry_run:
                session.rollback()  # a dry run changes nothing
        return {**report, "dry_run": dry_run}

    return envelope(await run_in_threadpool(run))
