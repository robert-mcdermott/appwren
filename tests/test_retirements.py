"""The retirement playbook (slice 5 of wave 5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from appwren.core import clock
from appwren.db.engine import Database
from appwren.planning.retirements import STEPS
from tests.people import People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]
TODAY = clock.today()


def test_a_retirement_is_planned_checked_off_and_counted(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Old Reports", annual_cost=30_000, lifecycle="phase_out")
    steward = as_role("steward")
    url = f"/api/v1/applications/{ref}/retirement"
    assert steward.get(url).json()["data"]["plan"] is None
    when = (TODAY + timedelta(days=60)).isoformat()
    assert as_role("member").post(url, json={"planned_on": when}).status_code == 403
    assert steward.post(url, json={}).status_code == 422
    started = steward.post(url, json={"planned_on": when, "note": "The dashboards replace it."})
    assert started.status_code == 201, started.text
    plan = started.json()["data"]["plan"]
    assert (plan["progress"], plan["started_by"]) == (0, "Steward Person")
    page = steward.get(f"/api/v1/applications/{ref}").json()["data"]
    assert page["retire_planned"] == when  # the record's date moves with the plan
    assert steward.post(url, json={"planned_on": when}).status_code == 409
    # It is completed only with every step done.
    assert steward.post(f"{url}/complete").status_code == 422
    for step in STEPS:
        said = steward.put(f"{url}/steps/{step}", json={"note": f"{step} done"})
        assert said.status_code == 200
    undone = steward.put(f"{url}/steps/users_told", json={"done": False}).json()["data"]["plan"]
    assert undone["progress"] == len(STEPS) - 1
    steward.put(f"{url}/steps/users_told", json={"note": "Told at the town hall"})
    assert steward.put(f"{url}/steps/no_such_step", json={}).status_code == 404
    done = steward.post(f"{url}/complete")
    assert done.status_code == 200, done.text
    plan = done.json()["data"]["plan"]
    assert plan["completed_on"] == TODAY.isoformat() and plan["savings"] == 30_000
    assert plan["done"]["users_told"]["note"] == "Told at the town hall"
    app = steward.get(f"/api/v1/applications/{ref}").json()["data"]
    assert app["lifecycle"] == "retired"
    # A completed plan changes no more.
    assert steward.put(f"{url}/steps/users_told", json={"done": False}).status_code == 409
    assert steward.delete(url).status_code == 409


def test_the_report_sums_the_savings_behind_it(
    as_role: Clients, db: Database, people: People
) -> None:
    steward = as_role("steward")
    refs = []
    for name, cost in (("First", 10_000), ("Second", 25_000), ("Third", 5_000)):
        ref = add_app(db, people, name=name, annual_cost=cost)
        url = f"/api/v1/applications/{ref}/retirement"
        steward.post(url, json={"planned_on": (TODAY + timedelta(days=30)).isoformat()})
        refs.append((ref, url))
    for _, url in refs[:2]:
        for step in STEPS:
            steward.put(f"{url}/steps/{step}", json={})
        steward.post(f"{url}/complete")
    late = add_app(db, people, name="Late")
    steward.post(f"/api/v1/applications/{late}/retirement",
                 json={"planned_on": (TODAY + timedelta(days=1)).isoformat()})  # fmt: skip
    # Cancelling one leaves no plan behind.
    assert steward.delete(f"/api/v1/applications/{late}/retirement").status_code == 200
    report = as_role("manager").get("/api/v1/retirements").json()["data"]
    assert [i["name"] for i in report["under_way"]] == ["Third"]
    assert sorted(i["name"] for i in report["done"]) == ["First", "Second"]
    assert report["savings"] == sum(i["savings"] for i in report["done"]) == 35_000
    assert report["savings_by_year"] == [{"year": TODAY.year, "savings": 35_000}]
