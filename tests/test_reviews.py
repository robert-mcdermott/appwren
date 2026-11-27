"""Portfolio reviews: the agenda drawn from a scope, decisions taken in the review, and a
closed review that changes no more (slice 1 of wave 5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from appwren import assessment
from appwren.core import clock
from appwren.db.engine import Database
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.people import ME, People
from tests.test_decisions import add_app, decide

Clients = Callable[[str | None], TestClient]
TODAY = clock.today()


def recommended(db: Database, ref: str) -> str:
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        return str(assessment.score_one(session, app)["recommendation"])


def plan(client: TestClient, people: People, unit: str = "IMM", **values: object) -> str:
    said = client.post("/api/v1/reviews", json={
        "name": "Immunology review, spring", "org_unit_id": people.units[unit],
        "held_on": (TODAY + timedelta(days=30)).isoformat(), **values,
    })  # fmt: skip
    assert said.status_code == 201, said.text
    return said.json()["data"]["ref"]


def test_the_agenda_holds_what_needs_deciding_in_scope(
    as_role: Clients, db: Database, people: People
) -> None:
    undecided = add_app(db, people, name="Undecided")
    settled = add_app(db, people, name="Settled")
    decide(db, people, "manager", settled, disposition=recommended(db, settled))
    mismatch = add_app(db, people, name="Mismatch")
    other = "retire" if recommended(db, mismatch) != "retire" else "invest"
    decide(db, people, "manager", mismatch, disposition=other)
    due = add_app(db, people, name="Due")
    decide(db, people, "manager", due, disposition=recommended(db, due),
           review_on=(TODAY + timedelta(days=10)).isoformat())  # fmt: skip
    add_app(db, people, unit="CANCER", name="Elsewhere")  # out of scope
    add_app(db, people, name="Tier five", tier="5")  # narrowed out by tier
    leader = as_role("leader")
    ref = plan(leader, people, tiers=["1", "2", "3"])
    drawn = leader.post(f"/api/v1/reviews/{ref}/draw")
    assert drawn.status_code == 200, drawn.text
    agenda = drawn.json()["data"]["agenda"]
    assert drawn.json()["meta"]["added"] == 3
    reasons = {item["application"]["name"]: item["reason"] for item in agenda["items"]}
    assert reasons == {"Undecided": "undecided", "Mismatch": "mismatch", "Due": "review_due"}
    assert undecided in [item["application"]["ref"] for item in agenda["items"]]
    # Drawing again adds nothing new; an application can be added and removed by hand.
    assert leader.post(f"/api/v1/reviews/{ref}/draw").json()["meta"]["added"] == 0
    added = leader.post(f"/api/v1/reviews/{ref}/items",
                        json={"application": settled, "note": "Renewal is coming"})  # fmt: skip
    assert added.status_code == 201
    again = leader.post(f"/api/v1/reviews/{ref}/items", json={"application": settled})
    assert again.status_code == 409
    item = next(i for i in added.json()["data"]["agenda"]["items"] if i["reason"] == "added")
    assert item["note"] == "Renewal is coming"
    removed = leader.delete(f"/api/v1/reviews/{ref}/items/{item['id']}")
    assert len(removed.json()["data"]["agenda"]["items"]) == 3
    # Only those who run reviews over the unit change one.
    for role in ("steward", "member", "architect"):
        assert as_role(role).post(f"/api/v1/reviews/{ref}/draw").status_code == 403
    assert as_role("member").get(f"/api/v1/reviews/{ref}").status_code == 200


def test_a_review_keeps_what_was_decided_in_it(
    as_role: Clients, db: Database, people: People
) -> None:
    first = add_app(db, people, name="First")
    second = add_app(db, people, name="Second")
    decide(db, people, "manager", first, disposition="tolerate")  # before the review
    manager = as_role("manager")
    ref = plan(manager, people)
    manager.post(f"/api/v1/reviews/{ref}/draw")
    assert manager.post(f"/api/v1/reviews/{ref}/close").status_code == 422  # not open yet
    opened = manager.post(f"/api/v1/reviews/{ref}/open").json()["data"]
    assert opened["state"] == "open"
    decide(db, people, "leader", second, disposition="invest", rationale="Agreed in review.")
    shown = manager.get(f"/api/v1/reviews/{ref}").json()["data"]["agenda"]
    taken = {i["application"]["name"]: i["taken"] for i in shown["items"]}
    assert taken["Second"]["disposition"] == "invest" and taken["Second"]["by"] == "Leader Person"
    assert taken.get("First") is None  # decided before the review opened
    assert (shown["decided"], shown["waiting"]) == (1, len(shown["items"]) - 1)
    closed = manager.post(f"/api/v1/reviews/{ref}/close").json()["data"]
    assert closed["state"] == "closed" and closed["closed_by"] == "Manager Person"
    # A decision after it closed is not the review's; and the review changes no more.
    decide(db, people, "manager", second, disposition="maintain")
    after = manager.get(f"/api/v1/reviews/{ref}").json()["data"]
    kept = {i["application"]["name"]: i["taken"] for i in after["agenda"]["items"]}
    assert kept["Second"]["disposition"] == "invest"
    assert after["may_run"] is False
    assert manager.post(f"/api/v1/reviews/{ref}/draw").status_code == 409
    assert (
        manager.post(f"/api/v1/reviews/{ref}/items", json={"application": first}).status_code == 409
    )
    change = {"name": "Renamed", "version": after["version"]}
    renamed = manager.patch(f"/api/v1/reviews/{ref}", json=change)
    assert renamed.status_code in (403, 422)


def test_who_may_plan_a_review(as_role: Clients, db: Database, people: People) -> None:
    # A leader plans reviews of the unit they lead, not of another.
    leader = as_role("leader")
    said = leader.post("/api/v1/reviews", json={
        "name": "Cancer review", "org_unit_id": people.units["CANCER"],
        "held_on": TODAY.isoformat(),
    })  # fmt: skip
    assert said.status_code == 403
    listed = as_role("member").get("/api/v1/reviews").json()["data"]
    assert listed == []
    ref = plan(as_role("manager"), people, unit="BIH")
    listed = as_role("member").get("/api/v1/reviews").json()["data"]
    assert [(r["ref"], r["state"], r["items"]) for r in listed] == [(ref, "planned", 0)]


def test_a_review_coming_up_is_on_home_for_those_who_run_it(
    as_role: Clients, db: Database, people: People
) -> None:
    add_app(db, people, name="Undecided")
    leader = as_role("leader")
    soon = plan(leader, people, held_on=(TODAY + timedelta(days=5)).isoformat())
    plan(leader, people, held_on=(TODAY + timedelta(days=60)).isoformat())  # not yet
    leader.post(f"/api/v1/reviews/{soon}/draw")
    items = [i for i in leader.get("/api/v1/home").json()["data"]["items"] if i["kind"] == "review"]
    assert [(i["href"], i["severity"]) for i in items] == [(f"/reviews/{soon}", "warning")]
    assert "1 on the agenda" in items[0]["text"]
    member = as_role("member").get("/api/v1/home").json()["data"]["items"]
    assert not [i for i in member if i["kind"] == "review"]
