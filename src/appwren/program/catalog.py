"""What the program says about applications beyond the vocabularies: the organization's own
fields, what each lifecycle stage requires, which fields are sensitive, and what counts as an
application at all (ADR-0007).

Each starts from the default program pack and is kept as a setting once an organization
changes it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from appwren.program import settings, vocab

FIELDS = "program.fields"
STAGES = "program.stage_requirements"
SENSITIVE = "program.sensitive_fields"
DEFINITION = "program.definition"

FIELD_TYPES = ("text", "long", "number", "date", "bool", "url", "choice")
SECTIONS = ("about", "source", "use", "support", "security", "operations", "cost", "research",
            "lifecycle")  # fmt: skip
# What a stage may require besides fields of the application itself.
SPECIAL = ("accountable", "capabilities", "components", "technologies", "assessment", "decision")
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")


def _get(session: Session, key: str, name: str) -> Any:
    stored = settings.get(session, key, None)
    return stored if stored is not None else vocab.default_pack()[name]


def fields(session: Session) -> list[dict[str, Any]]:
    """The organization's own fields for applications."""
    return list(_get(session, FIELDS, "fields"))


def stage_requirements(session: Session) -> dict[str, list[str]]:
    return dict(_get(session, STAGES, "stage_requirements"))


def sensitive_fields(session: Session) -> list[str]:
    return list(_get(session, SENSITIVE, "sensitive_fields"))


def definition(session: Session) -> dict[str, Any]:
    return dict(_get(session, DEFINITION, "definition"))


def check_fields(items: Any, builtin: set[str]) -> list[str]:
    """Everything wrong with a list of field definitions, in one pass."""
    found: list[str] = []
    if not isinstance(items, list):
        return ["The organization's fields must be a list."]
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"Field {index + 1}"
        if not isinstance(item, Mapping):
            found.append(f"{where} is not a definition.")
            continue
        key = str(item.get("key", ""))
        if not KEY.fullmatch(key):
            found.append(f"{where} needs a key of lower-case letters, digits, and underscores.")
        elif key in seen:
            found.append(f"The field {key} appears twice.")
        elif key in builtin:
            found.append(f"The field {key} has the name of one AppWren already has.")
        seen.add(key)
        if not str(item.get("label", "")).strip():
            found.append(f"{where} needs a label.")
        if item.get("type") not in FIELD_TYPES:
            found.append(f"{where} must be one of: {', '.join(FIELD_TYPES)}.")
        if item.get("section", "about") not in SECTIONS:
            found.append(f"{where} must be in one of the sections: {', '.join(SECTIONS)}.")
        if item.get("type") == "choice":
            options = item.get("options")
            if (
                not isinstance(options, list)
                or not options
                or not all(isinstance(option, list) and len(option) == 2 for option in options)
            ):
                found.append(f"{where} is a choice and needs options, each a key and a label.")
    return found


def check_stages(value: Any, field_names: set[str]) -> list[str]:
    found: list[str] = []
    if not isinstance(value, Mapping):
        return ["The stage requirements must name each stage."]
    for stage, needs in value.items():
        if not isinstance(needs, list):
            found.append(f"The requirements of {stage} must be a list.")
            continue
        for name in needs:
            if name not in field_names and name not in SPECIAL:
                found.append(f"{stage} requires {name}, which is not a field.")
    return found


def clean_values(
    session: Session, sourcing: str | None, given: Any, current: Mapping[str, Any] | None
) -> tuple[dict[str, Any], dict[str, str]]:
    """The values of the organization's own fields, checked against their definitions.
    Returns the values to keep and any errors, keyed ``fields.<key>``."""
    errors: dict[str, str] = {}
    out = dict(current or {})
    if given is None:
        return out, errors
    if not isinstance(given, Mapping):
        return out, {"fields": "Give the organization's fields as a set of values."}
    known = {item["key"]: item for item in fields(session)}
    for key, value in given.items():
        where = f"fields.{key}"
        spec = known.get(key)
        if spec is None:
            errors[where] = "There is no such field."
            continue
        if value in (None, ""):
            out.pop(key, None)
            continue
        applies = spec.get("applies_to")
        if applies and sourcing not in applies:
            errors[where] = "This field does not apply to applications sourced this way."
            continue
        kind = spec["type"]
        if kind in ("text", "long"):
            text = str(value).strip()
            limit = 200 if kind == "text" else 4000
            if len(text) > limit:
                errors[where] = f"Keep this to {limit} characters."
                continue
            out[key] = text
        elif kind == "number":
            try:
                out[key] = float(value) if "." in str(value) else int(str(value))
            except ValueError:
                errors[where] = "Give a number."
        elif kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
                errors[where] = "Give a date as YYYY-MM-DD."
            else:
                out[key] = str(value)
        elif kind == "bool":
            if not isinstance(value, bool):
                errors[where] = "Answer yes or no."
            else:
                out[key] = value
        elif kind == "url":
            text = str(value).strip()
            if not text.lower().startswith(("https://", "http://")):
                errors[where] = "Start the address with https://"
            else:
                out[key] = text[:300]
        elif kind == "choice":
            options = [option[0] for option in spec.get("options", [])]
            if value not in options:
                errors[where] = f"{value!r} is not one of the choices."
            else:
                out[key] = value
    return out, errors
