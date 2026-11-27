"""Home, the dashboard, data quality, and lists in and out (slice 7 of wave 1)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment
from appwren.db.engine import Database
from appwren.db.models import Event
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, VENDOR
from tests.people import ME, ROLES, People

Clients = Callable[[str | None], TestClient]
GOOD = {
    "strategic_fit": 4,
    "functional_fit": 4,
    "future_need": 4,
    "reliability": 4,
    "maintainability": 4,
    "support_effort": 4,
    "change_effort": 4,
    "compliance": 4,
}
POOR = {
    **GOOD,
    "strategic_fit": 1,
    "functional_fit": 2,
    "future_need": 1,
    "reliability": 1,
    "maintainability": 1,
}


def portfolio(db: Database, people: People) -> list[str]:
    """A small portfolio in two divisions: assessed and not, healthy and not, one orphaned,
    one restricted, one retired."""
    made = []
    plans = [
        ("Grants Portal", "IMM", {"tier": "2", "users": 900}, GOOD),
        (
            "Lab Notebook",
            "HALE",
            {"tier": "3", "sourcing": "research_software", "maintainers": 1},
            POOR,
        ),
        ("Old Surveys", "HALE", {"tier": "4", "users": 12}, POOR),
        ("Imaging Pipeline", "CANCER", {"tier": "3", "restricted": True}, GOOD),
        ("Unassessed Tool", "IMM", {}, None),
        ("Old Reports", "HALE", {"lifecycle": "retired"}, GOOD),
    ]
    with db.write(ME.actor) as session:
        for name, unit, values, answers in plans:
            app = records.create(
                session,
                ME,
                APPLICATION,
                {
                    "name": name,
                    "org_unit_id": people.units[unit],
                    "users": 120,
                    "maintainers": 3,
                    "annual_cost": 20_000,
                    "sign_in": "sso",
                    "monitoring": "alerting",
                    "backup": "vendor",
                    "data_classes": ["internal"],
                    "sourcing": "saas",
                    **values,
                },
                accountable=None if name == "Unassessed Tool" else people.accounts["steward"],
            )
            if answers:
                assessment.record(session, ME, app, answers)
            made.append(app.ref)
    return made


def figures(data: dict[str, Any]) -> list[dict[str, Any]]:
    out = [data["total"]]
    for value in data.values():
        if isinstance(value, list):
            for item in value:
                if "count" in item:
                    out.append(item)
                for issue in item.get("issues", []):
                    out.append(issue)
                if "total" in item:
                    out.append(item["total"])
    return out


def test_every_figure_opens_exactly_the_list_it_counted(
    db: Database, people: People, as_role: Clients
) -> None:
    portfolio(db, people)
    for role in ROLES:
        client = as_role(role)
        for path, params in (
            ("/api/v1/dashboard", {}),
            ("/api/v1/data-quality", {}),
            ("/api/v1/dashboard", {"unit": people.units["IMM"]}),
        ):
            data = client.get(path, params=params).json()["data"]
            for figure in figures(data):
                listed = client.get("/api/v1/portfolio", params=figure["filters"]).json()
                assert listed["meta"]["total"] == figure["count"], (role, path, figure["label"])


def test_the_parts_add_up_to_the_whole(db: Database, people: People, as_role: Clients) -> None:
    portfolio(db, people)
    data = as_role("manager").get("/api/v1/dashboard").json()["data"]
    total = data["total"]["count"]
    assert total == 5  # the retired one is not in service
    for part in ("recommendations", "decisions", "lifecycle", "sourcing", "confidence"):
        assert sum(item["count"] for item in data[part]) == total, part
    quality = as_role("manager").get("/api/v1/data-quality").json()["data"]
    assert sum(unit["total"]["count"] for unit in quality["units"]) == total
    member = as_role("member").get("/api/v1/dashboard").json()["data"]
    assert member["total"]["count"] == 4  # the restricted one is not theirs to know


def test_home_lists_what_a_person_owes(db: Database, people: People, as_role: Clients) -> None:
    refs = portfolio(db, people)
    steward = as_role("steward").get("/api/v1/home").json()["data"]
    kinds = {(item["application"]["ref"], item["kind"]) for item in steward["items"]}
    assert (refs[4], "orphan") in kinds  # nobody is accountable, in their unit
    assert (refs[1], "flag") in kinds  # one person keeps the lab notebook
    assert all(item["application"]["ref"] != refs[5] for item in steward["items"])
    severities = [item["severity"] for item in steward["items"]]
    assert severities == sorted(severities, key=["danger", "warning", "info"].index)
    leader = as_role("leader").get("/api/v1/home").json()["data"]
    assert leader["waiting_total"] >= 1
    assert as_role("member").get("/api/v1/home").json()["data"]["items"] == []


def test_a_file_with_one_bad_row_loads_nothing_and_names_the_row(
    db: Database, people: People, as_role: Clients
) -> None:
    with db.write(ME.actor) as session:
        records.create(session, ME, VENDOR, {"name": "Northwind Software"})
    text = (
        "Name,Unit,Accountable owner,Sourcing,Tier,Vendor,Users,Data classes\n"
        "Research Wiki,IMM,steward@bramblewood.example,Software as a service,2,"
        "Northwind Software,300,internal; personal\n"
        "Freezer Watch,HALE,,built_here,4,,25,\n"
        "Broken One,NOWHERE,nobody@bramblewood.example,magic,,Acme,,\n"
    )
    steward = as_role("steward")
    dry = steward.post(
        "/api/v1/imports/applications", content=text, headers={"Content-Type": "text/csv"}
    ).json()["data"]
    assert dry["applied"] is False
    rows = {problem["row"] for problem in dry["problems"]}
    assert rows == {4}
    messages = " ".join(problem["message"] for problem in dry["problems"])
    for words in ("NOWHERE", "nobody@", "Acme"):
        assert words in messages
    real = steward.post(
        "/api/v1/imports/applications",
        params={"dry_run": False},
        content=text,
        headers={"Content-Type": "text/csv"},
    ).json()["data"]
    assert real["applied"] is False  # one bad row, so none of it was kept
    with db.read() as session:
        assert records.search(session, ME, APPLICATION, {})[1] == 0
    good = "\n".join(text.splitlines()[:3]) + "\n"
    loaded = steward.post(
        "/api/v1/imports/applications",
        params={"dry_run": False},
        content=good,
        headers={"Content-Type": "text/csv"},
    ).json()["data"]
    assert (loaded["applied"], loaded["created"]) == (True, 2)
    with db.read() as session:
        rows_now, _ = records.search(session, ME, APPLICATION, {"q": "Research Wiki"})
        wiki = rows_now[0]
        assert (wiki.sourcing, wiki.tier, wiki.users, wiki.data_classes) == (
            "saas",
            "2",
            300,
            ["internal", "personal"],
        )
        assert wiki.vendor_id is not None
        ref = wiki.ref
    update = f"Reference,Name,Users\n{ref},Research Wiki,450\n"
    again = steward.post(
        "/api/v1/imports/applications",
        params={"dry_run": False},
        content=update,
        headers={"Content-Type": "text/csv"},
    ).json()["data"]
    assert (again["applied"], again["updated"], again["created"]) == (True, 1, 0)
    assert (
        as_role("member")
        .post("/api/v1/imports/applications", content=good, headers={"Content-Type": "text/csv"})
        .status_code
        == 403
    )


def test_exports_withhold_what_the_reader_may_not_see_and_are_recorded(
    db: Database, people: People, as_role: Clients
) -> None:
    portfolio(db, people)
    with db.write(ME.actor) as session:
        app = records.search(session, ME, APPLICATION, {"q": "Grants"})[0][0]
        records.update(
            session, ME, APPLICATION, app, {"summary": '=HYPERLINK("x")'}, version=app.version
        )
    member = as_role("member").get("/api/v1/exports/applications", params={"format": "csv"})
    assert member.status_code == 200 and "attachment" in member.headers["content-disposition"]
    table = list(csv.DictReader(io.StringIO(member.text)))
    assert {row["annual_cost"] for row in table} == {"withheld"}
    grants = next(row for row in table if row["name"] == "Grants Portal")
    assert grants["summary"].startswith("'=")  # a formula is written as text
    manager = as_role("manager").get("/api/v1/exports/portfolio", params={"format": "json"})
    rows = json.loads(manager.text)["rows"]
    assert {row["annual_cost"] for row in rows} == {20_000}
    assert "score_business_value" in rows[0]
    with db.read() as session:
        exported = session.scalars(select(Event).where(Event.action == "exported")).all()
        assert [e.changes["list"] for e in exported] == ["applications", "portfolio"]
