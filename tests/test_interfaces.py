"""Interfaces and data flows: what passes between applications, who may see and keep it, and
what it means for what depends on what (slice 1 of wave 2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from appwren import assessment
from appwren.core.errors import Invalid, NotFound, PermissionDenied
from appwren.db.engine import Database
from appwren.inventory import history, links, records
from appwren.inventory.registry import APPLICATION, INTERFACE
from appwren.landscape import interfaces
from tests.people import ME, People
from tests.test_inventory import add_app, who

Clients = Callable[[str | None], TestClient]


def add_interface(db: Database, principal: Any, source: str, target: str, **values: Any) -> str:
    with db.write(principal.actor) as session:
        record = records.create(
            session,
            principal,
            INTERFACE,
            {"name": "Nightly samples", "source_id": source, "target_id": target,
             "method": "extract_load", **values},
        )  # fmt: skip
        return record.ref


def test_an_interface_joins_two_applications_and_shows_on_both(
    as_role: Clients, db: Database, people: People
) -> None:
    tracker = add_app(db, people, name="Tracker", data_classes=["identifiable_research"])
    warehouse = add_app(db, people, role="manager", unit="CANCER", name="Warehouse")
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/interfaces",
        json={"name": "Nightly samples", "source_id": tracker, "target_id": warehouse,
              "method": "extract_load", "frequency": "daily",
              "data_classes": ["identifiable_research"], "owner_id": people.accounts["steward"]},
    )  # fmt: skip
    assert made.status_code == 201, made.text
    shown = made.json()["data"]
    assert shown["ref"] == "INT-0001"
    assert (shown["source"]["ref"], shown["target"]["ref"]) == (tracker, warehouse)
    assert shown["owner"]["name"] == "Steward Person"
    # The warehouse's record does not say it holds what it is sent.
    assert shown["undeclared"] == ["identifiable_research"]
    for ref in (tracker, warehouse):
        found = as_role("member").get("/api/v1/interfaces", params={"application": ref})
        assert [row["ref"] for row in found.json()["data"]] == ["INT-0001"]
    # Whoever keeps either end keeps the interface; nobody else does.
    assert (
        as_role("member")
        .patch("/api/v1/interfaces/INT-0001", json={"version": 1, "frequency": "weekly"})
        .status_code
        == 403
    )
    changed = steward.patch(
        "/api/v1/interfaces/INT-0001", json={"version": 1, "frequency": "weekly"}
    )
    assert changed.status_code == 200 and changed.json()["data"]["frequency"] == "weekly"
    with db.read() as session:
        record = records.load(session, ME, INTERFACE, "INT-0001")
        story = history.for_record(session, INTERFACE, record)
        assert "Weekly" in str(story)


def test_who_may_add_an_interface(db: Database, people: People) -> None:
    ours = add_app(db, people, name="Ours")  # in the Hale Lab, under the steward's Immunology
    theirs = add_app(db, people, role="manager", unit="CANCER", name="Theirs")
    other = add_app(db, people, role="manager", unit="CANCER", name="Other")
    assert add_interface(db, who(db, people, "steward"), ours, theirs) == "INT-0001"
    with pytest.raises(PermissionDenied):  # the steward keeps neither end
        add_interface(db, who(db, people, "steward"), theirs, other)
    with pytest.raises(PermissionDenied):
        add_interface(db, who(db, people, "member"), ours, theirs)
    with pytest.raises(Invalid) as same:
        add_interface(db, who(db, people, "manager"), ours, ours)
    assert "two different applications" in str(same.value.errors)
    with pytest.raises(Invalid):
        add_interface(db, who(db, people, "manager"), ours, theirs, method="carrier_pigeon")


def test_a_restricted_application_hides_its_interfaces(
    as_role: Clients, db: Database, people: People
) -> None:
    ours = add_app(db, people, name="Ours", data_classes=["health"])
    secret = add_app(
        db, people, role="manager", unit="CANCER", name="Secret", restricted=True,
        data_classes=["health"],
    )  # fmt: skip
    open_one = add_app(db, people, role="manager", unit="CANCER", name="Open")
    manager = who(db, people, "manager")
    hidden = add_interface(db, manager, ours, secret, data_classes=["health"])
    seen = add_interface(db, manager, ours, open_one, data_classes=["health"])
    # The steward of Immunology keeps one end and still may not know the other exists.
    for role in ("member", "steward", "leader"):
        client = as_role(role)
        listed = client.get("/api/v1/interfaces").json()
        assert [row["ref"] for row in listed["data"]] == [seen] and listed["meta"]["total"] == 1
        assert client.get(f"/api/v1/interfaces/{hidden}").status_code == 404
        flows = client.get("/api/v1/data-flows", params={"data_class": "health"}).json()["data"]
        assert [row["ref"] for row in flows["interfaces"]] == [seen]
        assert [row["name"] for row in flows["holders"]] == ["Ours"]
        assert flows["total"] == 1
        exported = client.get("/api/v1/exports/interfaces", params={"format": "json"}).json()
        assert [row["ref"] for row in exported["rows"]] == [seen]
    for role in ("manager", "auditor", "architect"):
        listed = as_role(role).get("/api/v1/interfaces").json()
        assert {row["ref"] for row in listed["data"]} == {hidden, seen}
    # Naming an application one may not see is the same as naming one that is not there.
    with pytest.raises(Invalid) as refused:
        add_interface(db, who(db, people, "steward"), ours, secret)
    assert refused.value.errors == {"target_id": f"There is no application {secret}."}
    with db.read() as session, pytest.raises(NotFound):
        records.load(session, who(db, people, "member"), INTERFACE, hidden)


def test_an_application_that_receives_data_depends_on_its_source(
    db: Database, people: People
) -> None:
    source = add_app(db, people, name="Source")
    reader = add_app(db, people, name="Reader")
    both = add_app(db, people, name="Both")
    gone = add_app(db, people, name="Gone", lifecycle="retired")
    manager = who(db, people, "manager")
    add_interface(db, manager, source, reader)
    add_interface(db, manager, source, both)
    add_interface(db, manager, source, gone)  # a retired application depends on nothing
    retired = add_interface(db, manager, source, reader, name="Old feed")
    with db.write(ME.actor) as session:
        # The same application by a link as well: it is still one dependent.
        links.add(
            session, ME, APPLICATION, records.load(session, ME, APPLICATION, both),
            "depends_on", APPLICATION, records.load(session, ME, APPLICATION, source),
        )  # fmt: skip
        old = records.load(session, ME, INTERFACE, retired)
        records.update(session, ME, INTERFACE, old, {"status": "retired"}, version=old.version)
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, source)
        value = assessment.score_one(session, app)["dimensions"]["business_value"]
        said = next(f for f in value["factors"] if f["key"] == "dependents")
        assert (said["level"], said["why"]) == (4, "2 active applications depend on it")
        assert interfaces.consumers(session, [app.id])[app.id] == {
            records.load(session, ME, APPLICATION, reader).id,
            records.load(session, ME, APPLICATION, both).id,
        }


def test_the_flow_view_follows_a_class_of_data(
    as_role: Clients, db: Database, people: People
) -> None:
    clinic = add_app(db, people, name="Clinic", data_classes=["health", "personal"])
    warehouse = add_app(db, people, name="Warehouse", data_classes=["health"])
    portal = add_app(db, people, name="Portal", data_classes=["internal"])
    manager = who(db, people, "manager")
    declared = add_interface(db, manager, clinic, warehouse, data_classes=["health", "personal"])
    undeclared = add_interface(db, manager, warehouse, portal, data_classes=["health"])
    add_interface(db, manager, portal, clinic, data_classes=["internal"])
    member = as_role("member")
    everything = member.get("/api/v1/data-flows").json()["data"]
    counts = {item["key"]: item["interfaces"] for item in everything["classes"]}
    assert (counts["health"], counts["personal"], counts["internal"], counts["public"]) == (
        2,
        1,
        1,
        0,
    )
    assert everything["interfaces"] == [] and everything["total"] == 3
    health = member.get("/api/v1/data-flows", params={"data_class": "health"}).json()["data"]
    assert {row["ref"] for row in health["interfaces"]} == {declared, undeclared}
    marks = {row["ref"]: row["undeclared"] for row in health["interfaces"]}
    assert marks == {declared: ["personal"], undeclared: ["health"]}
    assert health["undeclared"] == 1  # one interface delivers health data nobody recorded
    assert [row["name"] for row in health["holders"]] == ["Clinic", "Warehouse"]
    # The view lists exactly the interfaces the list gives for the class.
    listed = member.get("/api/v1/interfaces", params={"data_class": "health"}).json()["data"]
    assert {row["ref"] for row in listed} == {row["ref"] for row in health["interfaces"]}
    assert member.get("/api/v1/data-flows", params={"data_class": "nonsense"}).status_code == 422
    assert member.get("/api/v1/interfaces", params={"data_class": 'x" OR 1=1'}).status_code == 422
