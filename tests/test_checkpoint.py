"""The checkpoint another process asks (slice 1 of wave 8)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.people import ME, People
from tests.test_decisions import add_app, decide

Clients = Callable[[str | None], TestClient]


def test_the_checkpoint_says_yes_or_no_and_why(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Sample Store", data_classes=["internal", "personal"])
    member = as_role("member")
    said = member.get(f"/api/v1/checkpoint/{ref}", params={"data_class": "personal"})
    assert said.status_code == 200, said.text
    answer = said.json()["data"]
    assert answer["approved"] is True and answer["allowed"] is True
    assert {item["check"] for item in answer["reasons"]} == {"stage", "decision", "support",
                                                              "data_class"}  # fmt: skip
    health = member.get(f"/api/v1/checkpoint/{ref}", params={"data_class": "health"}).json()
    assert health["data"]["approved"] is True and health["data"]["allowed"] is False
    assert any(not r["ok"] and "does not say" in r["text"] for r in health["data"]["reasons"])
    assert member.get(f"/api/v1/checkpoint/{ref}", params={"data_class": "gold"}).status_code == 422
    # A decision to retire it takes the approval away, and says so.
    decide(db, people, "manager", ref, disposition="retire")
    retiring = member.get(f"/api/v1/checkpoint/{ref}").json()["data"]
    assert retiring["approved"] is False
    assert any(r["check"] == "decision" and not r["ok"] for r in retiring["reasons"])
    # So does a stage not open to new use.
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, ref)
        records.update(session, ME, APPLICATION, app, {"lifecycle": "evaluating"},
                       version=app.version)  # fmt: skip
    stage = member.get(f"/api/v1/checkpoint/{ref}").json()["data"]["reasons"][0]
    assert stage["check"] == "stage" and stage["ok"] is False


def test_a_hidden_application_is_not_even_confirmed(
    as_role: Clients, db: Database, people: People
) -> None:
    with db.write(ME.actor) as session:
        secret = records.create(session, ME, APPLICATION, {
            "name": "Hidden Store", "org_unit_id": people.units["CANCER"], "restricted": True,
        }, accountable=people.accounts["admin"]).ref  # fmt: skip
    assert as_role("member").get(f"/api/v1/checkpoint/{secret}").status_code == 404
    assert as_role("member").get("/api/v1/checkpoint/APP-9999").status_code == 404
    seen = as_role("auditor").get(f"/api/v1/checkpoint/{secret}").json()["data"]
    assert seen["name"] == "Hidden Store"
