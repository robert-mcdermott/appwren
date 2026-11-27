"""The picture around a record, and what breaks if an application goes (slice 2 of wave 2)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.inventory import applications, links, parts, records
from appwren.inventory.registry import APPLICATION, CAPABILITY, COMPONENT, TECHNOLOGY, VENDOR
from appwren.landscape import graph
from tests.people import ME, People
from tests.test_interfaces import add_interface
from tests.test_inventory import add_app, shared, who

Clients = Callable[[str | None], TestClient]


def depend(db: Database, source: str, target: str) -> None:
    with db.write(ME.actor) as session:
        links.add(
            session, ME, APPLICATION, records.load(session, ME, APPLICATION, source),
            "depends_on", APPLICATION, records.load(session, ME, APPLICATION, target),
        )  # fmt: skip


def serve(db: Database, app: str, capability: str, primary: bool = False) -> None:
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, app)
        applications.set_capabilities(
            session, ME, record, [{"capability": capability, "is_primary": primary}]
        )


def groups(answer: dict) -> dict[str, list[str]]:
    return {g["key"]: [r["name"] for r in g["records"]] for g in answer["groups"]}


def test_the_picture_gathers_everything_joined_to_a_record(
    as_role: Clients, db: Database, people: People
) -> None:
    vendor = shared(db, VENDOR, name="Larkfield", kind="software_vendor")
    python = shared(db, TECHNOLOGY, name="Python", kind="language", vendor_id=vendor)
    tracking = shared(db, CAPABILITY, name="Sample tracking")
    tracker = add_app(db, people, name="Tracker", vendor_id=vendor)
    warehouse = add_app(db, people, name="Warehouse")
    portal = add_app(db, people, name="Portal")
    old = add_app(db, people, name="Old Tracker", lifecycle="retired", successor_id=tracker)
    manager = who(db, people, "manager")
    add_interface(db, manager, tracker, warehouse)
    add_interface(db, manager, portal, tracker)
    depend(db, portal, tracker)
    serve(db, tracker, tracking, primary=True)
    with db.write(ME.actor) as session:
        component = records.create(
            session, ME, COMPONENT, {"name": "API", "application_id": tracker, "kind": "service"}
        )
        parts.set_technologies(session, ME, component, [{"technology": python}])
        part = component.ref
    answer = as_role("member").get(f"/api/v1/graph/{tracker}").json()["data"]
    assert answer["center"]["ref"] == tracker and answer["hidden"] == 0
    assert groups(answer) == {
        "depends_on:in": ["Portal"],
        "sends": ["Warehouse"],
        "receives": ["Portal"],
        "serves": ["Sample tracking"],
        "made_of": ["API"],
        "built_on": ["Python"],
        "supplied_by": ["Larkfield"],
        "replaces": ["Old Tracker"],
    }
    assert answer["count"] == 8
    # Every kind of record has a picture, seen from its own side.
    member = as_role("member")
    assert groups(member.get(f"/api/v1/graph/{part}").json()["data"]) == {
        "part_of": ["Tracker"], "built_on": ["Python"],
    }  # fmt: skip
    assert groups(member.get(f"/api/v1/graph/{python}").json()["data"]) == {
        "used_by": ["API"], "supplied_by": ["Larkfield"],
    }  # fmt: skip
    assert groups(member.get(f"/api/v1/graph/{vendor}").json()["data"]) == {
        "supplies": ["Tracker"], "makes": ["Python"],
    }  # fmt: skip
    assert groups(member.get(f"/api/v1/graph/{tracking}").json()["data"]) == {
        "served_by": ["Tracker"]
    }
    assert groups(member.get("/api/v1/graph/INT-0001").json()["data"]) == {
        "from": ["Tracker"], "to": ["Warehouse"],
    }  # fmt: skip
    assert groups(member.get(f"/api/v1/graph/{old}").json()["data"]) == {"replaced_by": ["Tracker"]}
    assert member.get("/api/v1/graph/APP-9999").status_code == 404
    assert member.get("/api/v1/graph/nonsense").status_code == 404


def test_the_picture_counts_what_the_reader_may_not_see(
    as_role: Clients, db: Database, people: People
) -> None:
    ours = add_app(db, people, name="Ours")
    secret = add_app(db, people, role="manager", unit="CANCER", name="Secret", restricted=True)
    add_interface(db, who(db, people, "manager"), ours, secret)
    depend(db, secret, ours)
    member = as_role("member").get(f"/api/v1/graph/{ours}").json()["data"]
    assert member["groups"] == [] and member["count"] == 0 and member["hidden"] == 2
    manager = as_role("manager").get(f"/api/v1/graph/{ours}").json()["data"]
    assert groups(manager) == {"depends_on:in": ["Secret"], "sends": ["Secret"]}
    assert as_role("member").get(f"/api/v1/graph/{secret}").status_code == 404
    # Impact names nothing hidden either: it counts it.
    impact = as_role("member").get(f"/api/v1/applications/{ours}/impact").json()["data"]
    assert impact["direct"] == [] and impact["hidden"] == 1 and impact["interfaces"] == []
    assert as_role("member").get(f"/api/v1/applications/{secret}/impact").status_code == 404


def test_what_breaks_if_an_application_goes(db: Database, people: People) -> None:
    tracking = shared(db, CAPABILITY, name="Sample tracking")
    surveys = shared(db, CAPABILITY, name="Surveys")
    tracker = add_app(db, people, name="Tracker", users=300, records_retention=True)
    warehouse = add_app(db, people, name="Warehouse", users=40)
    dashboards = add_app(db, people, name="Dashboards", users=25)
    reports = add_app(db, people, name="Reports", users=10)
    other = add_app(db, people, name="Other Surveys", users=5)
    gone = add_app(db, people, name="Gone", lifecycle="retired", users=1000)
    manager = who(db, people, "manager")
    add_interface(db, manager, tracker, warehouse)  # the warehouse relies on the tracker
    add_interface(db, manager, warehouse, dashboards)  # and the dashboards on the warehouse
    depend(db, reports, dashboards)  # three rings out
    depend(db, gone, tracker)  # a retired application relies on nothing
    depend(db, tracker, warehouse)  # a loop must not run forever
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, tracker)
        applications.set_capabilities(
            session, ME, record,
            [
                {"capability": tracking, "is_primary": True},
                {"capability": surveys, "is_primary": True},
            ],
        )  # fmt: skip
        applications.set_units(session, ME, record, [people.units["CANCER"]])
    serve(db, other, surveys)
    with db.read() as session:
        record = records.load(session, ME, APPLICATION, tracker)
        found = graph.impact(session, ME, record)
    assert [r["name"] for r in found["direct"]] == ["Warehouse"]
    assert [r["name"] for r in found["beyond"]] == ["Dashboards", "Reports"]
    assert found["people"] == 300 + 40 + 25 + 10 and found["hidden"] == 0
    assert [r["name"] for r in found["interfaces"]] == ["Nightly samples"]
    assert [c["name"] for c in found["capabilities_left"]] == ["Sample tracking"]
    weakened = found["capabilities_weakened"]
    assert [c["name"] for c in weakened] == ["Surveys"]
    assert [o["name"] for o in weakened[0]["others"]] == ["Other Surveys"]
    assert [u["name"] for u in found["units"]] == ["Cancer Biology"]
    assert found["records_retention"] is True and found["has_components"] is False
