"""Assessments and scores through the services and the API (slice 5 of wave 1)."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from appwren import assessment
from appwren.access.principal import Principal
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.inventory import applications, links, parts, records
from appwren.inventory.registry import APPLICATION, CAPABILITY, COMPONENT, TECHNOLOGY
from appwren.people import accounts
from appwren.program import vocab
from tests.people import ME, People

Clients = Callable[[str | None], TestClient]
GOOD = {
    "strategic_fit": 4,
    "functional_fit": 4,
    "future_need": 4,
    "reliability": 4,
    "maintainability": 4,
    "support_effort": 4,
    "change_effort": 4,
    "compliance": 4,
}


def who(db: Database, people: People, role: str) -> Principal:
    with db.read() as session:
        return accounts.principal_for(session, accounts.get(session, people.accounts[role]))


def add_app(db: Database, people: People, **values: Any) -> str:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        values = {
            "name": "Sample Tracker",
            "org_unit_id": people.units["HALE"],
            "tier": "3",
            "users": 120,
            "maintainers": 3,
            "annual_cost": 20_000,
            "sign_in": "sso",
            "monitoring": "alerting",
            "backup": "vendor",
            "data_classes": ["internal"],
            "sourcing": "saas",
            **values,
        }
        return records.create(session, steward, APPLICATION, values).ref


def assess(db: Database, people: People, ref: str, answers: dict[str, Any], **kw: Any) -> None:
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        assessment.record(session, steward, app, answers, **kw)


def scores(db: Database, ref: str) -> dict[str, Any]:
    with db.read() as session:
        return assessment.score_one(session, records.load(session, ME, APPLICATION, ref))


def test_an_assessment_is_recorded_and_the_next_supersedes_it(db: Database, people: People) -> None:
    ref = add_app(db, people)
    assert scores(db, ref)["recommendation"] == "assess"  # nothing answered yet
    assess(db, people, ref, GOOD, note="First look")
    assess(db, people, ref, {**GOOD, "reliability": {"level": 2, "note": "Two outages"}})
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        told = assessment.history(session, app)
        assert [(a["ref"], a["superseded"]) for a in told] == [
            ("ASM-0002", False),
            ("ASM-0001", True),
        ]
        assert told[0]["answers"]["reliability"] == {"level": 2, "note": "Two outages"}
        assert applications.missing(session, app)["now"].count("assessment") == 0
    result = scores(db, ref)
    assert result["assessment"]["ref"] == "ASM-0002"
    assert result["recommendation"] == "invest"


def test_answers_are_checked(db: Database, people: People) -> None:
    ref = add_app(db, people)
    for bad in (
        {"strategic_fit": 7},
        {"colour": 3},
        {"strategic_fit": None},
        {"reliability": True},
    ):
        with pytest.raises(Invalid):
            assess(db, people, ref, bad)


def test_who_may_assess(db: Database, people: People) -> None:
    ref = add_app(db, people)
    for role, allowed in [
        ("steward", True),
        ("architect", True),
        ("manager", True),
        ("member", False),
        ("leader", False),
        ("admin", False),
        ("auditor", False),
    ]:
        principal = who(db, people, role)
        with db.write(principal.actor) as session:
            app = records.load(session, principal, APPLICATION, ref)
            if allowed:
                assessment.record(session, principal, app, GOOD)
            else:
                with pytest.raises(PermissionDenied):
                    assessment.record(session, principal, app, GOOD)


def test_answers_expire_by_tier(db: Database, people: People) -> None:
    ref = add_app(db, people, tier="2")
    assess(db, people, ref, GOOD, on=date.today() - timedelta(days=400))
    result = scores(db, ref)
    assert result["assessment"]["current"] is False
    assert "assessment_expired" in [f["key"] for f in result["flags"]]
    reach = next(
        f for f in result["dimensions"]["business_value"]["factors"] if f["key"] == "strategic_fit"
    )
    assert reach["state"] == "unknown" and "expired" in reach["why"]
    tier4 = add_app(db, people, tier="4")
    assess(db, people, tier4, GOOD, on=date.today() - timedelta(days=400))
    assert scores(db, tier4)["assessment"]["current"] is True  # 24 months for tier 4


def test_the_preview_and_the_record_agree(db: Database, people: People) -> None:
    ref = add_app(db, people)
    steward = who(db, people, "steward")
    with db.read() as session:
        app = records.load(session, steward, APPLICATION, ref)
        previewed = assessment.preview(session, steward, app, GOOD)
    assess(db, people, ref, GOOD)
    recorded = scores(db, ref)
    for key in ("scores", "confidence", "recommendation", "flags", "missing"):
        assert previewed[key] == recorded[key], key


def test_facts_come_from_the_records_around_an_application(db: Database, people: People) -> None:
    ref = add_app(db, people, sourcing="built_here")
    other = add_app(db, people, name="Downstream")
    steward = who(db, people, "steward")
    with db.write(ME.actor) as session:
        tech = records.create(session, ME, TECHNOLOGY, {"name": "Java", "kind": "language"})
        parts.set_releases(
            session,
            ME,
            tech,
            [{"cycle": "8", "support_ends": (date.today() - timedelta(days=10)).isoformat()}],
        )
        capability = records.create(session, ME, CAPABILITY, {"name": "Sample tracking"})
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        component = records.create(
            session,
            steward,
            COMPONENT,
            {"name": "Server", "kind": "service", "application_id": ref},
        )
        parts.set_technologies(
            session, steward, component, [{"technology": tech.ref, "release": "8"}]
        )
        applications.set_capabilities(session, steward, app, [{"capability": capability.ref}])
        downstream = records.load(session, steward, APPLICATION, other)
        links.add(session, steward, APPLICATION, downstream, "depends_on", APPLICATION, app)
    result = scores(db, ref)
    by_key = {f["key"]: f for d in result["dimensions"].values() for f in d["factors"]}
    assert by_key["currency"]["level"] == 1 and "Java 8" in by_key["currency"]["why"]
    assert by_key["uniqueness"]["level"] == 5
    assert by_key["dependents"]["level"] == 3


def test_an_overlap_is_consolidated_into_the_primary(db: Database, people: People) -> None:
    primary = add_app(db, people, name="Survey Hub", tier="2", users=900)
    second = add_app(db, people, name="Old Surveys", tier="4", users=20)
    with db.write(ME.actor) as session:
        capability = records.create(session, ME, CAPABILITY, {"name": "Participant surveys"})
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        for ref, is_primary in ((primary, True), (second, False)):
            app = records.load(session, steward, APPLICATION, ref)
            applications.set_capabilities(
                session, steward, app, [{"capability": capability.ref, "is_primary": is_primary}]
            )
    assess(db, people, primary, GOOD)
    assess(db, people, second, {**GOOD, "strategic_fit": 2})
    result = scores(db, second)
    assert result["recommendation"] == "consolidate"
    assert result["overlap_with"]["ref"] == primary
    assert scores(db, primary)["recommendation"] == "invest"


def test_model_versions_are_never_changed_and_snapshots_reopen_unchanged(
    db: Database, people: People
) -> None:
    ref = add_app(db, people)
    assess(db, people, ref, GOOD)
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, ref)
        result = assessment.score_one(session, app)
        snap = assessment.take_snapshot(session, app, result, reason="manual")
        kept = (snap.id, snap.working, snap.digest)
        current = assessment.current_model(session)
        assert assessment.publish_model(session, copy.deepcopy(current.definition), "Test") is None
        changed = copy.deepcopy(current.definition)
        changed["thresholds"]["value"] = 4.5
        newer = assessment.publish_model(session, changed, "Test")
        assert (newer.version, current.status) == (2, "superseded")
        with pytest.raises(Invalid):
            broken = copy.deepcopy(changed)
            broken["thresholds"]["confidence"] = 400
            assessment.publish_model(session, broken, "Test")
    after = scores(db, ref)
    assert after["model_version"] == 2 and after["recommendation"] == "tolerate"
    with db.read() as session:
        from appwren.db.models import ScoreSnapshot

        again = session.get(ScoreSnapshot, kept[0])
        assert again.working == kept[1] and assessment.digest(again.working) == kept[2]
        assert again.recommendation == "invest" and again.model_id == current.id


def test_what_a_sensitive_field_reveals_is_withheld(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people)
    assess(db, people, ref, GOOD)
    member = as_role("member").get(f"/api/v1/applications/{ref}/scores").json()["data"]
    steward = as_role("steward").get(f"/api/v1/applications/{ref}/scores").json()["data"]
    assert member["scores"] == steward["scores"]  # scores are not sensitive
    assert member["recommendation"] == steward["recommendation"]

    def factor(data: dict[str, Any], dimension: str, key: str) -> dict[str, Any]:
        return next(f for f in data["dimensions"][dimension]["factors"] if f["key"] == key)

    for dimension, key in (
        ("technical_health", "security"),
        ("cost_burden", "annual_cost"),
        ("risk_exposure", "data_exposure"),
    ):
        assert factor(member, dimension, key)["value"] == "withheld"
        assert factor(steward, dimension, key)["value"] != "withheld"
    assert factor(member, "business_value", "reach")["value"] == 120  # users are not sensitive


def test_assessing_through_the_api(db: Database, people: People, as_role: Clients) -> None:
    ref = add_app(db, people)
    steward, member = as_role("steward"), as_role("member")
    bank = steward.get("/api/v1/questionnaire").json()["data"]
    assert all(len(q["levels"]) == 5 for s in bank["sections"] for q in s["questions"])
    preview = steward.post(f"/api/v1/applications/{ref}/score-preview", json={"answers": GOOD})
    assert preview.status_code == 200 and preview.json()["data"]["recommendation"] == "invest"
    assert (
        member.post(f"/api/v1/applications/{ref}/assessments", json={"answers": GOOD}).status_code
        == 403
    )
    done = steward.post(
        f"/api/v1/applications/{ref}/assessments", json={"answers": GOOD, "note": "ok"}
    )
    assert done.status_code == 201 and done.json()["data"]["scores"]["recommendation"] == "invest"
    listed = member.get("/api/v1/applications").json()["data"][0]
    assert listed["recommendation"] == "invest" and listed["confidence"] >= 70
    assert member.get(f"/api/v1/applications/{ref}/assessments").json()["data"][0]["note"] == "ok"


def test_the_question_bank_and_model_are_part_of_the_program(db: Database, people: People) -> None:
    from appwren.program import packs

    with db.write(ME.actor) as session:
        exported = packs.export(session)
        assert exported["scoring"] == vocab.default_pack()["scoring"]
        assert exported["questionnaire"] == vocab.default_pack()["questionnaire"]
        changed = copy.deepcopy(exported)
        changed["scoring"]["thresholds"]["confidence"] = 60
        result = packs.load(session, ME, changed, dry_run=False)
        assert "scoring" in result["settings"]
        assert assessment.current_model(session).version == 2
