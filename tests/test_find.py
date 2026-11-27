"""Finding and tidying: one search that returns only what its searcher may open, saved views,
likely duplicates when adding an application, and contested scores (CUR-08, INV-15, SCR-13)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Notice
from appwren.inventory import duplicates, find, records
from appwren.inventory.registry import APPLICATION, CONTRACT, TYPES, VENDOR
from appwren.oversight import contests, views
from tests.people import ME, ROLES, People
from tests.test_decisions import GOOD, who

Clients = Callable[[str | None], TestClient]


def add(
    db: Database,
    people: People,
    name: str,
    unit: str = "HALE",
    owner: str = "member",
    **values: Any,
) -> str:
    from appwren import assessment

    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION,
            {"name": name, "org_unit_id": people.units[unit], "tier": "3", "sourcing": "saas",
             **values},
            accountable=people.accounts[owner],
        )  # fmt: skip
        assessment.record(session, ME, app, GOOD)
        return app.ref


@pytest.fixture
def landscape(db: Database, people: People) -> dict[str, str]:
    with db.write(ME.actor) as session:
        vendor = records.create(
            session, ME, VENDOR, {"name": "Tracker Labs", "kind": "software_vendor"}
        )
        contract = records.create(
            session, ME, CONTRACT,
            {"name": "Tracker licenses", "vendor_id": vendor.id,
             "owner_id": people.accounts["architect"]},
        )  # fmt: skip
        vendor_ref, contract_ref = vendor.ref, contract.ref
    return {
        "open": add(db, people, "Sample Tracker", vendor_id=None),
        "restricted": add(
            db, people, "Secret Tracker", unit="CANCER", owner="manager", restricted=True
        ),
        "vendor": vendor_ref,
        "contract": contract_ref,
    }


def test_a_search_never_returns_a_record_its_searcher_could_not_open(
    as_role: Clients, db: Database, people: People, landscape: dict[str, str]
) -> None:
    seen: dict[str, set[str]] = {}
    for role in ROLES:
        client = as_role(role)
        found = client.get("/api/v1/search", params={"q": "tracker"}).json()["data"]
        refs = set()
        for group in found["groups"]:
            for item in group["items"]:
                opened = client.get(f"/api/v1/{TYPES[item['type']].path}/{item['ref']}")
                assert opened.status_code == 200, (role, item["ref"])
                refs.add(item["ref"])
        seen[role] = refs
    assert landscape["restricted"] not in seen["member"]  # in Cancer Biology, not named on it
    assert landscape["restricted"] in seen["manager"]
    assert landscape["contract"] not in seen["member"]  # contracts are kept close
    assert {landscape["open"], landscape["vendor"]} <= seen["member"]


def test_the_best_answer_comes_first(
    db: Database, people: People, landscape: dict[str, str]
) -> None:
    with db.read() as session:
        found = find.everywhere(session, ME, landscape["open"].lower())
        assert found["best"] == {"type": "application", "ref": landscape["open"]}
        assert found["groups"][0]["items"][0]["ref"] == landscape["open"]
        assert find.everywhere(session, ME, "t")["groups"] == []  # too short to look


def test_a_saved_view_is_a_question_each_person_answers_for_themselves(
    db: Database, people: People
) -> None:
    member, manager = who(db, people, "member"), who(db, people, "manager")
    with db.write(member.actor) as session:
        mine = views.create(
            session, member,
            {"name": "My trackers", "path": "/applications", "query": "q=tracker&cursor=abc"},
        )  # fmt: skip
        assert mine.query == "q=tracker"  # where someone was in the list is not kept
        with pytest.raises(Invalid):
            views.create(
                session, member, {"name": "Shared", "path": "/applications", "shared": True}
            )
    with db.write(manager.actor) as session:
        shared = views.create(
            session, manager,
            {"name": "Tier 1", "path": "/applications", "query": "tier=1", "shared": True},
        )  # fmt: skip
        assert [row["name"] for row in views.listed(session, manager, "/applications")] == [
            "Tier 1"
        ]
    with db.read() as session:
        listed = views.listed(session, member, "/applications")
        assert [(row["name"], row["mine"]) for row in listed] == [
            ("My trackers", True),
            ("Tier 1", False),
        ]
        with pytest.raises(PermissionDenied):
            views.get(session, member, shared.id, to_change=True)


def test_adding_an_application_like_one_on_record_shows_it_first(
    as_role: Clients, db: Database, people: People, landscape: dict[str, str]
) -> None:
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, landscape["open"])
        records.update(
            session, ME, APPLICATION, app,
            {"aliases": ["Freezer Log"], "product": "SampleTrack Pro",
             "vendor_id": records.load(session, ME, VENDOR, landscape["vendor"]).id},
            version=app.version,
        )  # fmt: skip
    member = as_role("member")

    def similar(**params: Any) -> list[tuple[str, str]]:
        found = member.get("/api/v1/similar-applications", params=params).json()["data"]
        return [(item["ref"], item["why"]) for item in found]

    assert similar(name="Tracker, Sample") == [(landscape["open"], "The same name")]
    assert similar(name="Sample Trackr") == [(landscape["open"], "A name close to it")]
    assert similar(name="Freezer inventory") == [] and similar(name="Freezer log") == [
        (landscape["open"], "Its alias")
    ]
    assert similar(
        name="Something else", vendor=landscape["vendor"], product="Sampletrack pro"
    ) == [(landscape["open"], "The same product from the same vendor")]
    assert similar(name="Secret Tracker") == []  # restricted, and the member may not see it
    assert similar(name="Sample Tracker", **{"except": landscape["open"]}) == []
    with db.read() as session:
        assert duplicates.likeness("Data Warehouse", "Warehouse of Data") == 1.0


def test_an_owner_contests_a_factor_and_the_portfolio_team_answers(
    as_role: Clients, db: Database, people: People, landscape: dict[str, str]
) -> None:
    ref = landscape["open"]
    member = as_role("member")  # accountable for it
    raised = member.post(
        f"/api/v1/applications/{ref}/contests",
        json={"factor": "reliability", "level_claimed": 5, "note": "No outage in two years.",
              "evidence_url": "https://status.example.org/history"},
    )  # fmt: skip
    assert raised.status_code == 201
    contest = raised.json()["data"]
    assert (contest["factor_label"], contest["level_shown"], contest["level_claimed"]) == (
        "Reliability", 4, 5,
    )  # fmt: skip
    assert (
        as_role("auditor")
        .post(f"/api/v1/applications/{ref}/contests", json={"factor": "reliability", "note": "x"})
        .status_code
        == 403
    )
    bad = member.post(f"/api/v1/applications/{ref}/contests", json={"factor": "nope", "note": ""})
    assert {item["location"][0] for item in bad.json()["errors"]} == {"factor", "note"}
    waiting = as_role("architect").get("/api/v1/contests").json()["data"]
    assert [item["id"] for item in waiting] == [contest["id"]]
    home = as_role("architect").get("/api/v1/home").json()["data"]["items"]
    assert "contest" in [item["kind"] for item in home]
    leader = who(db, people, "leader")
    with db.write(leader.actor) as session, pytest.raises(PermissionDenied):
        contests.answer(session, leader, contests.load(session, leader, contest["id"]),
                        accept=True, text="Yes")  # fmt: skip
    answered = (
        as_role("architect")
        .post(
            f"/api/v1/contests/{contest['id']}/answer",
            json={"accept": True, "answer": "Agreed; reassess reliability at 5."},
        )
        .json()["data"]
    )
    assert (answered["status"], answered["answered_by"]) == ("accepted", "Architect Person")
    shown = member.get(f"/api/v1/applications/{ref}/contests").json()["data"]
    assert [item["status"] for item in shown["contests"]] == ["accepted"] and shown["can_raise"]
    with db.read() as session:
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == people.accounts["member"])
        ).all()
    assert f"Architect Person accepted your contest of reliability for {ref} Sample Tracker" in told
