"""Engineering maturity and signals as factors (slice 6 of wave 4)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from appwren import assessment
from appwren.connectors import sourced
from appwren.connectors.kinds import codehost as gh
from appwren.connectors.push import INCIDENTS
from appwren.db.engine import Database
from appwren.engine.model import problems
from appwren.events.actor import Actor
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, COMPONENT
from tests.people import ME, People
from tests.test_inventory import add_app, who

Clients = Callable[[str | None], TestClient]
KEPT = {"monitoring": "alerting", "backup": "tested", "docs_url": "https://docs.lab.example/x"}


def part(db: Database, people: People, app: str, name: str, *, repo: bool = True,
         kind: str = "service", role: str = "steward") -> str:  # fmt: skip
    steward = who(db, people, role)
    values = {"name": name, "application_id": app, "kind": kind}
    if repo:
        values["repo_url"] = f"https://github.com/lab/{name.lower().replace(' ', '-')}"
    with db.write(steward.actor) as session:
        return records.create(session, steward, COMPONENT, values).ref


def read(db: Database, ref: str, facts: dict[Any, Any], source: str = "GitHub") -> None:
    """What a source would have read, written as a run would write it."""
    with db.write(Actor.system(f"Connector: {source}")) as session:
        from appwren.inventory.registry import find_any

        _, record = find_any(session, ref)
        for spec, value in facts.items():
            sourced.write(session, source=source.lower(), source_name=source, record=record,
                          spec=spec, value=value)  # fmt: skip


GOLD = {gh.TESTS: True, gh.CI: True, gh.UPDATES: True,
        gh.ALERTS: {"critical": 0, "high": 2, "medium": 0, "low": 0}}  # fmt: skip


def test_a_component_is_at_exactly_the_level_its_checks_give(
    as_role: Clients, db: Database, people: People
) -> None:
    app = add_app(db, people, name="Tracker", **KEPT)
    api = part(db, people, app, "Tracker API")
    jobs = part(db, people, app, "Tracker jobs")
    store = part(db, people, app, "Tracker store", repo=False, kind="database")
    read(db, api, GOLD)
    read(db, jobs, {gh.TESTS: True, gh.CI: False, gh.ALERTS: {"critical": 1}})
    member = as_role("member")
    found = member.get(f"/api/v1/maturity/{app}").json()["data"]
    levels = {c["name"]: c["level"] for c in found["components"]}
    # A database with no repository: the checks about code do not apply to it.
    assert levels == {"Tracker API": "gold", "Tracker jobs": "bronze", "Tracker store": "gold"}
    assert (found["level"], found["label"]) == ("bronze", "Bronze")  # its least mature part
    assert found["held_back_by"] == [jobs]
    jobs_item = next(c for c in found["components"] if c["ref"] == jobs)
    assert jobs_item["next"]["key"] == "silver"
    assert [c["key"] for c in jobs_item["next"]["missing"]] == ["ci"]
    states = {c["key"]: c["state"] for c in jobs_item["checks"]}
    assert states == {"monitoring": "met", "backups": "met", "documentation": "met",
                      "tests": "met", "ci": "not_met", "dependency_updates": "unknown",
                      "no_critical_alerts": "not_met"}  # fmt: skip
    one = member.get(f"/api/v1/maturity/{store}").json()["data"]
    assert one["component"]["level"] == "gold" and one["application"]["level"] == "bronze"
    # Below the first level when a check of it fails; not measured with no components.
    bare = add_app(db, people, name="Bare", sourcing="built_here", monitoring="none",
                   backup="tested", docs_url="https://docs.lab.example/bare")  # fmt: skip
    part(db, people, bare, "Bare app", repo=False)
    assert member.get(f"/api/v1/maturity/{bare}").json()["data"]["label"] == "Below bronze"
    alone = add_app(db, people, name="Alone", sourcing="built_here")
    assert member.get(f"/api/v1/maturity/{alone}").json()["data"]["level"] is None
    # A bought product's engineering is its vendor's: not measured, though it has parts.
    bought = add_app(db, people, name="Bought", sourcing="saas", **KEPT)
    part(db, people, bought, "Bought app", repo=False)
    assert member.get(f"/api/v1/maturity/{bought}").json()["data"]["level"] is None
    # Code built here with no repository recorded cannot show its practice.
    unknown = add_app(db, people, name="Unknown", sourcing="built_here", **KEPT)
    part(db, people, unknown, "Unknown app", repo=False)
    assert member.get(f"/api/v1/maturity/{unknown}").json()["data"]["level"] == "bronze"
    # A README counts as documentation where no address is recorded.
    readme = add_app(db, people, name="Readme only", monitoring="uptime", backup="vendor")
    code = part(db, people, readme, "Readme code")
    read(db, code, {gh.README: True, **GOLD})
    assert member.get(f"/api/v1/maturity/{readme}").json()["data"]["level"] == "gold"


def test_the_report_counts_are_the_lists_behind_them(
    as_role: Clients, db: Database, people: People
) -> None:
    gold = add_app(db, people, name="Gold one", **KEPT)
    read(db, part(db, people, gold, "Gold code"), GOLD)
    bronze = add_app(db, people, name="Bronze one", **KEPT)
    part(db, people, bronze, "Bronze code")
    add_app(db, people, role="manager", unit="CANCER", name="Elsewhere", restricted=True, **KEPT)
    none = add_app(db, people, role="manager", unit="CANCER", name="Not kept", monitoring="none")
    part(db, people, none, "Not kept code", repo=False, role="manager")
    for role in ("member", "manager"):
        client = as_role(role)
        report = client.get("/api/v1/maturity").json()["data"]
        assert [key for key, _ in report["levels"]] == [
            "none",
            "bronze",
            "silver",
            "gold",
            "unmeasured",
        ]
        checked = 0
        for row in [*report["rows"], {"unit": None, **report["all"]}]:
            for level, count in row["counts"].items():
                params = {"maturity": level, "limit": 200}
                if row["unit"]:
                    params["unit"] = row["unit"]["id"]
                listed = client.get("/api/v1/applications", params=params).json()["data"]
                assert len(listed) == count, (role, row["unit"], level)
                checked += count
        assert checked > 0
        assert report["all"]["counts"]["gold"] == 1 and report["all"]["counts"]["bronze"] == 1
    # The manager sees the restricted application in the other unit; the member does not.
    member_all = as_role("member").get("/api/v1/maturity").json()["data"]["all"]["total"]
    manager_all = as_role("manager").get("/api/v1/maturity").json()["data"]["all"]["total"]
    assert manager_all > member_all


def factor(result: dict[str, Any], key: str) -> dict[str, Any]:
    return next(f for d in result["dimensions"].values() for f in d["factors"] if f["key"] == key)


def test_a_signal_counts_only_where_a_source_supplies_it(db: Database, people: People) -> None:
    app = add_app(db, people, name="Tracker", sourcing="built_here", users=40, **KEPT)
    other = add_app(db, people, name="Other", sourcing="built_here", users=40, **KEPT)
    with db.read() as session:
        before = assessment.score_one(session, records.load(session, ME, APPLICATION, other))
    read(db, app, {INCIDENTS: 7}, source="Service desk")
    read(db, app, {gh.MAINTAINERS: 3})
    api = part(db, people, app, "Tracker API")
    read(db, api, {**GOLD, gh.LAST_CHANGE: "2026-11-01"})
    with db.read() as session:
        scored = assessment.score_one(session, records.load(session, ME, APPLICATION, app))
        after = assessment.score_one(session, records.load(session, ME, APPLICATION, other))
    # Nothing supplied: every signal stands aside, and the scores are as they were.
    assert after["scores"] == before["scores"] and after["confidence"] == before["confidence"]
    for key in ("incidents", "dependency_alerts", "code_activity", "engineering_maturity",
                "support_load"):  # fmt: skip
        found = factor(after, key)
        assert (found["state"], found["why"]) == ("not_applicable", "No source supplies it")
    # Supplied: each joins its dimension, with its source in the working.
    incidents = factor(scored, "incidents")
    assert incidents["state"] == "known" and incidents["level"] == 2
    assert incidents["why"] == "7 in 90 days, from Service desk"
    alerts = factor(scored, "dependency_alerts")
    assert (alerts["value"], alerts["from"]) == (2, "GitHub")
    maturity = factor(scored, "engineering_maturity")
    assert maturity["value"] == "gold" and maturity["why"] == "Gold, from its checks"
    assert factor(scored, "sustainability")["from"] == "GitHub"  # its maintainers
    assert factor(scored, "support_load")["state"] == "not_applicable"  # no tickets pushed
    assert scored["scores"]["technical_health"] != after["scores"]["technical_health"]


def test_an_upgrade_from_030_brings_signals_to_an_unshaped_model(
    db: Database, people: People
) -> None:
    from appwren.program import packs

    earlier = json.loads(
        Path(__file__).parent.joinpath("fixtures", "scoring-0.3.0.json").read_text()
    )
    assert assessment.digest(earlier) in assessment.earlier_defaults("scoring")
    assert "maturity" not in earlier
    with db.write(ME.actor) as session:
        assessment.publish_model(session, earlier, "Program pack")
        assert packs.install(session)["scoring"] == 1
        model = assessment.current_model(session).definition
        kinds = [f["kind"] for f in model["profiles"][-1]["factors"]["technical_health"]]
        assert kinds.count("signal") == 4
        assert [level["key"] for level in model["maturity"]["levels"]] == [
            "bronze",
            "silver",
            "gold",
        ]


def test_a_model_says_what_is_wrong_with_its_signals_and_levels() -> None:
    from appwren.program import vocab

    pack = vocab.default_pack()
    model = json.loads(json.dumps(pack["scoring"]))
    questions = assessment.question_keys(pack["questionnaire"])
    standard = model["profiles"][-1]["factors"]["technical_health"]
    standard.append({"key": "mood", "label": "Mood", "kind": "signal", "weight": 5,
                     "signal": "mood", "bands": [1, 2, 3, 4], "direction": "rising"})  # fmt: skip
    model["maturity"]["levels"][1]["checks"].append("vibes")
    found = problems(model, questions)
    signals = "incidents_90d, tickets_90d, open_alerts, days_since_change, maturity"
    assert f"Profile standard technical_health mood: a signal is one of {signals}" in found
    assert "The maturity level silver has no check called vibes." in found
