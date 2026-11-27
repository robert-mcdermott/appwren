"""Initiatives and the roadmap (slice 2 of wave 5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from appwren.core import clock
from appwren.db.engine import Database
from tests.people import People
from tests.test_decisions import add_app, decide

Clients = Callable[[str | None], TestClient]
TODAY = clock.today()


def start(client: TestClient, people: People, unit: str = "IMM", **values: object) -> str:
    said = client.post("/api/v1/initiatives", json={
        "name": "Move the trackers to one", "org_unit_id": people.units[unit],
        "kind": "consolidate", "stage": "approved",
        "starts_on": TODAY.isoformat(), "ends_on": (TODAY + timedelta(days=200)).isoformat(),
        **values,
    })  # fmt: skip
    assert said.status_code == 201, said.text
    return said.json()["data"]["ref"]


def test_an_initiative_names_what_it_changes_with_the_decisions_behind_it(
    as_role: Clients, db: Database, people: People
) -> None:
    old = add_app(db, people, name="Old Tracker")
    new = add_app(db, people, name="New Tracker")
    secret = add_app(db, people, name="Secret Tracker", restricted=True)
    decide(db, people, "manager", old, disposition="consolidate", rationale="Two do one job.",
           successor=new, target_on=(TODAY + timedelta(days=180)).isoformat())  # fmt: skip
    steward = as_role("steward")
    ref = start(steward, people)
    said = steward.put(f"/api/v1/initiatives/{ref}/applications", json={"applications": [
        {"application": old, "action": "retires"},
        {"application": new, "action": "receives", "note": "Takes the old one's samples"},
        {"application": secret, "action": "changes"},
    ]})  # fmt: skip
    assert said.status_code == 200, said.text
    shown = said.json()["data"]
    names = {a["name"]: (a["action"], a["decision"]) for a in shown["applications"]}
    assert names["Old Tracker"][0] == "retires"
    assert names["Old Tracker"][1]["disposition"] == "consolidate"
    assert names["New Tracker"] == ("receives", None)
    # Someone who may not see an application is not told it is there.
    member = as_role("member").get(f"/api/v1/initiatives/{ref}").json()["data"]
    assert {a["name"] for a in member["applications"]} == {"Old Tracker", "New Tracker"}
    assert member["hidden_applications"] == 1
    # And the application's page lists it.
    page = steward.get(f"/api/v1/applications/{old}").json()["data"]
    assert [(i["ref"], i["action"]) for i in page["initiatives"]] == [(ref, "retires")]
    listed = steward.get("/api/v1/initiatives", params={"application": new}).json()["data"]
    assert [row["ref"] for row in listed] == [ref]
    # Bad lists are refused whole.
    refused = steward.put(f"/api/v1/initiatives/{ref}/applications", json={"applications": [
        {"application": old, "action": "explodes"}, {"application": "APP-9999"}]})  # fmt: skip
    assert refused.status_code == 422 and len(refused.json()["errors"]) == 2
    # Those who keep neither it nor its unit change nothing on it.
    assert as_role("member").put(f"/api/v1/initiatives/{ref}/applications",
                                 json={"applications": []}).status_code == 403  # fmt: skip
    early = (TODAY - timedelta(days=1)).isoformat()
    ends_first = steward.patch(f"/api/v1/initiatives/{ref}",
                               json={"version": shown["version"], "ends_on": early})  # fmt: skip
    assert ends_first.status_code == 422


def test_the_roadmap_shows_exactly_the_initiatives_in_its_filters(
    as_role: Clients, db: Database, people: People
) -> None:
    manager = as_role("manager")
    first = start(manager, people, name="First", kind="modernize")
    second = start(manager, people, unit="CANCER", name="Second", kind="retire",
                   starts_on=(TODAY + timedelta(days=400)).isoformat(),
                   ends_on=(TODAY + timedelta(days=500)).isoformat())  # fmt: skip
    done = start(manager, people, name="Done", stage="done")
    whole = manager.get("/api/v1/roadmap").json()["data"]
    assert [i["ref"] for i in whole["initiatives"]] == [first, second]  # by start; none done
    assert whole["from"] <= TODAY.isoformat() <= whole["to"]
    assert whole["to"] >= (TODAY + timedelta(days=500)).isoformat()
    unit = manager.get("/api/v1/roadmap", params={"unit": people.units["IMM"]}).json()["data"]
    assert [i["ref"] for i in unit["initiatives"]] == [first]
    kind = manager.get("/api/v1/roadmap", params={"kind": "retire"}).json()["data"]
    assert [i["ref"] for i in kind["initiatives"]] == [second]
    closed = manager.get("/api/v1/roadmap", params={"closed": "true"}).json()["data"]
    assert {i["ref"] for i in closed["initiatives"]} == {first, second, done}
    item = next(i for i in whole["initiatives"] if i["ref"] == second)
    assert (item["kind"], item["stage"], item["unit"]["name"]) == ("retire", "approved",
                                                                   "Cancer Biology")  # fmt: skip
