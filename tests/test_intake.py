"""Intake: a request for something new, checked against what is already there (slice 3 of
wave 5)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.inventory import applications, records
from appwren.inventory.registry import APPLICATION, CAPABILITY
from tests.people import ME, People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def capability(db: Database, name: str = "Sample management") -> str:
    with db.write(ME.actor) as session:
        return records.create(session, ME, CAPABILITY, {"name": name}).ref


def serves(db: Database, app: str, cap: str, primary: bool = False) -> None:
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, app)
        applications.set_capabilities(session, ME, record,
                                      [{"capability": cap, "is_primary": primary}])  # fmt: skip


def ask(client: TestClient, people: People, cap: str, **values: object) -> str:
    said = client.post("/api/v1/requests", json={
        "name": "Sample Tracker for the Hale Lab", "org_unit_id": people.units["HALE"],
        "capability_id": cap, "summary": "We need to know where every sample is.",
        "users_expected": 12, **values,
    })  # fmt: skip
    assert said.status_code == 201, said.text
    return said.json()["data"]["ref"]


def test_a_request_shows_what_already_serves_the_need(
    as_role: Clients, db: Database, people: People
) -> None:
    cap = capability(db)
    first = add_app(db, people, name="Freezer Inventory")
    second = add_app(db, people, name="Biobank Catalog")
    secret = add_app(db, people, name="Secret Samples", restricted=True)
    serves(db, first, cap, primary=True)
    serves(db, second, cap)
    serves(db, secret, cap)
    add_app(db, people, name="Sample Tracker")  # named like it, not serving it
    member = as_role("member")
    ref = ask(member, people, cap, name="Sample tracker")
    shown = member.get(f"/api/v1/requests/{ref}").json()["data"]
    assert shown["state"] == "submitted" and shown["requested_by"]["name"] == "Member Person"
    assert [(a["name"], a["is_primary"]) for a in shown["serving"]] == [
        ("Freezer Inventory", True),
        ("Biobank Catalog", False),
    ]  # the secret one is not shown
    assert "Sample Tracker" in [a["name"] for a in shown["similar"]]
    # The member who asked may change the request; only keepers weigh and end it.
    assert member.put(f"/api/v1/requests/{ref}/options", json={"options": []}).status_code == 403
    assert member.post(f"/api/v1/requests/{ref}/decline", json={"reason": "x"}).status_code == 403


def test_a_request_is_weighed_and_ends_once(as_role: Clients, db: Database, people: People) -> None:
    cap = capability(db)
    existing = add_app(db, people, name="Freezer Inventory")
    serves(db, existing, cap, primary=True)
    member, steward = as_role("member"), as_role("steward")
    ref = ask(member, people, cap)
    options = steward.put(f"/api/v1/requests/{ref}/options", json={"options": [
        {"approach": "reuse", "application": existing, "fit": 3, "notes": "Does most of it"},
        {"approach": "buy", "name": "A hosted tracker", "annual_cost": 12000, "fit": 5},
        {"approach": "build", "name": "Built here", "fit": 4},
    ]})  # fmt: skip
    assert options.status_code == 200, options.text
    shown = options.json()["data"]
    assert shown["state"] == "evaluating"
    assert [(o["approach"], o["name"]) for o in shown["options"]] == [
        ("reuse", "Freezer Inventory"),
        ("buy", "A hosted tracker"),
        ("build", "Built here"),
    ]
    bad = steward.put(f"/api/v1/requests/{ref}/options", json={"options": [
        {"approach": "reuse"}, {"approach": "steal", "name": "x"}]})  # fmt: skip
    assert bad.status_code == 422
    assert steward.post(f"/api/v1/requests/{ref}/approve", json={"reason": ""}).status_code == 422
    approved = steward.post(f"/api/v1/requests/{ref}/approve",
                            json={"reason": "Nothing on record tracks samples in transit.",
                                  "name": "Hale Sample Tracker"})  # fmt: skip
    assert approved.status_code == 200, approved.text
    ended = approved.json()["data"]
    assert ended["state"] == "approved" and ended["outcome"]["by"] == "Steward Person"
    new_ref = ended["outcome"]["application"]["ref"]
    app = steward.get(f"/api/v1/applications/{new_ref}").json()["data"]
    assert (app["name"], app["lifecycle"], app["users"]) == ("Hale Sample Tracker", "proposed", 12)
    assert [c["ref"] for c in app["capabilities"]] == [cap]
    # It ends once.
    for path, body in (("approve", {"reason": "Again"}), ("decline", {"reason": "No"}),
                       ("meet", {"reason": "x", "application": existing})):  # fmt: skip
        assert steward.post(f"/api/v1/requests/{ref}/{path}", json=body).status_code == 409
    listed = steward.get("/api/v1/applications", params={"q": "Hale Sample"}).json()["data"]
    assert len(listed) == 1
    change = {"version": ended["version"], "name": "Renamed"}
    assert member.patch(f"/api/v1/requests/{ref}", json=change).status_code in (403, 422)


def test_a_request_met_by_what_is_there_or_declined(
    as_role: Clients, db: Database, people: People
) -> None:
    cap = capability(db)
    existing = add_app(db, people, name="Freezer Inventory")
    steward = as_role("steward")
    met = ask(as_role("member"), people, cap)
    body = {"application": existing, "reason": "It does this already."}
    done = steward.post(f"/api/v1/requests/{met}/meet", json=body)
    assert done.json()["data"]["outcome"]["application"]["ref"] == existing
    declined = ask(as_role("member"), people, cap, name="Something nobody needs")
    said = steward.post(f"/api/v1/requests/{declined}/decline", json={"reason": "Not a need."})
    assert said.json()["data"]["state"] == "declined"
    states = {r["ref"]: r["state"] for r in steward.get("/api/v1/requests").json()["data"]}
    assert states == {met: "met", declined: "declined"}
