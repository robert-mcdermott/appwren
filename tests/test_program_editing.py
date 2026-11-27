"""Shaping the program in the app, with a preview of what a changed model would change, and
the monthly snapshot (CUR-09)."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, jobs
from appwren.core.clock import frozen_at
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Application, PortfolioSnapshot
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from appwren.program import catalog, editing, vocab
from tests.conftest import Instance
from tests.people import ME, People
from tests.test_decisions import GOOD, who

Clients = Callable[[str | None], TestClient]


def portfolio(db: Database, people: People) -> list[str]:
    """A handful of applications at different tiers and costs, all assessed."""
    refs = []
    with db.write(ME.actor) as session:
        for index, (tier, cost) in enumerate(
            [("1", 400_000), ("2", 90_000), ("3", 20_000), ("4", 3_000), ("5", 0)]
        ):
            app = records.create(
                session, ME, APPLICATION,
                {"name": f"Application {index}", "org_unit_id": people.units["HALE"], "tier": tier,
                 "sourcing": "saas", "users": 50 * (index + 1), "annual_cost": cost,
                 "sign_in": "sso", "monitoring": "alerting", "backup": "vendor",
                 "data_classes": ["internal"], "maintainers": 2},
                accountable=people.accounts["member"],
            )  # fmt: skip
            assessment.record(session, ME, app, GOOD)
            refs.append(app.ref)
    return refs


def scored(db: Database) -> dict[str, dict[str, Any]]:
    with db.read() as session:
        apps = list(session.scalars(select(Application)))
        found = assessment.score_all(session, apps)
        return {app.ref: editing._summary(found[app.id]) for app in apps}


def test_publishing_a_changed_model_changes_exactly_the_applications_the_preview_listed(
    db: Database, people: People
) -> None:
    portfolio(db, people)
    manager = who(db, people, "manager")
    with db.read() as session:
        model = copy.deepcopy(assessment.current_model(session).definition)
    model["thresholds"]["value"] = 3.9  # fewer count as valuable
    standard = next(p for p in model["profiles"] if p["key"] == "standard")
    cost = standard["factors"]["cost_burden"]
    cost[0]["weight"], cost[3]["weight"] = cost[0]["weight"] + 10, cost[3]["weight"] - 10
    before = scored(db)
    with db.read() as session:
        preview = editing.preview_model(session, manager, model)
    assert preview["count"] >= 1 and not preview["same"]
    assert scored(db) == before  # a preview changes nothing
    with db.write(manager.actor) as session:
        published = editing.publish_model(session, manager, model)
    after = scored(db)
    moved = {ref for ref in after if after[ref] != before[ref]}
    assert moved == {item["application"]["ref"] for item in preview["changed"]}
    assert published["version"] == 2 and published["changed"] == preview["changed"]
    with db.read() as session:
        assert assessment.current_model(session).published_by == "Manager Person"


def test_a_model_that_does_not_add_up_is_refused(db: Database, people: People) -> None:
    manager = who(db, people, "manager")
    with db.read() as session:
        model = copy.deepcopy(assessment.current_model(session).definition)
    standard = next(p for p in model["profiles"] if p["key"] == "standard")
    standard["factors"]["business_value"][0]["weight"] += 5
    model["cadence"]["stale_penalty"] = 80
    with db.read() as session, pytest.raises(Invalid) as caught:
        editing.preview_model(session, manager, model)
    text = caught.value.errors["scoring"]
    assert "add up to 105, not 100" in text and "0 to 50 points" in text
    steward = who(db, people, "steward")
    with db.read() as session, pytest.raises(PermissionDenied):
        editing.preview_model(session, steward, model)


def test_a_list_is_renamed_reordered_added_to_and_retired_but_never_emptied(
    db: Database, people: People
) -> None:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        have = vocab.get(session, "hosting")
        with pytest.raises(Invalid, match="not saved"):  # what the rules read stays fixed
            editing.save_vocabulary(session, manager, "hosting", [*have, {"label": "Under a desk"}])
        kinds = vocab.get(session, "platform_kinds")
        renamed = [{**kinds[1], "label": "A cloud account"}, kinds[0], *kinds[2:],
                   {"label": "Lab server room"}]  # fmt: skip
        saved = editing.save_vocabulary(session, manager, "platform_kinds", renamed)
        assert [item["key"] for item in saved][:2] == [kinds[1]["key"], kinds[0]["key"]]
        assert saved[1 - 1]["label"] == "A cloud account" and saved[-1]["key"] == "lab_server_room"
        with pytest.raises(Invalid, match="not saved") as caught:
            editing.save_vocabulary(session, manager, "platform_kinds", saved[:-1])
        assert "cannot be removed" in caught.value.errors["items"]
        retired = [*saved[:-1], {**saved[-1], "retired": True}]
        editing.save_vocabulary(session, manager, "platform_kinds", retired)
        assert "lab_server_room" not in vocab.keys(session, "platform_kinds")
        assert "lab_server_room" in vocab.keys(session, "platform_kinds", active_only=False)


def test_the_organizations_own_fields_and_the_wording_of_the_questions(
    db: Database, people: People
) -> None:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        irb = {"key": "irb_number", "label": "IRB number", "type": "text", "section": "research"}
        fields = [*catalog.fields(session), irb]
        saved = editing.save_fields(session, manager, fields, ["annual_cost", "irb_number"])
        assert "irb_number" in [f["key"] for f in saved["fields"]]
        assert "irb_number" in saved["sensitive_fields"]
        with pytest.raises(Invalid, match="not saved"):
            editing.save_fields(session, manager, fields[:-1])
        bank = copy.deepcopy(assessment.current_questionnaire(session).definition)
        bank["sections"][0]["questions"][0]["text"] = "How closely does it serve our strategy?"
        assert editing.save_questionnaire(session, manager, bank) == {"version": 2, "changed": True}
        bank["sections"][0]["questions"].pop()
        with pytest.raises(Invalid, match="not published"):
            editing.save_questionnaire(session, manager, bank)


def test_the_api_previews_and_publishes(as_role: Clients, db: Database, people: People) -> None:
    portfolio(db, people)
    manager = as_role("manager")
    program = manager.get("/api/v1/program").json()["data"]
    assert "hosting" in program["fixed"] and program["scoring"]["version"] == 1
    model = program["scoring"]["definition"]
    model["cadence"]["stale_penalty"] = 20
    shown = manager.post("/api/v1/program/scoring/preview", json={"definition": model}).json()
    assert shown["data"]["count"] == 0  # nothing here is stale, so nothing moves
    done = manager.put("/api/v1/program/scoring", json={"definition": model}).json()["data"]
    assert (done["version"], done["published"]) == (2, True)
    assert as_role("architect").get("/api/v1/program").status_code == 403


def test_the_scheduler_keeps_a_snapshot_each_month(instance: Instance, people: People) -> None:
    db, config = instance.db, instance.config
    with frozen_at(datetime(2026, 11, 3, 9, tzinfo=UTC)):
        result = jobs.run_job(db, config, "snapshots", force=True)
        assert result is not None and result["counts"] == {"monthly_snapshots_taken": 0}
    portfolio(db, people)
    with frozen_at(datetime(2026, 11, 3, 10, tzinfo=UTC)):
        assert jobs.run_job(db, config, "snapshots", force=True)["counts"] == {
            "monthly_snapshots_taken": 1
        }
        assert jobs.run_job(db, config, "snapshots", force=True)["counts"] == {
            "monthly_snapshots_taken": 0
        }  # once a month
    with frozen_at(datetime(2026, 12, 1, 7, tzinfo=UTC)):
        assert jobs.run_job(db, config, "snapshots", force=True)["counts"] == {
            "monthly_snapshots_taken": 1
        }
    with db.read() as session:
        names = session.scalars(select(PortfolioSnapshot.name).order_by(PortfolioSnapshot.id)).all()
        assert names == ["November 2026, monthly", "December 2026, monthly"]
        assert session.scalars(select(PortfolioSnapshot)).first().count == 5
