"""Scenarios: what a set of changes would do, before anyone commits to it (slice 4 of wave 6)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from appwren.db.engine import Database
from appwren.db.models import Event
from tests.people import ME, People
from tests.test_decisions import add_app
from tests.test_intake import capability, serves
from tests.test_interfaces import add_interface

Clients = Callable[[str | None], TestClient]


def events(db: Database, subject: str) -> int:
    with db.read() as session:
        return session.scalar(select(func.count()).where(Event.subject_type == subject)) or 0


def test_a_scenario_shows_its_effect_and_changes_nothing(
    as_role: Clients, db: Database, people: People
) -> None:
    old = add_app(db, people, name="Old Lab Notebook", annual_cost=30_000, users=100)
    small = add_app(db, people, name="Small Tracker", annual_cost=20_000, users=50)
    big = add_app(db, people, name="Big Tracker", annual_cost=80_000, users=400)
    stays = add_app(db, people, name="Warehouse", annual_cost=10_000, users=10)
    add_interface(db, ME, old, stays, name="Notebook to warehouse")  # breaks
    add_interface(db, ME, small, big, name="Small into big")  # its work moves inside
    add_interface(db, ME, old, small, name="Between the two leaving")  # goes with them
    notes, samples = capability(db, "Electronic notes"), capability(db, "Sample tracking")
    serves(db, old, notes)
    serves(db, small, samples)
    serves(db, big, samples)
    architect, member = as_role("architect"), as_role("member")
    assert member.post("/api/v1/scenarios", json={"name": "Tidy"}).status_code == 403
    made = architect.post("/api/v1/scenarios", json={"name": "Tidy the lab tools",
                                                     "summary": "Fewer trackers."})  # fmt: skip
    assert made.status_code == 201, made.text
    ref = made.json()["data"]["ref"]
    assert ref.startswith("SCN-")
    url = f"/api/v1/scenarios/{ref}/changes"
    bad = architect.put(url, json={"changes": [{"application": small, "action": "consolidate"}]})
    assert bad.status_code == 422  # consolidated into what?
    before = events(db, "application")
    said = architect.put(url, json={"changes": [
        {"application": old, "action": "retire"},
        {"application": small, "action": "consolidate", "into": big, "note": "Same samples"},
    ]})  # fmt: skip
    assert said.status_code == 200, said.text
    assert events(db, "application") == before  # building it changed no application
    found = member.get(f"/api/v1/scenarios/{ref}").json()["data"]
    effect = found["effect"]
    assert [c["action"] for c in found["changes"]] == ["retire", "consolidate"]
    assert found["changes"][1]["into"]["name"] == "Big Tracker"
    assert effect["cost_saved"] == 0 and effect["cost_withheld"] == 2  # not theirs to see
    whole = as_role("manager").get(f"/api/v1/scenarios/{ref}").json()["data"]["effect"]
    assert whole["cost_saved"] == 50_000 and whole["people"] == effect["people"] == 150
    assert [i["name"] for i in effect["interfaces"]] == ["Notebook to warehouse"]
    assert [c["name"] for c in effect["capabilities"]] == ["Electronic notes"]
    assert len(effect["risk"]["applications"]) == 2
    assert not found["may_keep"] and member.put(url, json={"changes": []}).status_code == 403
    # Something moving into an application that is itself leaving is refused.
    circular = architect.put(url, json={"changes": [
        {"application": old, "action": "retire"},
        {"application": small, "action": "replace", "into": old},
    ]})  # fmt: skip
    assert circular.status_code == 422
    # It becomes an initiative, proposed, naming the same applications.
    turned = architect.post(f"/api/v1/scenarios/{ref}/initiative", json={})
    assert turned.status_code == 201, turned.text
    initiative = turned.json()["data"]
    assert (initiative["kind"], initiative["stage"]) == ("consolidate", "proposed")
    actions = {a["name"]: a["action"] for a in initiative["applications"]}
    assert actions == {"Old Lab Notebook": "retires", "Small Tracker": "retires",
                       "Big Tracker": "receives"}  # fmt: skip
    again = member.get(f"/api/v1/scenarios/{ref}").json()["data"]
    assert again["initiative"]["ref"] == initiative["ref"]
    assert architect.put(url, json={"changes": []}).status_code == 409
    assert architect.post(f"/api/v1/scenarios/{ref}/initiative", json={}).status_code == 409
