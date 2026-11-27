"""Capabilities served more than once, and the capability map measured (slice 5 of wave 2)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.inventory import applications, records
from appwren.inventory.registry import APPLICATION, CAPABILITY
from tests.people import ME, ROLES, People
from tests.test_graph import serve
from tests.test_inventory import add_app, shared

Clients = Callable[[str | None], TestClient]


def test_overlap_lists_capabilities_served_more_than_once(
    as_role: Clients, db: Database, people: People
) -> None:
    surveys = shared(db, CAPABILITY, name="Surveys")
    tracking = shared(db, CAPABILITY, name="Tracking")
    hub = add_app(db, people, name="Hub", users=900, annual_cost=40000)
    old = add_app(db, people, name="Old", users=60, annual_cost=4000)
    secret = add_app(
        db, people, role="manager", unit="CANCER", name="Secret", restricted=True, users=10,
        annual_cost=1000,
    )  # fmt: skip
    gone = add_app(db, people, name="Gone", lifecycle="retired")
    alone = add_app(db, people, name="Alone")
    serve(db, hub, surveys, primary=True)
    for ref in (old, secret, gone):
        serve(db, ref, surveys)
    serve(db, alone, tracking)
    for role in ROLES:
        client = as_role(role)
        found = client.get("/api/v1/overlap").json()["data"]
        # One capability is served more than once; a retired application serves nothing.
        assert [c["name"] for c in found["capabilities"]] == ["Surveys"], role
        item = found["capabilities"][0]
        sees_secret = role in ("manager", "architect", "auditor", "admin")
        names = [a["name"] for a in item["applications"]]
        assert names == (["Hub", "Old", "Secret"] if sees_secret else ["Hub", "Old"]), role
        assert item["primary"] == hub and item["applications"][0]["is_primary"] is True
        # The page's applications are the portfolio list's, for the same filters.
        listed = client.get("/api/v1/portfolio", params=item["filters"]).json()["data"]
        assert sorted(a["ref"] for a in item["applications"]) == sorted(r["ref"] for r in listed)
        assert found["applications"] == len(names) and found["unnamed"] == 0
        assert item["users"] == (970 if sees_secret else 960)
        # A total is given whole or not at all.
        sees_cost = role != "member"
        expected = (45000 if sees_secret else 44000) if sees_cost else None
        assert item["annual_cost"] == expected, role
        if not sees_cost:
            assert {a["annual_cost"] for a in item["applications"]} == {"withheld"}
    narrowed = as_role("manager").get("/api/v1/overlap", params={"unit": people.units["CANCER"]})
    assert narrowed.json()["data"]["capabilities"] == []  # only one of them is in that unit


def test_the_map_is_measured_over_what_serves_each_capability(
    as_role: Clients, db: Database, people: People
) -> None:
    research = shared(db, CAPABILITY, name="Research")
    surveys = shared(db, CAPABILITY, name="Surveys", parent_id=research)
    tracking = shared(db, CAPABILITY, name="Tracking", parent_id=research)
    empty = shared(db, CAPABILITY, name="Nothing yet", parent_id=research)
    hub = add_app(
        db, people, name="Hub", tier="1", users=900, sign_in="sso_mfa", monitoring="on_call"
    )
    old = add_app(db, people, name="Old", tier="5", users=5, sign_in="shared", monitoring="none")
    with db.write(ME.actor) as session:  # the hub serves two capabilities, and leads one
        applications.set_capabilities(
            session, ME, records.load(session, ME, APPLICATION, hub),
            [{"capability": surveys, "is_primary": True}, {"capability": tracking}],
        )  # fmt: skip
    serve(db, old, surveys)
    tree = as_role("member").get("/api/v1/capability-heat").json()["data"]
    root = next(node for node in tree if node["ref"] == research)
    by_name = {node["name"]: node for node in root["children"]}
    assert by_name["Surveys"]["measures"]["applications"] == 2
    assert by_name["Tracking"]["measures"]["applications"] == 1
    assert by_name["Nothing yet"]["measures"] == {
        "applications": 0, "business_value": None, "technical_health": None,
        "cost_burden": None, "risk_exposure": None, "confidence": None, "weakest_health": None,
    }  # fmt: skip
    # The broader capability counts each application beneath it once.
    assert root["measures"]["applications"] == 2
    both = by_name["Surveys"]["measures"]
    scores = [a["scores"]["technical_health"] for a in by_name["Surveys"]["applications"]]
    assert both["weakest_health"] == min(scores)
    assert both["technical_health"] == round(sum(scores) / 2, 1)
    # Each capability's figure opens the list it counts.
    listed = as_role("member").get("/api/v1/portfolio", params=by_name["Surveys"]["filters"])
    assert len(listed.json()["data"]) == 2
    assert empty  # a capability nothing serves is still on the map
