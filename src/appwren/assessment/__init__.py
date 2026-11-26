"""Assessments, and scores worked out from what is known (SCR-01 to SCR-10).

This module gathers the facts the engine reads, for one application or the whole portfolio
in a few queries; asks the engine; and keeps the results it is asked to keep as snapshots.
Scores between snapshots are worked out when they are read and never stored.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import add_months, utc_now
from appwren.core.clock import today as today_
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import (
    Account,
    Application,
    ApplicationCapability,
    Assessment,
    Capability,
    Component,
    ComponentTechnology,
    Questionnaire,
    RecordLink,
    RecordOwner,
    ScoreSnapshot,
    ScoringModel,
    Technology,
    TechnologyRelease,
)
from appwren.db.models.inventory import ACCOUNTABLE
from appwren.db.refs import next_ref
from appwren.engine import evaluate, months_current, problems
from appwren.events import audit
from appwren.inventory import access, applications
from appwren.inventory.registry import APPLICATION
from appwren.program import catalog, vocab

VENDOR_SOURCED = ("saas", "commercial", "vendor_custom")
# Later slices add facts of their own (the decision on record): each takes the session and
# the applications and returns each one's extra facts by id.
EXTRA_FACTS: list[Callable[[Session, list[Application]], dict[int, dict[str, Any]]]] = []
# Facts a sensitive field feeds, and the computed factors that reveal them.
REVEALS = {
    "sign_in": {"security", "data_exposure"},
    "backup": {"continuity"},
    "last_restore_test": {"continuity"},
    "annual_cost": {"annual_cost"},
}


# --- The question bank and the scoring model, in versions ---------------------------------


def current_questionnaire(session: Session) -> Questionnaire:
    row = session.scalars(select(Questionnaire).where(Questionnaire.status == "current")).first()
    if row is None:
        raise Invalid("There is no question bank yet: run `appwren db upgrade`.")
    return row


def current_model(session: Session) -> ScoringModel:
    row = session.scalars(select(ScoringModel).where(ScoringModel.status == "current")).first()
    if row is None:
        raise Invalid("There is no scoring model yet: run `appwren db upgrade`.")
    return row


def question_keys(definition: Mapping[str, Any]) -> set[str]:
    return {q["key"] for s in definition.get("sections", []) for q in s.get("questions", [])}


def questions(definition: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {q["key"]: q for s in definition.get("sections", []) for q in s.get("questions", [])}


def check_questionnaire(definition: Any) -> list[str]:
    found: list[str] = []
    if not isinstance(definition, Mapping) or not isinstance(definition.get("sections"), list):
        return ["The question bank must be a list of sections."]
    seen: set[str] = set()
    for section in definition["sections"]:
        for item in section.get("questions", []):
            key = item.get("key")
            if not key or key in seen:
                found.append(f"Every question needs a key of its own ({key!r}).")
            seen.add(key)
            levels = item.get("levels")
            if not isinstance(levels, list) or len(levels) != 5 or not all(levels):
                found.append(f"The question {key} needs a definition for each of its five levels.")
            if item.get("dimension") not in (
                "business_value", "technical_health", "cost_burden", "risk_exposure",
            ):  # fmt: skip
                found.append(f"The question {key} must serve one of the four dimensions.")
    return found


def _publish(session: Session, model: type, definition: dict[str, Any], by: str) -> Any:
    rows = session.scalars(select(model).order_by(model.version.desc())).all()
    if rows and rows[0].definition == definition:
        return None
    for row in rows:
        if row.status == "current":
            row.status = "superseded"
    row = model(
        version=(rows[0].version + 1) if rows else 1,
        status="current",
        definition=copy.deepcopy(definition),
        published_at=utc_now(),
        published_by=by,
    )
    session.add(row)
    session.flush()
    return row


def publish_questionnaire(session: Session, definition: dict[str, Any], by: str) -> Any:
    """A new version of the question bank, unless it is the same as the current one."""
    found = check_questionnaire(definition)
    if found:
        raise Invalid("The question bank was not published.", {"questionnaire": " ".join(found)})
    with audit.operation(session, "program.questionnaire"):
        return _publish(session, Questionnaire, definition, by)


def publish_model(session: Session, definition: dict[str, Any], by: str) -> Any:
    """A new version of the scoring model, unless it is the same as the current one. A
    version once used is never changed: this always adds."""
    bank = current_questionnaire(session).definition
    found = problems(definition, question_keys(bank))
    if found:
        raise Invalid("The scoring model was not published.", {"scoring": " ".join(found)})
    with audit.operation(session, "program.scoring"):
        return _publish(session, ScoringModel, definition, by)


# --- Assessments -----------------------------------------------------------------------------


def latest(session: Session, application_ids: Iterable[int]) -> dict[int, Assessment]:
    ids = list(application_ids)
    if not ids:
        return {}
    rows = session.scalars(
        select(Assessment).where(
            Assessment.application_id.in_(ids), Assessment.superseded_by.is_(None)
        )
    )
    return {row.application_id: row for row in rows}


def is_current(row: Assessment, tier: str | None, model: Mapping[str, Any], on: date) -> bool:
    months = months_current(model, int(tier) if tier else None)
    return add_months(row.assessed_on, months) >= on


def clean_answers(bank: Mapping[str, Any], given: Any) -> dict[str, dict[str, Any]]:
    """Answers checked against the question bank: each a level from 1 to 5, or null for
    *don't know*, with an optional note."""
    known = questions(bank)
    if not isinstance(given, Mapping):
        raise Invalid("The answers were not saved.", {"answers": "Give the answers by question."})
    errors: dict[str, str] = {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in given.items():
        if key not in known:
            errors[f"answers.{key}"] = "There is no such question."
            continue
        if isinstance(value, Mapping):
            level, note = value.get("level"), value.get("note")
        else:
            level, note = value, None
        if level is not None and (isinstance(level, bool) or level not in (1, 2, 3, 4, 5)):
            errors[f"answers.{key}"] = "Choose a level from 1 to 5, or Don't know."
            continue
        note = str(note).strip()[:1000] if note else None
        out[key] = {"level": level, "note": note}
    if errors:
        raise Invalid("The answers were not saved.", errors)
    return out


def record(
    session: Session,
    principal: Principal,
    application: Application,
    given: Any,
    *,
    note: str | None = None,
    on: date | None = None,
) -> Assessment:
    """Answer the question bank for an application. The new assessment supersedes the last."""
    if not access.can_assess(session, principal, application):
        raise PermissionDenied("You cannot assess this application.")
    bank = current_questionnaire(session)
    answers = clean_answers(bank.definition, given)
    if not any(item["level"] is not None for item in answers.values()):
        raise Invalid("The answers were not saved.", {"answers": "Answer at least one question."})
    previous = latest(session, [application.id]).get(application.id)
    with audit.operation(session, "assessment.record"):
        row = Assessment(
            ref=next_ref(session, "ASM"),
            application_id=application.id,
            questionnaire_id=bank.id,
            answers=answers,
            note=(note or "").strip()[:2000] or None,
            assessed_by=principal.account_id,
            assessed_by_name=principal.name,
            assessed_on=on or today_(),
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        if previous is not None:
            previous.superseded_by = row.id
    return row


def view(row: Assessment, bank: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ref": row.ref,
        "answers": row.answers,
        "note": row.note,
        "assessed_by": row.assessed_by_name,
        "assessed_on": row.assessed_on,
        "superseded": row.superseded_by is not None,
        "questionnaire_id": row.questionnaire_id,
    }


def history(session: Session, application: Application) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Assessment)
        .where(Assessment.application_id == application.id)
        .order_by(Assessment.id.desc())
    ).all()
    return [view(row) for row in rows]


# --- Facts -----------------------------------------------------------------------------------


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month - (end.day < start.day)


def gather(
    session: Session, apps: list[Application], model: Mapping[str, Any], on: date
) -> dict[int, dict[str, Any]]:
    """The facts the engine reads, for each application, in a handful of queries."""
    ids = [app.id for app in apps]
    if not ids:
        return {}
    accountable = set(
        session.scalars(
            select(RecordOwner.record_id)
            .join(Account, Account.id == RecordOwner.account_id)
            .where(
                RecordOwner.record_type == "application",
                RecordOwner.record_id.in_(ids),
                RecordOwner.kind == ACCOUNTABLE,
                Account.status != "disabled",
            )
        )
    )
    components: dict[int, int] = defaultdict(int)
    for app_id in session.scalars(
        select(Component.application_id).where(
            Component.application_id.in_(ids), Component.status == "active"
        )
    ):
        components[app_id] += 1
    technologies: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for app_id, tech, release in session.execute(
        select(Component.application_id, Technology, TechnologyRelease)
        .join(ComponentTechnology, ComponentTechnology.component_id == Component.id)
        .join(Technology, Technology.id == ComponentTechnology.technology_id)
        .outerjoin(TechnologyRelease, TechnologyRelease.id == ComponentTechnology.release_id)
        .where(Component.application_id.in_(ids), Component.status == "active")
    ):
        technologies[app_id].append(
            {"name": tech.name, "ref": tech.ref, "radar": tech.radar,
             "release": release.cycle if release else None,
             "support_ends": release.support_ends if release else None,
             "extended_ends": release.extended_ends if release else None}
        )  # fmt: skip
    links = session.execute(
        select(ApplicationCapability.application_id, ApplicationCapability.capability_id,
               ApplicationCapability.is_primary)
        .where(ApplicationCapability.application_id.in_(ids))
    ).all()  # fmt: skip
    capability_ids = {row[1] for row in links}
    serving: dict[int, list[tuple[int, bool]]] = defaultdict(list)
    names: dict[int, tuple[str, str]] = {}
    if capability_ids:
        for cap_id, app_id, primary in session.execute(
            select(ApplicationCapability.capability_id, ApplicationCapability.application_id,
                   ApplicationCapability.is_primary)
            .join(Application, Application.id == ApplicationCapability.application_id)
            .where(ApplicationCapability.capability_id.in_(capability_ids),
                   Application.status == "active")
        ):  # fmt: skip
            serving[cap_id].append((app_id, primary))
        names = {
            row.id: (row.ref, row.name)
            for row in session.scalars(select(Capability).where(Capability.id.in_(capability_ids)))
        }
    capabilities: dict[int, list[dict[str, Any]]] = defaultdict(list)
    peers: dict[int, int] = {}
    for app_id, cap_id, is_primary in links:
        others = [(other, primary) for other, primary in serving[cap_id] if other != app_id]
        primary_of = next((other for other, primary in others if primary), None)
        ref, name = names.get(cap_id, ("", ""))
        capabilities[app_id].append(
            {"ref": ref, "name": name, "others": len(others),
             "primary": "self" if is_primary else ("other" if primary_of else None)}
        )  # fmt: skip
        if primary_of is not None and app_id not in peers:
            peers[app_id] = primary_of
    primaries = {app_id for app_id, _, is_primary in links if is_primary}
    peers = {app_id: peer for app_id, peer in peers.items() if app_id not in primaries}
    dependents: dict[int, int] = defaultdict(int)
    for target in session.scalars(
        select(RecordLink.to_id)
        .join(Application, Application.id == RecordLink.from_id)
        .where(
            RecordLink.from_type == "application",
            RecordLink.to_type == "application",
            RecordLink.relation == "depends_on",
            RecordLink.to_id.in_(ids),
            Application.status == "active",
        )
    ):
        dependents[target] += 1
    assessments = latest(session, ids)
    extra: dict[int, dict[str, Any]] = defaultdict(dict)
    for gatherer in EXTRA_FACTS:
        for app_id, found in gatherer(session, apps).items():
            extra[app_id].update(found)
    out: dict[int, dict[str, Any]] = {}
    for app in apps:
        assessed = assessments.get(app.id)
        current = assessed is not None and is_current(assessed, app.tier, model, on)
        started = app.go_live or app.created_at.date()
        out[app.id] = {
            "lifecycle": app.lifecycle,
            "sourcing": app.sourcing,
            "vendor_sourced": app.sourcing in VENDOR_SOURCED,
            "purpose": app.purpose,
            "pace": app.pace,
            "domain": app.domain,
            "tier": int(app.tier) if app.tier else None,
            "users": app.users,
            "maintainers": app.maintainers,
            "annual_cost": app.annual_cost,
            "sign_in": app.sign_in,
            "monitoring": app.monitoring,
            "backup": app.backup,
            "last_restore_test": app.last_restore_test,
            "data_classes": app.data_classes or [],
            "sensitivity": app.sensitivity,
            "funding": app.funding,
            "grant_ends_in_days": (app.grant_end - on).days if app.grant_end else None,
            "research_continuity": app.research_continuity,
            "regulated_record": app.regulated_record,
            "records_retention": app.records_retention,
            "external_users": app.external_users,
            "age_months": max(0, _months_between(started, on)),
            "accountable": app.id in accountable,
            "has_components": components.get(app.id, 0) > 0,
            "technologies": technologies.get(app.id, []),
            "capabilities": capabilities.get(app.id, []),
            "dependents": dependents.get(app.id, 0),
            "peer_id": peers.get(app.id),
            "answer": {
                key: item["level"] for key, item in assessed.answers.items()
            } if current and assessed else {},
            "assessment": {
                "ref": assessed.ref, "by": assessed.assessed_by_name, "on": assessed.assessed_on,
                "current": current,
            } if assessed else None,
            "assessment_expired": bool(assessed and not current),
            "decided_within_year": False,
            "decision": None,
            "decision_review_due": False,
            **extra.get(app.id, {}),
        }  # fmt: skip
    return out


def _peer(app: Application, bv: float | None) -> dict[str, Any]:
    return {"ref": app.ref, "name": app.name, "bv": bv}


def score_all(
    session: Session, apps: list[Application], *, on: date | None = None
) -> dict[int, dict[str, Any]]:
    """Each application's scores, recommendation, flags, and working. The primary providers
    an application overlaps with are scored too, since consolidation compares with them."""
    on = on or today_()
    model_row = current_model(session)
    model = model_row.definition
    facts = gather(session, apps, model, on)
    wanted = {peer for f in facts.values() if (peer := f.get("peer_id")) and peer not in facts}
    peer_apps = {app.id: app for app in apps}
    if wanted:
        more = list(session.scalars(select(Application).where(Application.id.in_(wanted))))
        peer_apps.update({app.id: app for app in more})
        peer_facts = gather(session, more, model, on)
    else:
        peer_facts = {}
    first = {
        app_id: evaluate({**f, "peer": None}, model, today=on)
        for app_id, f in {**facts, **peer_facts}.items()
    }
    out = {}
    for app_id, f in facts.items():
        peer_id = f.get("peer_id")
        if peer_id is None:
            result = first[app_id]
        else:
            bv = first[peer_id]["scores"]["business_value"] if peer_id in first else None
            result = evaluate({**f, "peer": _peer(peer_apps[peer_id], bv)}, model, today=on)
        result["model_version"] = model_row.version
        result["model_id"] = model_row.id
        result["assessment"] = f["assessment"]
        out[app_id] = result
    return out


def score_one(session: Session, app: Application, *, on: date | None = None) -> dict[str, Any]:
    return score_all(session, [app], on=on)[app.id]


def preview(session: Session, principal: Principal, app: Application, given: Any) -> dict[str, Any]:
    """What the scores would be with these answers, worked out by the same engine."""
    if not access.can_assess(session, principal, app):
        raise PermissionDenied("You cannot assess this application.")
    bank = current_questionnaire(session).definition
    answers = clean_answers(bank, given)
    model_row = current_model(session)
    on = today_()
    facts = gather(session, [app], model_row.definition, on)[app.id]
    facts["answer"] = {key: item["level"] for key, item in answers.items()}
    facts["assessment_expired"] = False
    peer = None
    if facts.get("peer_id"):
        other = session.get(Application, facts["peer_id"])
        if other is not None:
            peer = _peer(other, score_one(session, other, on=on)["scores"]["business_value"])
    result = evaluate({**facts, "peer": peer}, model_row.definition, today=on)
    result["model_version"] = model_row.version
    return result


def redact(result: dict[str, Any], sensitive: Iterable[str]) -> dict[str, Any]:
    """The working with anything a sensitive field would reveal withheld: the value, its
    level, and the words that say it. The scores themselves are not sensitive."""
    hidden: set[str] = set()
    for name in sensitive:
        hidden |= REVEALS.get(name, {name})
    out = copy.deepcopy(result)
    for dimension in out["dimensions"].values():
        for factor in dimension["factors"]:
            if factor["key"] in hidden and factor["state"] == "known":
                factor.update(level="withheld", value="withheld", why="Withheld")
        dimension.pop("sum", None)
        dimension.pop("raw", None)
    out["withheld"] = True
    return out


def shown(
    session: Session, principal: Principal, app: Application, result: dict[str, Any]
) -> dict[str, Any]:
    if access.sees_sensitive(session, principal, app):
        return result
    return redact(result, catalog.sensitive_fields(session))


# --- Snapshots -------------------------------------------------------------------------------


def digest(working: Mapping[str, Any]) -> str:
    text = json.dumps(working, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def take_snapshot(
    session: Session,
    app: Application,
    result: dict[str, Any],
    *,
    reason: str,
    portfolio_snapshot_id: int | None = None,
) -> ScoreSnapshot:
    """Keep a score exactly as it is now. The caller records its digest in an event."""
    working = json.loads(json.dumps(result, default=str))
    scores = result["scores"]
    row = ScoreSnapshot(
        application_id=app.id,
        portfolio_snapshot_id=portfolio_snapshot_id,
        taken_at=utc_now(),
        reason=reason,
        model_id=result["model_id"],
        profile_key=result["profile"]["key"],
        bv=scores["business_value"],
        th=scores["technical_health"],
        cb=scores["cost_burden"],
        re=scores["risk_exposure"],
        confidence=result["confidence"],
        recommendation=result["recommendation"],
        flags=[flag["key"] for flag in result["flags"]],
        working=working,
        digest=digest(working),
    )
    session.add(row)
    session.flush()
    return row


# --- The program's parts: the question bank and the scoring model -----------------------------


def _load_questionnaire(session: Session, definition: Any, *, only_missing: bool) -> int:
    if definition is None:
        return 0
    have = session.scalars(select(Questionnaire.id).limit(1)).first()
    if only_missing and have is not None:
        return 0
    return 1 if publish_questionnaire(session, definition, "Program pack") else 0


def _load_scoring(session: Session, definition: Any, *, only_missing: bool) -> int:
    if definition is None:
        return 0
    have = session.scalars(select(ScoringModel.id).limit(1)).first()
    if only_missing and have is not None:
        return 0
    return 1 if publish_model(session, definition, "Program pack") else 0


def _check_scoring(definition: Any) -> list[str]:
    bank = vocab.default_pack()["questionnaire"]
    return problems(definition, question_keys(bank))


def _has_assessment(session: Session, app: Application) -> bool:
    row = latest(session, [app.id]).get(app.id)
    if row is None:
        return False
    return is_current(row, app.tier, current_model(session).definition, today_())


def _install() -> None:
    from appwren.program import packs

    packs.PARTS.extend(
        [
            ("questionnaire", check_questionnaire,
             lambda s: current_questionnaire(s).definition, _load_questionnaire),
            ("scoring", _check_scoring, lambda s: current_model(s).definition, _load_scoring),
        ]
    )  # fmt: skip
    applications.HAS["assessment"] = _has_assessment
    original = APPLICATION.extra.get("cards")

    def cards(session: Session, principal: Principal, rows: list[Any]) -> list[dict[str, Any]]:
        """Each row of a list of applications carries its scores and recommendation."""
        base = original(session, principal, rows) if original else [{} for _ in rows]
        found = score_all(session, rows) if rows else {}
        for item, row in zip(base, rows, strict=True):
            result = found[row.id]
            item.update(
                scores=result["scores"],
                confidence=result["confidence"],
                recommendation=result["recommendation"],
                flags=[{"key": f["key"], "severity": f["severity"], "text": f["text"]}
                       for f in result["flags"]],
            )  # fmt: skip
        return base

    APPLICATION.extra["cards"] = cards


_install()
