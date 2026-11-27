"""Shaping the program in the app: vocabularies, the organization's own fields, the question
bank, and the scoring model with its cadence (CUR-09).

Each part is checked whole by the same rules a program pack is, and saved by the same means,
so the app and a pack can never disagree about what is allowed. A change to the scoring model
is previewed first: every application in service is scored under the model as it is and as it
would be, and those whose scores, recommendation, or flags would differ are listed. The
preview changes nothing. Publishing makes a new version, and the applications whose scores it
changes are exactly the ones the preview listed, since both are worked out by one engine.

Some vocabularies are lists the software gives meaning to: a lifecycle stage of *retired*,
a disposition of *consolidate*, a funding kind of *grant*. Those may be renamed, described,
and reordered, never added to or taken from. The rest may also gain values, and retire them;
a value is never removed, because records keep it.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren import assessment
from appwren.access.principal import Principal
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import Application
from appwren.events import audit
from appwren.inventory.registry import APPLICATION
from appwren.program import catalog, packs, settings, vocab

# The lists AppWren's own rules read by key: renamed and reordered, never added to or emptied.
FIXED = frozenset(
    {"lifecycle", "sourcing", "purpose", "pace", "tiers", "funding", "data_classes",
     "dispositions", "radar", "application_roles", "agreement_states", "environments",
     "link_kinds", "sign_in", "monitoring", "backup", "hosting"}
)  # fmt: skip
KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
NOT_IN_SERVICE = ("retired", "archived")


def _no(message: str, field: str, text: str) -> Invalid:
    return Invalid(message, {field: text})


def _require(principal: Principal) -> None:
    if not principal.configures:
        raise PermissionDenied("Only a manager for the whole organization, or an administrator, "
                               "shapes the program.")  # fmt: skip


def current(session: Session) -> dict[str, Any]:
    """The program as it stands, with what may be changed in each part."""
    exported = packs.export(session)
    model = assessment.current_model(session)
    bank = assessment.current_questionnaire(session)
    return {
        "vocabularies": exported["vocabularies"],
        "fixed": sorted(FIXED),
        "fields": exported["fields"],
        "sensitive_fields": exported["sensitive_fields"],
        "decision_rules": exported["decision_rules"],
        "field_types": list(catalog.FIELD_TYPES),
        "sections": list(catalog.SECTIONS),
        "questionnaire": {"version": bank.version, "definition": bank.definition},
        "scoring": {"version": model.version, "definition": model.definition,
                    "published_at": model.published_at, "published_by": model.published_by},
    }  # fmt: skip


def _pack_problems(part: str, value: Any) -> list[str]:
    return packs.check({"pack": {"kind": "program"}, part: value})


# --- Vocabularies ---------------------------------------------------------------------------


def save_vocabulary(
    session: Session, principal: Principal, name: str, items: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    _require(principal)
    if name not in vocab.NAMES:
        raise Invalid("There is no such vocabulary.", {"name": name})
    have = vocab.get(session, name)
    old_keys = [item["key"] for item in have]
    cleaned: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("key") or "").strip()
        label = " ".join(str(item.get("label") or "").split())
        if key not in old_keys:
            if name in FIXED:
                raise Invalid("The list was not saved.",
                              {"items": f"Values cannot be added to {name}: AppWren's rules read "
                                        "its keys."})  # fmt: skip
            if not KEY.fullmatch(key):
                key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40]
                if not KEY.fullmatch(key or ""):
                    raise _no("The list was not saved.", "items",
                              f"Give “{label}” a label that starts with a letter.")  # fmt: skip
        if not label:
            raise Invalid("The list was not saved.", {"items": "Every value needs a label."})
        before = next((each for each in have if each["key"] == key), {})
        kept = {**before, **{k: v for k, v in item.items() if k not in ("key", "label")},
                "key": key, "label": label[:120]}  # fmt: skip
        if name in FIXED:
            kept.pop("retired", None)  # what the rules read stays offered
        elif not kept.get("retired"):
            kept.pop("retired", None)
        cleaned.append(kept)
    keys = [each["key"] for each in cleaned]
    if len(set(keys)) != len(keys):
        raise Invalid("The list was not saved.", {"items": "Two values have the same key."})
    missing = [key for key in old_keys if key not in keys]
    if missing:
        raise _no("The list was not saved.", "items",
                  f"{missing[0]} is in use and cannot be removed. Retire it.")  # fmt: skip
    if not any(not each.get("retired") for each in cleaned):
        raise Invalid("The list was not saved.", {"items": "Keep at least one value offered."})
    problems = _pack_problems("vocabularies", {name: cleaned})
    if problems:
        raise Invalid("The list was not saved.", {"items": " ".join(problems)})
    with audit.operation(session, "program.vocabulary"):
        vocab.put(session, name, cleaned)
    return vocab.get(session, name)


# --- The organization's own fields --------------------------------------------------------


def save_fields(
    session: Session,
    principal: Principal,
    fields: list[Mapping[str, Any]],
    sensitive: list[str] | None = None,
) -> dict[str, Any]:
    _require(principal)
    have = {item["key"] for item in catalog.fields(session)}
    given = [dict(item) for item in fields]
    gone = have - {str(item.get("key")) for item in given}
    if gone:
        raise _no("The fields were not saved.", "fields",
                  f"The field {sorted(gone)[0]} holds values and cannot be removed.")  # fmt: skip
    problems = _pack_problems("fields", given)
    if sensitive is not None:
        names = (
            {field.name for field in APPLICATION.fields}
            | packs.HEADER
            | {str(item.get("key")) for item in given}
        )
        problems += [f"{name} cannot be sensitive: it is not a field." for name in sensitive
                     if name not in names]  # fmt: skip
    if problems:
        raise Invalid("The fields were not saved.", {"fields": " ".join(problems)})
    with audit.operation(session, "program.fields"):
        settings.put(session, catalog.FIELDS, copy.deepcopy(given))
        if sensitive is not None:
            settings.put(session, catalog.SENSITIVE, list(dict.fromkeys(sensitive)))
    return {
        "fields": catalog.fields(session),
        "sensitive_fields": catalog.sensitive_fields(session),
    }


# --- Who may decide -----------------------------------------------------------------------


def save_decision_rules(
    session: Session, principal: Principal, values: Mapping[str, Any]
) -> dict[str, bool]:
    """Whether an application's own accountable owner may record its decision, where they are
    also a manager or a leader over it. For a team too small for anyone else to; each such
    decision is marked as the owner's own."""
    _require(principal)
    rules = {"owners_may_decide": values.get("owners_may_decide")}
    problems = catalog.check_decision_rules(rules)
    if problems:
        raise Invalid("The setting was not saved.", {"owners_may_decide": " ".join(problems)})
    with audit.operation(session, "program.decision_rules"):
        settings.put(session, catalog.DECISION_RULES, rules)
    return catalog.decision_rules(session)


# --- The question bank --------------------------------------------------------------------


def _questions(definition: Mapping[str, Any]) -> dict[str, str]:
    return {
        question["key"]: question.get("dimension", "")
        for section in definition.get("sections") or []
        for question in section.get("questions") or []
    }


def save_questionnaire(
    session: Session, principal: Principal, definition: Mapping[str, Any]
) -> dict[str, Any]:
    """The wording of the questions and their levels. Which questions there are, and which
    score each answers, is the scoring model's to say and is changed with a pack."""
    _require(principal)
    bank = assessment.current_questionnaire(session).definition
    if _questions(definition) != _questions(bank):
        raise Invalid("The questions were not published.",
                      {"questionnaire": "Change the wording here. Adding or removing a question, "
                                        "or moving it to another score, is done with a program "
                                        "pack, together with the scoring model."})  # fmt: skip
    for section in definition.get("sections") or []:
        for question in section.get("questions") or []:
            if len(question.get("levels") or []) != 5 or not all(
                str(level).strip() for level in question["levels"]
            ):
                raise Invalid("The questions were not published.",
                              {"questionnaire": f"Each of the five levels of {question['key']} "
                                                "needs words."})  # fmt: skip
    row = assessment.publish_questionnaire(session, dict(definition), principal.name)
    current = assessment.current_questionnaire(session)
    return {"version": current.version, "changed": row is not None}


# --- The scoring model --------------------------------------------------------------------


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scores": dict(result["scores"]),
        "confidence": result["confidence"],
        "recommendation": result["recommendation"],
        "flags": sorted(flag["key"] for flag in result["flags"]),
    }


def impact(session: Session, definition: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every application in service whose scores, confidence, recommendation, or flags would
    be different under this model."""
    apps = list(
        session.scalars(
            select(Application).where(
                Application.status == "active", Application.lifecycle.not_in(NOT_IN_SERVICE)
            )
        )
    )
    if not apps:
        return []
    before = assessment.score_all(session, apps)
    after = assessment.score_all(session, apps, definition=definition)
    changed = []
    for app in sorted(apps, key=lambda each: each.name):
        was, will = _summary(before[app.id]), _summary(after[app.id])
        if was == will:
            continue
        what = []
        for key, value in will["scores"].items():
            if value != was["scores"].get(key):
                what.append({"what": key, "from": was["scores"].get(key), "to": value})
        for key in ("confidence", "recommendation"):
            if will[key] != was[key]:
                what.append({"what": key, "from": was[key], "to": will[key]})
        if will["flags"] != was["flags"]:
            what.append({"what": "flags", "from": was["flags"], "to": will["flags"]})
        changed.append(
            {"application": {"ref": app.ref, "name": app.name, "type": "application"},
             "changes": what}
        )  # fmt: skip
    return changed


def _check_model(session: Session, definition: Any) -> None:
    bank = assessment.current_questionnaire(session).definition
    problems = assessment.problems(definition, assessment.question_keys(bank))
    if problems:
        raise Invalid("The scoring model is not valid.", {"scoring": " ".join(problems)})


def preview_model(
    session: Session, principal: Principal, definition: Mapping[str, Any]
) -> dict[str, Any]:
    _require(principal)
    _check_model(session, definition)
    changed = impact(session, definition)
    same = definition == assessment.current_model(session).definition
    return {"changed": changed, "count": len(changed), "same": same}


def publish_model(
    session: Session, principal: Principal, definition: Mapping[str, Any]
) -> dict[str, Any]:
    """Publish a new version of the scoring model. What it changes is worked out first, by
    the same function the preview uses."""
    _require(principal)
    _check_model(session, definition)
    changed = impact(session, definition)
    row = assessment.publish_model(session, dict(definition), principal.name)
    current = assessment.current_model(session)
    return {"version": current.version, "published": row is not None, "changed": changed,
            "count": len(changed)}  # fmt: skip
