"""Confirming a record: who may, how often by tier, and what a stale record costs (CUR-03)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, reminders
from appwren.core.clock import frozen_at
from appwren.core.errors import PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Notice
from appwren.inventory import history, records
from appwren.inventory.registry import APPLICATION
from appwren.oversight import attestation
from appwren.reporting import data_quality
from tests.people import ME, People
from tests.test_decisions import GOOD, who

Clients = Callable[[str | None], TestClient]
BEGAN = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=9, tzinfo=UTC)


def begin(db: Database, moment: datetime = BEGAN) -> None:
    with db.write(ME.actor) as session, frozen_at(moment):
        attestation.begin(session)


def add(db: Database, people: People, *, tier: str = "3", owner: str = "member") -> str:
    """A well-known application in the Hale Lab, assessed when it is added."""
    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION,
            {"name": "Sample Tracker", "org_unit_id": people.units["HALE"], "tier": tier,
             "sourcing": "saas", "users": 120, "annual_cost": 20_000, "sign_in": "sso",
             "monitoring": "alerting", "backup": "vendor", "data_classes": ["internal"],
             "maintainers": 3},
            accountable=people.accounts[owner],
        )  # fmt: skip
        assessment.record(session, ME, app, GOOD)
        return app.ref


def scores(db: Database, ref: str) -> dict:
    with db.read() as session:
        return assessment.score_one(session, records.load(session, ME, APPLICATION, ref))


def confirm(db: Database, people: People, role: str, ref: str, note: str | None = None) -> None:
    principal = who(db, people, role)
    with db.write(principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        attestation.confirm(session, principal, app, note=note)


def test_a_stale_record_loses_the_models_points_and_regains_them_when_confirmed(
    db: Database, people: People
) -> None:
    begin(db)
    with frozen_at(at("2026-02-02")):
        ref = add(db, people)  # tier 3: confirmed once a year
        fresh = scores(db, ref)
        assert fresh["stale"] is None and "stale" not in [f["key"] for f in fresh["flags"]]
    with frozen_at(at("2027-02-01")):
        assert scores(db, ref)["stale"] is None  # due on the day: not yet past it
    with frozen_at(at("2027-02-03")):
        late = scores(db, ref)
        assert late["stale"] == {
            "penalty": 15, "from": fresh["confidence"], "due": date(2027, 2, 2),
            "confirmed_on": None,
        }  # fmt: skip
        assert late["confidence"] == fresh["confidence"] - 15
        assert late["missing"][0]["factor"] == "confirm"
        assert "Never confirmed; it was due by 2027-02-02" in late["missing"][0]["why"]
        assert "stale" in [flag["key"] for flag in late["flags"]]
        confirm(db, people, "member", ref, note="Checked the vendor and the hosting.")
        again = scores(db, ref)
        assert again["stale"] is None and again["confidence"] == fresh["confidence"]
    with frozen_at(at("2028-02-04")):  # a year after the confirmation, and a day
        assert scores(db, ref)["stale"]["confirmed_on"] == date(2027, 2, 3)


def test_how_often_follows_the_tier(db: Database, people: People) -> None:
    begin(db)
    with frozen_at(at("2026-02-02")):
        critical = add(db, people, tier="1")
        minor = add(db, people, tier="5")
    with frozen_at(at("2026-08-10")):
        assert scores(db, critical)["stale"] is not None  # six months for tiers 1 and 2
        assert scores(db, minor)["stale"] is None


def test_nothing_is_stale_on_the_day_of_an_upgrade(db: Database, people: People) -> None:
    """A record added long before the installation began asking is due one period after it
    began, not one period after it was added."""
    with frozen_at(at("2024-06-01")):
        ref = add(db, people)
    with frozen_at(at("2026-03-01")):
        assert scores(db, ref)["stale"] is None  # before the upgrade, nothing has begun
    begin(db, at("2026-03-02"))
    with frozen_at(at("2026-03-03")):
        assert scores(db, ref)["stale"] is None
    with frozen_at(at("2027-03-03")):
        assert scores(db, ref)["stale"]["due"] == date(2027, 3, 2)
    begin(db, at("2027-06-01"))  # a later upgrade does not move the day it began
    with frozen_at(at("2027-03-03")):
        assert scores(db, ref)["stale"] is not None


def test_who_may_confirm(db: Database, people: People) -> None:
    begin(db)
    ref = add(db, people)
    for role, allowed in [
        ("member", True),  # accountable for it
        ("steward", True),  # for Immunology, above the Hale Lab
        ("manager", True),
        ("architect", False),
        ("leader", False),
        ("auditor", False),
        ("admin", False),
    ]:
        if allowed:
            confirm(db, people, role, ref)
        else:
            with pytest.raises(PermissionDenied):
                confirm(db, people, role, ref)
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, ref)
        records.update(session, ME, APPLICATION, app, {"lifecycle": "retired"}, version=app.version)
    with pytest.raises(PermissionDenied, match="retired"):
        confirm(db, people, "member", ref)


def test_a_confirmation_is_on_the_record_and_in_its_history(
    as_role: Clients, db: Database, people: People
) -> None:
    begin(db)
    ref = add(db, people)
    member = as_role("member")
    shown = member.get(f"/api/v1/applications/{ref}/scores").json()["data"]["confirmation"]
    assert (shown["last"], shown["stale"], shown["can_confirm"], shown["months"]) == (
        None, False, True, 12,
    )  # fmt: skip
    done = member.post(
        f"/api/v1/applications/{ref}/confirmations", json={"note": "All still true."}
    )
    assert done.status_code == 201
    body = done.json()["data"]
    assert body["confirmed"]["by"] == "Member Person" and body["last"]["note"] == "All still true."
    listed = member.get(f"/api/v1/applications/{ref}/confirmations").json()["data"]
    assert [item["by"] for item in listed["history"]] == ["Member Person"]
    refused = as_role("architect").post(f"/api/v1/applications/{ref}/confirmations", json={})
    assert refused.status_code == 403
    assert (
        as_role("architect")
        .get(f"/api/v1/applications/{ref}/scores")
        .json()["data"]["confirmation"]["can_confirm"]
        is False
    )
    with db.read() as session:
        told = history.for_record(session, APPLICATION, records.load(session, ME, APPLICATION, ref))
        assert "Confirmed the record" in [entry["title"] for entry in told]


def test_a_stale_record_is_counted_reminded_and_listed_on_home(
    as_role: Clients, db: Database, people: People
) -> None:
    begin(db)
    with frozen_at(at("2026-02-02")):
        ref = add(db, people)
    with frozen_at(at("2027-01-25")), db.bookkeeping() as session:
        reminders.send(session)
    with db.read() as session:
        told = session.scalars(
            select(Notice.text).where(Notice.account_id == people.accounts["member"])
        ).all()
    assert told == [f"Due in 8 days: confirming the record of {ref} Sample Tracker"]
    with frozen_at(at("2027-02-10")):
        with db.read() as session:
            quality = data_quality(session, who(db, people, "manager"), {"unit": None})
        counted = {item["key"]: item for item in quality["issues"]}
        assert (counted["not_confirmed"]["label"], counted["not_confirmed"]["count"]) == (
            "Not confirmed in time", 1,
        )  # fmt: skip
        owed = as_role("member").get("/api/v1/home").json()["data"]["items"]
        assert ("confirm", "Confirm that its record is right") in [
            (item["kind"], item["text"]) for item in owed
        ]
        listed = as_role("manager").get("/api/v1/portfolio", params={"quality": "not_confirmed"})
        assert [row["ref"] for row in listed.json()["data"]] == [ref]


def test_an_upgrade_from_020_brings_the_cadence_to_an_unshaped_model(
    db: Database, people: People
) -> None:
    import json
    from pathlib import Path

    from appwren.program import packs

    earlier = json.loads(
        Path(__file__).parent.joinpath("fixtures", "scoring-0.2.0.json").read_text()
    )
    assert assessment.digest(earlier) in assessment.earlier_defaults("scoring")
    assert "stale_penalty" not in earlier["cadence"]
    with db.write(ME.actor) as session:
        assessment.publish_model(session, earlier, "Program pack")
        assert packs.install(session)["scoring"] == 1
        cadence = assessment.current_model(session).definition["cadence"]
        assert (cadence["stale_penalty"], cadence["confirm_months"]["1"]) == (15, 6)
        assert cadence["reminders"]["soon_days"] == 14
        assert cadence["triggers"]["contract_notice_days"] == 60
