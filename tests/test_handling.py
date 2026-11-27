"""The evidence other processes ask for: who handles a class of data, links to other systems,
and every change in one place (slice 7 of wave 2)."""

from __future__ import annotations

import copy
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from appwren.core.errors import Invalid
from appwren.db.engine import Database
from appwren.inventory import parts, records
from appwren.inventory.registry import APPLICATION, COMPONENT, HOSTING_PLATFORM, TECHNOLOGY
from appwren.program import packs
from tests.people import ME, ROLES, People
from tests.test_costs import contract
from tests.test_hosting import deploy
from tests.test_interfaces import add_interface
from tests.test_inventory import add_app, shared, who
from tests.test_lifecycle import day

Clients = Callable[[str | None], TestClient]


def test_who_handles_a_class_of_data(as_role: Clients, db: Database, people: People) -> None:
    python = shared(db, TECHNOLOGY, name="Python", kind="language")
    room = shared(db, HOSTING_PLATFORM, name="Data center", kind="data_center")
    with db.write(ME.actor) as session:
        parts.set_releases(
            session, ME, records.load(session, ME, TECHNOLOGY, python),
            [{"cycle": "3.9", "support_ends": day(-10)}],
        )  # fmt: skip
    clinic = add_app(
        db, people, name="Clinic", data_classes=["health", "personal"], sign_in="sso_mfa",
        tier="1", sourcing="built_here", hosting="on_premises",
    )  # fmt: skip
    hosted = add_app(
        db, people, role="manager", unit="CANCER", name="Hosted", data_classes=["health"],
        sourcing="saas", hosting="vendor_cloud", sign_in="local",
    )  # fmt: skip
    secret = add_app(
        db, people, role="manager", unit="CANCER", name="Secret", data_classes=["health"],
        restricted=True,
    )  # fmt: skip
    add_app(db, people, name="Elsewhere", data_classes=["internal"])
    add_app(db, people, name="Gone", data_classes=["health"], lifecycle="retired")
    with db.write(ME.actor) as session:
        component = records.create(
            session, ME, COMPONENT, {"name": "API", "application_id": clinic, "kind": "service"}
        )
        parts.set_technologies(session, ME, component, [{"technology": python, "release": "3.9"}])
    manager = who(db, people, "manager")
    deploy(db, manager, clinic, room)
    add_interface(db, manager, clinic, hosted, data_classes=["health"])
    contract(db, [(hosted, None)], data_agreement="missing")
    for role in ROLES:
        client = as_role(role)
        found = client.get("/api/v1/data-handling", params={"data_class": "health"}).json()["data"]
        rows = {row["name"]: row for row in found["applications"]}
        # The page is the applications list narrowed by the class, for every role.
        listed = client.get(
            "/api/v1/applications", params={"data_class": "health", "status": "active"}
        ).json()["data"]
        assert sorted(rows) == sorted(r["name"] for r in listed), role
        sees_all = role in ("manager", "architect", "auditor", "admin")
        assert ("Secret" in rows) is sees_all and "Gone" not in rows and "Elsewhere" not in rows
        counts = {c["key"]: c["applications"] for c in found["classes"]}
        assert counts["health"] == len(rows) and counts["internal"] == 1
        ours = rows["Clinic"]
        assert ours["accountable"] == ["Steward Person"] and ours["platforms"] == ["Data center"]
        assert ours["technologies"] == [{"name": "Python", "release": "3.9", "support": "ended"}]
        assert (ours["support"], ours["sends"], ours["receives"]) == ("ended", 1, 0)
        # What a reader may not see of an application is withheld, as on its record.
        near = role != "member"  # everyone else here has a role over Immunology, or reads all
        assert ours["sign_in"] == ("sso_mfa" if near else "withheld"), role
        theirs = rows["Hosted"]
        assert theirs["sign_in"] == ("local" if sees_all else "withheld")
        assert theirs["data_agreement"] == ("missing" if sees_all else "withheld")
        assert (theirs["receives"], theirs["technologies"], theirs["support"]) == (1, [], None)
        assert found["unsupported"] == 1 and found["no_agreement"] == (1 if sees_all else 0)
        exported = client.get(
            "/api/v1/exports/data-handling", params={"data_class": "health", "format": "json"}
        ).json()["rows"]
        assert [row["name"] for row in exported] == [row["name"] for row in found["applications"]]
        assert next(r for r in exported if r["name"] == "Clinic")["technologies"] == [
            "Python 3.9 (ended)"
        ]
    assert (
        as_role("member")
        .get("/api/v1/data-handling", params={"data_class": "nonsense"})
        .status_code
        == 422
    )
    assert secret  # never named to those who may not see it


def test_every_change_in_one_place(as_role: Clients, db: Database, people: People) -> None:
    app = add_app(db, people, name="Tracker")
    steward = as_role("steward")
    record = steward.get(f"/api/v1/applications/{app}").json()["data"]
    steward.patch(f"/api/v1/applications/{app}", json={"version": record["version"], "users": 40})
    steward.get("/api/v1/exports/applications", params={"format": "csv"})
    for role in ROLES:
        answer = as_role(role).get("/api/v1/history")
        assert answer.status_code == (200 if role in ("manager", "auditor", "admin") else 403), role
    auditor = as_role("auditor")
    told = auditor.get("/api/v1/history", params={"kind": "records"}).json()["data"]["entries"]
    assert any(e["title"] == "Added this application" and e["record"]["ref"] == app for e in told)
    changed = next(e for e in told if e["lines"])
    assert changed["actor"] == "Steward Person" and changed["lines"][0]["after"] == 40
    # What is not a change to a record is one choice away: an export says what was taken.
    other = auditor.get("/api/v1/history", params={"kind": "other"}).json()["data"]["entries"]
    assert any(e["title"] == "Exported applications as CSV: 1 rows" for e in other)
    about = auditor.get("/api/v1/history", params={"about": app}).json()["data"]["entries"]
    assert about and all(e["record"]["ref"] == app for e in about)
    # By one person: the member changed no record, and signed in, which is on record too.
    member = {"actor": people.accounts["member"]}
    by = auditor.get("/api/v1/history", params={**member, "kind": "records"})
    assert by.json()["data"]["entries"] == []
    signed = auditor.get("/api/v1/history", params={**member, "kind": "other"})
    assert {e["actor"] for e in signed.json()["data"]["entries"]} == {"Member Person"}
    assert auditor.get("/api/v1/history", params={"since": "soon"}).status_code == 422
    assert auditor.get("/api/v1/history", params={"about": "APP-9999"}).status_code == 404


def test_an_identifier_elsewhere_is_a_link_where_its_system_has_a_pattern(
    db: Database, people: People
) -> None:
    with db.write(ME.actor) as session:
        pack = packs.export(session)
    systems = pack["vocabularies"]["external_systems"]
    next(s for s in systems if s["key"] == "repository")["url"] = "https://code.example.org/{id}"
    with db.write(ME.actor) as session:
        packs.load(session, ME, pack, dry_run=False)
    app = add_app(db, people, name="Tracker")
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, app)
        records.update(
            session, ME, APPLICATION, record,
            {"external_refs": [
                {"system": "repository", "value": "labs/tracker app"},
                {"system": "ticket_queue", "value": "TRK"},
            ]},
            version=record.version,
        )  # fmt: skip
    with db.read() as session:
        shown = records.detail(
            session, ME, APPLICATION, records.load(session, ME, APPLICATION, app)
        )
        links = {item["system"]: item["url"] for item in shown["external_refs"]}
        # The identifier is made safe for an address; a system with no pattern has no link.
        assert links == {
            "repository": "https://code.example.org/labs%2Ftracker%20app",
            "ticket_queue": None,
        }
    # A pattern can only make an https address, and must say where the identifier goes.
    for bad in (
        "http://code.example.org/{id}",
        "javascript:alert({id})",
        "https://code.example.org/",
    ):
        broken = copy.deepcopy(pack)
        next(s for s in broken["vocabularies"]["external_systems"] if s["key"] == "repository")[
            "url"
        ] = bad
        with pytest.raises(Invalid) as refused, db.write(ME.actor) as session:
            packs.load(session, ME, broken, dry_run=True)
        assert "address pattern for repository" in str(refused.value.errors)
