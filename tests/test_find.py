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


def test_a_list_narrowed_by_what_it_is_built_on_is_the_technologys_used_by(
    as_role: Clients, db: Database, people: People
) -> None:
    """Which applications run .NET 6, and which exact version: the list says the same as the
    technology's page, for each reader, and exports."""
    from appwren.inventory import parts
    from appwren.inventory.registry import COMPONENT, TECHNOLOGY

    with db.write(ME.actor) as session:
        dotnet = records.create(session, ME, TECHNOLOGY, {"name": ".NET", "kind": "framework"})
        parts.set_releases(session, ME, dotnet, [{"cycle": "6"}, {"cycle": "8"}])
        plan = {
            "Grants Portal": ("HALE", False, [("6", "6.0.25"), ("8", "8.0.1")]),
            "Payroll Bridge": ("HALE", False, [("6", "6.0.11")]),
            "Secret Ledger": ("CANCER", True, [("6", "6.0.25")]),
            "Old Kiosk": ("HALE", False, [("", "4.8")]),
        }
        for name, (unit, restricted, uses) in plan.items():
            app = records.create(
                session, ME, APPLICATION,
                {"name": name, "org_unit_id": people.units[unit], "tier": "3",
                 "sourcing": "built_here", "restricted": restricted},
                accountable=people.accounts["manager" if restricted else "member"],
            )  # fmt: skip
            for index, (release, version) in enumerate(uses):
                component = records.create(
                    session, ME, COMPONENT,
                    {"name": f"{name} part {index}", "application_id": app.id, "kind": "service"},
                )  # fmt: skip
                parts.set_technologies(
                    session, ME, component,
                    [{"technology": dotnet.ref, "release": release or None, "version": version}],
                )  # fmt: skip
        ref = dotnet.ref
    for role in ("member", "manager"):
        principal = who(db, people, role)
        with db.read() as session:
            page = records.detail(
                session, principal, TECHNOLOGY, records.load(session, principal, TECHNOLOGY, ref)
            )
            for release in page["releases"]:
                shown = {use["application"]["ref"] for use in release["used_by"]}
                rows, _ = records.search(
                    session, principal, APPLICATION,
                    {"technology": ref, "release": release["cycle"]}, limit=200,
                )  # fmt: skip
                assert {row.ref for row in rows} == shown, (role, release["cycle"])
            unpinned = {use["application"]["ref"] for use in page["unpinned"]}
            rows, _ = records.search(
                session, principal, APPLICATION, {"technology": ref, "release": "none"}
            )
            assert {row.ref for row in rows} == unpinned
    with db.read() as session:
        member = who(db, people, "member")
        on_six, _ = records.search(
            session, member, APPLICATION, {"technology": ref, "release": "6"}
        )
        assert sorted(row.name for row in on_six) == ["Grants Portal", "Payroll Bridge"]
        exact, _ = records.search(
            session, member, APPLICATION, {"technology": ref, "version": "6.0.25"}
        )
        assert [row.name for row in exact] == ["Grants Portal"]  # the restricted one is not seen
        parts_on, _ = records.search(
            session, member, COMPONENT, {"technology": ref, "release": "8"}
        )
        assert [row.name for row in parts_on] == ["Grants Portal part 1"]
        with pytest.raises(Invalid):
            records.search(session, member, APPLICATION, {"technology": ref, "release": "5"})
        with pytest.raises(Invalid):
            records.search(session, member, APPLICATION, {"release": "6"})
    exported = as_role("member").get(
        "/api/v1/exports/applications", params={"technology": ref, "release": "6", "format": "csv"}
    )
    assert exported.status_code == 200
    lines = exported.text.strip().splitlines()
    assert (
        len(lines) == 3
        and "Payroll Bridge" in exported.text
        and "Secret Ledger" not in exported.text
    )
