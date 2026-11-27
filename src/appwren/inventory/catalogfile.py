"""Catalog files: an application and its components described in a file kept beside their code,
in the common descriptor shape (documents with ``kind``, ``metadata``, and ``spec``), read with a
safe loader (INV-17).

A file is imported into one application, with a dry run first: a ``System`` document describes
the application, and each ``Component`` or ``Resource`` document one of its components, matched
by the reference AppWren wrote into it, or by name; one that matches none is added. Only what
the file says is changed, and nothing is removed, so importing the same file twice changes
nothing the second time. An application is exported in the same shape, with AppWren's
references in it, so the file can be kept in the repository and imported again.
"""

from __future__ import annotations

import re
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import Application, Component, OrgUnit
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION, COMPONENT
from appwren.program import vocab

API_VERSION = "appwren/v1"
REF = "appwren/ref"
MOST_BYTES = 1_000_000
MOST_DOCUMENTS = 200
# The common lifecycle words, and the stages they mean here; exported the other way.
LIFECYCLE_IN = {"production": "active", "experimental": "evaluating", "deprecated": "phase_out"}
LIFECYCLE_OUT = {
    "proposed": "experimental", "evaluating": "experimental", "phase_in": "experimental",
    "active": "production", "containment": "deprecated", "phase_out": "deprecated",
    "retired": "deprecated", "archived": "deprecated",
}  # fmt: skip
KIND_IN = {"service": "service", "website": "web_frontend", "library": "library",
           "database": "database", "pipeline": "pipeline", "job": "batch_job",
           "batch": "batch_job", "mobile-app": "mobile_app", "integration": "integration",
           "report": "report"}  # fmt: skip
KIND_OUT = {
    "service": "service", "web_frontend": "website", "library": "library",
    "database": "database", "pipeline": "pipeline", "batch_job": "job",
    "mobile_app": "mobile-app", "integration": "integration", "report": "report",
}  # fmt: skip
READ_KINDS = "only a System, a Component, or a Resource is read"
HOSTS = {"github.com/project-slug": "https://github.com/",
         "gitlab.com/project-slug": "https://gitlab.com/"}  # fmt: skip


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:63] or "unnamed"


def _read(text: str) -> list[dict[str, Any]]:
    if len(text.encode()) > MOST_BYTES:
        raise Invalid("The file was not read.", {"file": "Import at most 1 MB at a time."})
    try:
        documents = [doc for doc in yaml.safe_load_all(text) if doc is not None]
    except yaml.YAMLError as exc:
        where = getattr(exc, "problem_mark", None)
        line = f" at line {where.line + 1}" if where is not None else ""
        raise Invalid("The file was not read.", {"file": f"It is not YAML{line}."}) from exc
    if not documents or len(documents) > MOST_DOCUMENTS:
        raise Invalid("The file was not read.",
                      {"file": f"It should hold 1 to {MOST_DOCUMENTS} documents."})  # fmt: skip
    if not all(isinstance(doc, dict) for doc in documents):
        raise Invalid("The file was not read.", {"file": "Each document should be a mapping."})
    return documents


def _text(value: Any) -> str | None:
    return " ".join(str(value).split()) if isinstance(value, str | int | float) else None


def _links(metadata: dict[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    for link in metadata.get("links") or []:
        if not isinstance(link, dict) or not str(link.get("url", "")).startswith("https://"):
            continue
        kind = str(link.get("type") or link.get("title") or "").casefold()
        if kind in ("docs", "documentation", "runbook") and "docs_url" not in found:
            found["docs_url"] = str(link["url"])
        elif kind in ("home", "website", "homepage") and "home_url" not in found:
            found["home_url"] = str(link["url"])
        elif kind in ("source", "repository", "code") and "repo_url" not in found:
            found["repo_url"] = str(link["url"])
    return found


def _application_values(session: Session, doc: dict[str, Any]) -> dict[str, Any]:
    metadata, spec = doc.get("metadata") or {}, doc.get("spec") or {}
    notes = metadata.get("annotations") or {}
    values: dict[str, Any] = {}
    if _text(metadata.get("description")):
        values["summary"] = str(metadata["description"]).strip()
    if isinstance(metadata.get("tags"), list):
        values["tags"] = [str(tag)[:40] for tag in metadata["tags"]][:20]
    stage = notes.get("appwren/lifecycle") or LIFECYCLE_IN.get(str(spec.get("lifecycle", "")))
    if stage in vocab.keys(session, "lifecycle"):
        values["lifecycle"] = stage
    links = _links(metadata)
    values.update({key: links[key] for key in ("docs_url", "home_url") if key in links})
    return values


def _component_values(session: Session, doc: dict[str, Any]) -> dict[str, Any]:
    metadata, spec = doc.get("metadata") or {}, doc.get("spec") or {}
    notes = metadata.get("annotations") or {}
    values: dict[str, Any] = {"name": _text(metadata.get("title")) or _text(metadata.get("name"))}
    kinds = vocab.keys(session, "component_kinds")
    kind = notes.get("appwren/kind") or KIND_IN.get(str(spec.get("type", "")).casefold())
    if kind not in kinds and str(doc.get("kind")) == "Resource":
        kind = "database" if "database" in kinds else None
    if kind in kinds:
        values["kind"] = kind
    if _text(metadata.get("description")):
        values["summary"] = str(metadata["description"]).strip()
    repo = next((HOSTS[key] + str(notes[key]).strip("/") for key in HOSTS if notes.get(key)),
                None) or _links(metadata).get("repo_url")  # fmt: skip
    if repo:
        values["repo_url"] = repo
    return values


def _changes(record: Any, values: dict[str, Any], labels: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for field, wanted in values.items():
        have = getattr(record, field)
        if field == "tags":
            have = list(have or [])
        if have != wanted:
            out.append({"field": field, "label": labels.get(field, field), "from": have,
                        "to": wanted})  # fmt: skip
    return out


def _labels(record_type: Any) -> dict[str, str]:
    return {spec.name: spec.label for spec in record_type.fields} | {"name": "Name",
                                                                      "summary": "Summary",
                                                                      "tags": "Tags"}  # fmt: skip


def import_file(
    session: Session, principal: Principal, application: Application, text: str
) -> dict[str, Any]:
    """Bring a catalog file into an application and its components. The caller rolls back a
    dry run; what this returns is the same either way."""
    if not access.can_edit(session, principal, APPLICATION, application):
        raise PermissionDenied("Only someone who keeps this application imports into it.")
    documents = _read(text)
    report: dict[str, Any] = {"application": {"ref": application.ref, "changes": []},
                              "components": [], "ignored": []}  # fmt: skip
    systems = [doc for doc in documents if doc.get("kind") == "System"]
    if len(systems) > 1:
        raise Invalid("The file was not read.", {"file": "It describes more than one system."})
    if systems:
        wanted = _application_values(session, systems[0])
        changes = _changes(application, wanted, _labels(APPLICATION))
        if changes:
            records.update(session, principal, APPLICATION, application,
                           {c["field"]: c["to"] for c in changes},
                           version=application.version)  # fmt: skip
        report["application"]["changes"] = changes
    ours = session.scalars(
        select(Component).where(Component.application_id == application.id)
    ).all()
    by_ref = {row.ref: row for row in ours}
    by_name = {}
    for row in ours:
        by_name.setdefault(row.name.casefold(), row)
        by_name.setdefault(slug(row.name), row)
    labels = _labels(COMPONENT)
    for doc in documents:
        kind = doc.get("kind")
        metadata = doc.get("metadata") or {}
        if kind == "System":
            continue
        if kind not in ("Component", "Resource"):
            what = f"{kind or 'A document'} {metadata.get('name', '')}".strip()
            report["ignored"].append({"what": what, "why": READ_KINDS})
            continue
        values = _component_values(session, doc)
        if not values.get("name"):
            report["ignored"].append({"what": f"A {kind}", "why": "it has no name"})
            continue
        ref = (metadata.get("annotations") or {}).get(REF)
        name = str(metadata.get("name") or "")
        row = by_ref.get(str(ref)) if ref else None
        row = row or by_name.get(values["name"].casefold()) or by_name.get(slug(name))
        if row is None:
            values.setdefault("kind", "module")
            created = records.create(session, principal, COMPONENT,
                                     {**values, "application_id": application.ref})  # fmt: skip
            by_name[created.name.casefold()] = created
            report["components"].append({"name": created.name, "ref": None, "action": "add",
                                         "changes": []})  # fmt: skip
            continue
        values.pop("name")  # matched: its name here is the one people chose
        changes = _changes(row, values, labels)
        if changes:
            records.update(session, principal, COMPONENT, row,
                           {c["field"]: c["to"] for c in changes}, version=row.version)  # fmt: skip
        report["components"].append({"name": row.name, "ref": row.ref,
                                     "action": "change" if changes else "same",
                                     "changes": changes})  # fmt: skip
    report["changed"] = bool(report["application"]["changes"]) or any(
        item["action"] != "same" for item in report["components"]
    )
    return report


def export_file(session: Session, principal: Principal, application: Application) -> str:
    """The application and its components as a catalog file, AppWren's references in it."""
    name = slug(application.name)
    unit = session.get(OrgUnit, application.org_unit_id) if application.org_unit_id else None
    links = [{"url": url, "title": title, "type": kind}
             for url, title, kind in ((application.docs_url, "Documentation", "docs"),
                                      (application.home_url, "Home", "home")) if url]  # fmt: skip
    system: dict[str, Any] = {
        "apiVersion": API_VERSION,
        "kind": "System",
        "metadata": {
            "name": name, "title": application.name,
            **({"description": application.summary} if application.summary else {}),
            **({"tags": list(application.tags)} if application.tags else {}),
            "annotations": {REF: application.ref, "appwren/lifecycle": application.lifecycle},
            **({"links": links} if links else {}),
        },
        "spec": {"owner": unit.name if unit else "unknown",
                 "lifecycle": LIFECYCLE_OUT.get(application.lifecycle, "production")},
    }  # fmt: skip
    documents = [system]
    parts = session.scalars(
        select(Component)
        .where(Component.application_id == application.id, Component.status == "active")
        .order_by(Component.ref)
    )
    for part in parts:
        notes: dict[str, Any] = {REF: part.ref, "appwren/kind": part.kind}
        for key, base in HOSTS.items():
            if part.repo_url and part.repo_url.startswith(base):
                notes[key] = part.repo_url[len(base) :].strip("/")
        documents.append({
            "apiVersion": API_VERSION,
            "kind": "Resource" if part.kind == "database" else "Component",
            "metadata": {
                "name": slug(part.name), "title": part.name,
                **({"description": part.summary} if part.summary else {}),
                "annotations": notes,
                **({"links": [{"url": part.repo_url, "title": "Repository", "type": "source"}]}
                   if part.repo_url else {}),
            },
            "spec": {"type": KIND_OUT.get(part.kind, part.kind),
                     "lifecycle": LIFECYCLE_OUT.get(application.lifecycle, "production"),
                     "owner": unit.name if unit else "unknown", "system": name},
        })  # fmt: skip
    return yaml.safe_dump_all(documents, sort_keys=False, allow_unicode=True, width=100)
