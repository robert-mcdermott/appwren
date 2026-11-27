"""Trends between snapshots, scores over time, and shares of the portfolio (slice 1 of
wave 6)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren import assessment, decisions
from appwren.db.engine import Database
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.people import ME, People
from tests.test_decisions import add_app, decide, who

Clients = Callable[[str | None], TestClient]

QUESTIONS = ("strategic_fit", "functional_fit", "future_need", "reliability", "maintainability",
             "vendor_viability", "support_effort", "change_effort", "compliance")  # fmt: skip
POOR = dict.fromkeys(QUESTIONS, 1)


def snapshot(db: Database, people: People, name: str) -> str:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        return decisions.take_portfolio_snapshot(session, manager, name).ref


def test_two_snapshots_say_what_moved_between_them(
    as_role: Clients, db: Database, people: People
) -> None:
    steady = add_app(db, people, name="Steady")
    falling = add_app(db, people, name="Falling")
    secret = add_app(db, people, name="Secret", restricted=True, unit="CANCER")
    first = snapshot(db, people, "Spring")
    with db.write(ME.actor) as session:  # its answers turn poor: its scores fall
        app = records.load(session, ME, APPLICATION, falling)
        assessment.record(session, ME, app, POOR)
    decide(db, people, "manager", steady, disposition="maintain")
    added = add_app(db, people, name="Added later")
    second = snapshot(db, people, "Summer")
    member = as_role("member")
    said = member.get("/api/v1/trends", params={"before": first, "after": second})
    assert said.status_code == 200, said.text
    found = said.json()["data"]
    assert found["before"]["figures"]["scored"] == 2  # the restricted one is not counted
    assert found["after"]["figures"]["scored"] == 3
    names = {item["name"] for item in found["moved"]["scores"]}
    assert names == {"Falling"}
    change = found["moved"]["scores"][0]["changes"]
    assert all(c["to"] < c["from"] for c in change.values())
    assert [item["name"] for item in found["added"]] == ["Added later"]
    assert [(d["name"], d["disposition"]) for d in found["decided"]] == [("Steady", "maintain")]
    assert all(item["name"] != "Secret" for group in found["moved"].values() for item in group)
    # The manager, who may see everything, sees the restricted one counted.
    whole = as_role("manager").get("/api/v1/trends", params={"before": first}).json()["data"]
    assert whole["before"]["figures"]["scored"] == 3 and whole["after"]["name"] == "Today"
    assert (
        member.get("/api/v1/trends", params={"before": second, "after": first}).status_code == 422
    )
    # An application's scores over time: a point at each snapshot, and one for its decision.
    points = member.get(f"/api/v1/applications/{falling}/score-history").json()["data"]
    assert [p["reason"] for p in points] == ["portfolio", "portfolio"]
    assert points[1]["scores"]["business_value"] < points[0]["scores"]["business_value"]
    assert len(member.get(f"/api/v1/applications/{steady}/score-history").json()["data"]) == 3
    assert secret and added


def test_shares_of_the_portfolio(as_role: Clients, db: Database, people: People) -> None:
    for index in range(10):
        add_app(db, people, name=f"App {index}", annual_cost=1000 * (index + 1),
                users=10 * (index + 1))  # fmt: skip
    add_app(db, people, name="No cost", annual_cost=None, users=None)
    found = as_role("manager").get("/api/v1/shares").json()["data"]
    by_key = {share["key"]: share for share in found["shares"]}
    costliest = by_key["costliest"]
    assert [item["name"] for item in costliest["items"]] == ["App 9"]
    assert (costliest["of"], costliest["not_known"]) == (10, 1)
    least = by_key["least_used"]
    assert [item["name"] for item in least["items"]] == ["App 0", "App 1"]  # a fifth of ten
    assert least["threshold"] == 20
