"""Campaigns: the owners in a unit asked to confirm or assess by a date, items that close
themselves, and coverage by unit that matches the list behind it (CUR-05)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, reminders
from appwren.core.clock import frozen_at
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Notice
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from appwren.oversight import attestation, campaigns
from appwren.people import accounts
from tests.people import ME, People
from tests.test_decisions import GOOD, who

Clients = Callable[[str | None], TestClient]
START = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
DUE = "2026-05-15"


def add(db: Database, people: People, name: str, unit: str, owner: str, **values: Any) -> str:
    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION,
            {"name": name, "org_unit_id": people.units[unit], "tier": "3", "sourcing": "saas",
             **values},
            accountable=people.accounts[owner],
        )  # fmt: skip
        return app.ref


def start(db: Database, people: People, role: str, **values: Any) -> str:
    principal = who(db, people, role)
    with db.write(principal.actor) as session, frozen_at(START):
        campaign = campaigns.start(
            session, principal,
            {"name": "Spring confirmations", "kind": "confirm", "org_unit_id": people.units["IMM"],
             "due_on": DUE, **values},
        )  # fmt: skip
        return campaign.ref


def detail(db: Database, people: People, role: str, ref: str, **filters: Any) -> dict[str, Any]:
    principal = who(db, people, role)
    with db.write(principal.actor) as session:
        campaign = campaigns.load(session, ref)
        campaigns.refresh(session, campaign)
        return campaigns.detail(session, principal, campaign, filters)


def confirm(db: Database, people: People, role: str, ref: str) -> None:
    principal = who(db, people, role)
    with db.write(principal.actor) as session:
        attestation.confirm(session, principal, records.load(session, principal, APPLICATION, ref))


@pytest.fixture
def portfolio(db: Database, people: People) -> dict[str, str]:
    """Two in the Hale Lab, one directly in Immunology, one in Cancer Biology."""
    with frozen_at(START - timedelta(days=30)):
        return {
            "tracker": add(db, people, "Sample Tracker", "HALE", "member"),
            "notebook": add(db, people, "Lab Notebook", "HALE", "member"),
            "portal": add(db, people, "Immunology Portal", "IMM", "architect"),
            "registry": add(db, people, "Tumor Registry", "CANCER", "manager"),
        }


def test_a_campaign_asks_the_owners_and_tracks_who_has_answered(
    db: Database, people: People, portfolio: dict[str, str]
) -> None:
    with frozen_at(START - timedelta(days=1)):
        confirm(db, people, "member", portfolio["tracker"])  # before the campaign: not counted
    ref = start(db, people, "steward")
    with db.read() as session:
        told = session.execute(
            select(Notice.account_id, Notice.text).where(Notice.kind == "campaign")
        ).all()
    assert sorted(told) == sorted([
        (people.accounts["member"],
         f"Steward Person asks you to confirm the record of 2 applications by {DUE}: "
         "Spring confirmations"),
        (people.accounts["architect"],
         f"Steward Person asks you to confirm the record of 1 application by {DUE}: "
         "Spring confirmations"),
    ])  # fmt: skip
    shown = detail(db, people, "steward", ref)
    assert shown["progress"] == {"total": 3, "done": 0, "excused": 0, "pending": 3, "percent": 0}
    assert portfolio["registry"] not in [item["application"]["ref"] for item in shown["items"]]
    with frozen_at(START + timedelta(days=3)):
        confirm(db, people, "member", portfolio["tracker"])
    shown = detail(db, people, "steward", ref)
    done = next(i for i in shown["items"] if i["application"]["ref"] == portfolio["tracker"])
    assert (done["status"], done["done_on"], done["done_by"]) == (
        "done", date(2026, 4, 4), "Member Person",
    )  # fmt: skip
    assert shown["progress"]["percent"] == 33
    # Coverage by unit, least covered first, each figure the length of the list behind it.
    assert [row["unit"]["name"] for row in shown["coverage"]] == ["Immunology", "Hale Lab"]
    for row in shown["coverage"]:
        listed = detail(db, people, "steward", ref, unit=row["unit"]["id"])
        assert len(listed["items"]) == row["total"]
        assert sum(item["status"] == "done" for item in listed["items"]) == row["done"]
    mine = detail(db, people, "member", ref, mine=True)
    assert {item["application"]["ref"] for item in mine["items"]} == {
        portfolio["notebook"], portfolio["tracker"],
    }  # fmt: skip


def test_an_assessment_campaign_closes_an_item_when_it_is_assessed(
    db: Database, people: People, portfolio: dict[str, str]
) -> None:
    ref = start(db, people, "manager", kind="assess", name="Spring assessments")
    with db.write(ME.actor) as session, frozen_at(START + timedelta(days=1)):
        app = records.load(session, ME, APPLICATION, portfolio["portal"])
        assessment.record(session, ME, app, GOOD)
        attestation.confirm(  # a confirmation is not an assessment
            session, who(db, people, "member"),
            records.load(session, ME, APPLICATION, portfolio["tracker"]),
        )  # fmt: skip
    statuses = {
        item["application"]["ref"]: item["status"]
        for item in detail(db, people, "manager", ref)["items"]
    }
    assert statuses == {
        portfolio["portal"]: "done", portfolio["tracker"]: "pending",
        portfolio["notebook"]: "pending",
    }  # fmt: skip


def test_who_may_run_a_campaign(db: Database, people: People, portfolio: dict[str, str]) -> None:
    start(db, people, "steward")  # Immunology's steward, for Immunology
    start(db, people, "manager", org_unit_id=None)  # the whole organization
    for role, unit in (("steward", "CANCER"), ("leader", "IMM"), ("member", "HALE")):
        with pytest.raises(PermissionDenied):
            start(db, people, role, org_unit_id=people.units[unit])
    with pytest.raises(PermissionDenied):
        start(db, people, "steward", org_unit_id=None)
    with pytest.raises(Invalid) as caught:
        start(db, people, "steward", name="", due_on="2020-01-01", kind="sing")
    assert set(caught.value.errors) == {"name", "due_on", "kind"}


def test_an_item_is_excused_with_a_reason_and_a_campaign_ends(
    db: Database, people: People, portfolio: dict[str, str]
) -> None:
    ref = start(db, people, "steward")
    steward = who(db, people, "steward")
    item = next(
        i for i in detail(db, people, "steward", ref)["items"]
        if i["application"]["ref"] == portfolio["portal"]
    )  # fmt: skip
    with db.write(steward.actor) as session:
        campaign = campaigns.load(session, ref)
        with pytest.raises(Invalid):
            campaigns.excuse(session, steward, campaign, item["id"], "  ")
        campaigns.excuse(session, steward, campaign, item["id"], "Being retired next month.")
    progress = detail(db, people, "steward", ref)["progress"]
    assert (progress["excused"], progress["pending"], progress["total"]) == (1, 2, 3)
    with db.write(steward.actor) as session:
        campaigns.end(session, steward, campaigns.load(session, ref), "close")
        with pytest.raises(Invalid, match="already ended"):
            campaigns.end(session, steward, campaigns.load(session, ref), "cancel")
    confirm(db, people, "member", portfolio["tracker"])
    shown = detail(db, people, "steward", ref)
    assert shown["status"] == "closed" and shown["progress"]["done"] == 0  # it found what it found


def test_an_application_with_nobody_to_ask_is_listed_before_starting(
    db: Database, people: People, portfolio: dict[str, str]
) -> None:
    """Its owner has gone, and Cancer Biology has no steward to ask instead. In Immunology,
    the steward is asked in place of an owner who has gone."""
    orphan = add(db, people, "Pathology Archive", "CANCER", "auditor")
    kept = add(db, people, "Flow Booking", "IMM", "auditor")
    with db.write(ME.actor) as session:
        accounts.get(session, people.accounts["auditor"]).status = "disabled"
    manager = who(db, people, "manager")
    with db.read() as session, frozen_at(START):
        found = campaigns.preview(
            session, manager, {"name": "x", "kind": "confirm", "org_unit_id": None, "due_on": DUE}
        )
        assert found["applications"] == 6
        assert [item["ref"] for item in found["nobody"]] == [orphan]
        flow = records.load(session, ME, APPLICATION, kept)
        assert campaigns.asked_for(session, flow) == people.accounts["steward"]


def test_home_lists_what_a_campaign_asks_and_the_scheduler_reminds(
    as_role: Clients, db: Database, people: People, portfolio: dict[str, str]
) -> None:
    ref = start(db, people, "steward")
    with frozen_at(START + timedelta(days=2)):
        owed = as_role("member").get("/api/v1/home").json()["data"]["items"]
    campaign_items = [item for item in owed if item["kind"] == "campaign"]
    assert len(campaign_items) == 2
    assert (
        campaign_items[0]["text"]
        == f"Confirm that its record is right, for Spring confirmations, by {DUE}"
    )
    assert not [item for item in owed if item["kind"] == "confirm"]  # said once, as the campaign's
    with frozen_at(datetime(2026, 5, 5, 9, tzinfo=UTC)), db.bookkeeping() as session:
        said = reminders.send(session)
    assert said["reminders"] >= 3  # two for the member, one for the architect
    with db.read() as session:
        texts = session.scalars(
            select(Notice.text).where(
                Notice.kind == "reminder", Notice.account_id == people.accounts["architect"]
            )
        ).all()
    assert any(
        f"Spring confirmations: confirm the record of {portfolio['portal']}" in t for t in texts
    )
    page = as_role("member").get(f"/api/v1/campaigns/{ref}", params={"mine": "true"}).json()["data"]
    assert len(page["items"]) == 2 and page["can_run"] is False
    assert as_role("steward").post(f"/api/v1/campaigns/{ref}/remind").json()["data"]["told"] == 2
