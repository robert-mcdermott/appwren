"""Where things run: hosting platforms and deployments (slice 3 of wave 2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.inventory import records
from appwren.inventory.registry import COMPONENT, DEPLOYMENT, HOSTING_PLATFORM
from tests.people import ME, ROLES, People
from tests.test_inventory import add_app, shared, who

Clients = Callable[[str | None], TestClient]


def deploy(db: Database, principal: Any, app: str, platform: str, **values: Any) -> str:
    with db.write(principal.actor) as session:
        record = records.create(
            session, principal, DEPLOYMENT,
            {"application_id": app, "platform_id": platform, **values},
        )  # fmt: skip
        return record.ref


def test_a_deployment_says_what_runs_where(as_role: Clients, db: Database, people: People) -> None:
    room = shared(db, HOSTING_PLATFORM, name="Main data center", kind="data_center")
    tracker = add_app(db, people, name="Tracker")
    other = add_app(db, people, name="Other")
    with db.write(ME.actor) as session:
        api = records.create(
            session,
            ME,
            COMPONENT,
            {"name": "Tracker API", "application_id": tracker, "kind": "service"},
        ).ref
        stray = records.create(
            session,
            ME,
            COMPONENT,
            {"name": "Other DB", "application_id": other, "kind": "database"},
        ).ref
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/deployments",
        json={"application_id": tracker, "component_id": api, "platform_id": room,
              "url": "https://tracker.bramblewood.example"},
    )  # fmt: skip
    assert made.status_code == 201, made.text
    shown = made.json()["data"]
    # Named for what runs and where, in production unless it says otherwise.
    assert (shown["ref"], shown["name"], shown["environment"]) == (
        "DEP-0001", "Tracker API, production", "production",
    )  # fmt: skip
    assert shown["application"]["ref"] == tracker and shown["platform"]["ref"] == room
    whole = steward.post(
        "/api/v1/deployments",
        json={"application_id": tracker, "platform_id": room, "environment": "test"},
    ).json()["data"]
    assert whole["name"] == "Tracker, test" and whole["component"] is None
    # A component belongs to its own application's deployments only.
    wrong = steward.post(
        "/api/v1/deployments",
        json={"application_id": tracker, "component_id": stray, "platform_id": room},
    )
    assert wrong.status_code == 422 and "component_id" in str(wrong.json()["errors"])
    listed = as_role("member").get("/api/v1/deployments", params={"application": tracker})
    assert [row["ref"] for row in listed.json()["data"]] == ["DEP-0002", "DEP-0001"]
    # The pictures: the application runs on the platform, and the platform hosts it.
    around = as_role("member").get(f"/api/v1/graph/{tracker}").json()["data"]
    assert [g["records"][0]["name"] for g in around["groups"] if g["key"] == "runs_on"] == [
        "Main data center"
    ]
    hosts = as_role("member").get(f"/api/v1/graph/{room}").json()["data"]
    assert [r["name"] for g in hosts["groups"] if g["key"] == "hosts" for r in g["records"]] == [
        "Tracker"
    ]


def test_who_keeps_platforms_and_deployments(db: Database, people: People) -> None:
    for role, allowed in [
        ("architect", True),
        ("manager", True),
        ("steward", False),
        ("member", False),
    ]:
        principal = who(db, people, role)
        try:
            with db.write(principal.actor) as session:
                records.create(
                    session, principal, HOSTING_PLATFORM, {"name": f"By {role}", "kind": "cluster"}
                )
            assert allowed, role
        except PermissionDenied:
            assert not allowed, role
    room = shared(db, HOSTING_PLATFORM, name="Room", kind="data_center")
    ours = add_app(db, people, name="Ours")
    theirs = add_app(db, people, role="manager", unit="CANCER", name="Theirs")
    assert deploy(db, who(db, people, "steward"), ours, room).startswith("DEP-")
    with pytest.raises(PermissionDenied):
        deploy(db, who(db, people, "steward"), theirs, room)
    with pytest.raises(PermissionDenied):
        deploy(db, who(db, people, "member"), ours, room)
    with pytest.raises(Invalid):
        deploy(db, who(db, people, "manager"), ours, room, environment="the moon")
    with db.write(ME.actor) as session:  # a retired platform takes nothing new
        old = records.load(session, ME, HOSTING_PLATFORM, room)
        records.update(
            session, ME, HOSTING_PLATFORM, old, {"status": "retired"}, version=old.version
        )
    with pytest.raises(Invalid) as retired:
        deploy(db, who(db, people, "manager"), ours, room)
    assert "retired" in str(retired.value.errors)


def test_a_platform_shows_only_what_the_reader_may_see(
    as_role: Clients, db: Database, people: People
) -> None:
    cloud = shared(db, HOSTING_PLATFORM, name="Cloud", kind="cloud_account")
    ours = add_app(db, people, name="Ours")
    secret = add_app(db, people, role="manager", unit="CANCER", name="Secret", restricted=True)
    manager = who(db, people, "manager")
    seen = deploy(db, manager, ours, cloud)
    deploy(db, manager, ours, cloud, environment="staging")
    hidden = deploy(db, manager, secret, cloud)
    for role in ROLES:
        client = as_role(role)
        page = client.get(f"/api/v1/hosting-platforms/{cloud}").json()["data"]
        listed = client.get("/api/v1/deployments", params={"platform_id": 1, "status": "active"})
        # The platform's page is the deployments list, narrowed by it, for every role.
        assert {r["ref"] for r in page["deployments"]} == {r["ref"] for r in listed.json()["data"]}
        row = client.get("/api/v1/hosting-platforms").json()["data"][0]
        sees_all = role in ("manager", "architect", "auditor", "admin")
        assert (row["deployment_count"], row["application_count"]) == (
            (3, 2) if sees_all else (2, 1)
        )
        assert page["application_count"] == (2 if sees_all else 1)
        assert page["by_environment"] == (
            {"production": 2, "staging": 1} if sees_all else {"production": 1, "staging": 1}
        )
        assert (hidden in {r["ref"] for r in page["deployments"]}) is sees_all
        assert client.get(f"/api/v1/deployments/{hidden}").status_code == (200 if sees_all else 404)
        assert client.get(f"/api/v1/deployments/{seen}").status_code == 200
        exported = client.get("/api/v1/exports/deployments", params={"format": "json"}).json()
        assert len(exported["rows"]) == (3 if sees_all else 2)
