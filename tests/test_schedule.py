"""Scheduled work: each job run once by whichever process claims it, and reminders that go
to whoever a thing waits on, then the steward, then the leader, each once (CUR-04)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, jobs, reminders
from appwren.core.clock import frozen_at
from appwren.db.engine import Database
from appwren.db.models import Job, JobRun, Notice, Reminder
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, CONTRACT, VENDOR
from appwren.people import accounts
from tests.conftest import Instance
from tests.people import ME, People
from tests.test_decisions import GOOD, decide

Clients = Callable[[str | None], TestClient]
START = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
QUIET = {"reminders": 0, "overdue": 0, "escalated": 0}


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=9, tzinfo=UTC)


def notices_of(db: Database, account_id: int) -> list[tuple[str, str]]:
    with db.read() as session:
        rows = session.scalars(
            select(Notice).where(Notice.account_id == account_id).order_by(Notice.id)
        )
        return [(row.kind, row.text) for row in rows]


def remind(db: Database) -> dict[str, int]:
    with db.bookkeeping() as session:
        return reminders.send(session)


def forget_notices(db: Database) -> None:
    with db.bookkeeping() as session:
        for row in session.scalars(select(Notice)):
            session.delete(row)


def assessed_app(db: Database, people: People, *, owner: str = "member", **values: Any) -> str:
    """A tier 3 application in the Hale Lab, assessed today: current for 18 months."""
    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION,
            {"name": "Sample Tracker", "org_unit_id": people.units["HALE"], "tier": "3",
             "sourcing": "saas", **values},
            accountable=people.accounts[owner],
        )  # fmt: skip
        assessment.record(session, ME, app, GOOD)
        return app.ref


# --- Jobs ---------------------------------------------------------------------------------


def test_jobs_run_when_due_and_not_before(instance: Instance, people: People) -> None:
    db, config = instance.db, instance.config
    with frozen_at(START):
        ran = {result["key"] for result in jobs.run_due(db, config)}
        assert ran == set(jobs.JOBS)
        assert jobs.run_due(db, config) == []  # nothing is due again yet
    with frozen_at(START + timedelta(minutes=2)):
        assert [result["key"] for result in jobs.run_due(db, config)] == ["mail"]
    with frozen_at(START + timedelta(hours=1, minutes=1)):
        ran = {result["key"] for result in jobs.run_due(db, config)}
        assert "reminders" in ran and "tidy" not in ran  # not the daily one


def test_two_processes_run_a_job_once_between_them(instance: Instance, people: People) -> None:
    """Each server process, and `appwren jobs run`, has its own connection to the one
    database. Whichever claims a job has it; the other finds it taken."""
    first, config = instance.db, instance.config
    second = Database(config.database_url)
    try:
        with frozen_at(START):
            jobs.ensure(first)
            results = [jobs.run_job(db, config, "reminders") for db in (first, second)]
            assert [result is not None for result in results] == [True, False]
            with first.read() as session:
                row = session.get(Job, "reminders")
                assert row is not None and row.claimed_until is None
                assert row.next_run_at == START + timedelta(hours=1)
    finally:
        second.dispose()


def test_a_claimed_job_is_not_run_again_until_the_claim_runs_out(
    instance: Instance, people: People
) -> None:
    db, config = instance.db, instance.config
    with frozen_at(START):
        jobs.ensure(db)
        assert jobs._claim(db, "reminders", force=False)  # another process has it
        assert jobs.run_job(db, config, "reminders") is None
        assert jobs.run_job(db, config, "reminders", force=True) is None
    with frozen_at(START + jobs.LEASE + timedelta(seconds=1)):
        result = jobs.run_job(db, config, "reminders")  # that process died; it is taken up
        assert result is not None and result["status"] == "ok"


def test_a_failing_job_is_recorded_and_tried_again(
    instance: Instance, people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, config = instance.db, instance.config

    def broken(_db: Database, _config: object) -> dict[str, int]:
        raise RuntimeError("the disk is full")

    spec = jobs.JOBS["tidy"]
    monkeypatch.setitem(
        jobs.JOBS, "tidy", jobs.JobSpec(spec.key, spec.label, spec.describes, spec.every, broken)
    )
    with frozen_at(START):
        jobs.ensure(db)
        result = jobs.run_job(db, config, "tidy")
        assert result is not None and result["status"] == "failed"
        with db.read() as session:
            row = session.get(Job, "tidy")
            assert row is not None and row.last_status == "failed" and row.claimed_until is None
            assert "the disk is full" in (row.last_summary or "")
            [run] = session.scalars(select(JobRun)).all()
            assert run.status == "failed"
    monkeypatch.setitem(jobs.JOBS, "tidy", spec)
    with frozen_at(START + timedelta(days=1, seconds=1)):
        result = jobs.run_job(db, config, "tidy")
        assert result is not None and result["status"] == "ok"


def test_a_paused_job_is_skipped_unless_asked_for(instance: Instance, people: People) -> None:
    db, config = instance.db, instance.config
    jobs.set_enabled(db, "reminders", False)
    assert "reminders" not in {result["key"] for result in jobs.run_due(db, config)}
    assert jobs.run_job(db, config, "reminders", force=True) is not None


def test_an_administrator_sees_and_runs_jobs(as_role: Clients, people: People) -> None:
    admin = as_role("admin")
    shown = admin.get("/api/v1/jobs").json()["data"]
    assert [job["key"] for job in shown["jobs"]] == list(jobs.JOBS)
    assert all(job["enabled"] for job in shown["jobs"])
    assert shown["reminders"] == {"soon_days": 14, "steward_after_days": 7, "leader_after_days": 21}
    done = admin.post("/api/v1/jobs/reminders/run").json()["data"]
    assert (done["status"], done["summary"]) == ("ok", "Nothing to do")
    paused = admin.put("/api/v1/jobs/reminders", json={"enabled": False}).json()["data"]
    assert paused["enabled"] is False and paused["last_status"] == "ok"
    assert admin.post("/api/v1/jobs/nothing/run").status_code == 404
    assert as_role("manager").get("/api/v1/jobs").status_code == 403


# --- Reminders ----------------------------------------------------------------------------


def test_an_expiring_assessment_reminds_its_owner_then_the_steward_then_the_leader(
    db: Database, people: People
) -> None:
    owner, above, top = (people.accounts[role] for role in ("member", "steward", "leader"))
    with frozen_at(START):
        ref = assessed_app(db, people)
    what = f"assessment of {ref} Sample Tracker"
    with frozen_at(at("2027-08-01")):  # a month ahead of the end of its 18 months: too early
        assert remind(db) == QUIET
    with frozen_at(at("2027-08-30")):
        assert remind(db)["reminders"] == 1
        assert remind(db)["reminders"] == 0  # said once
    assert notices_of(db, owner) == [("reminder", f"Due in 3 days: {what}")]
    with frozen_at(at("2027-09-03")):
        assert remind(db)["overdue"] == 1
    with frozen_at(at("2027-09-06")):
        assert remind(db) == QUIET  # nothing new to say
    with frozen_at(at("2027-09-09")):
        assert remind(db)["escalated"] == 1
    with frozen_at(at("2027-09-23")):
        assert remind(db)["escalated"] == 1
        assert remind(db)["escalated"] == 0
    assert notices_of(db, owner) == [
        ("reminder", f"Due in 3 days: {what}"),
        ("overdue", f"Assessment expired by 1 day: {what}"),
    ]
    assert notices_of(db, above) == [
        ("escalated", f"Assessment expired by 7 days, and now with you: {what}")
    ]
    assert notices_of(db, top) == [
        ("escalated", f"Assessment expired by 21 days, and now with you: {what}")
    ]
    with db.read() as session:
        stages = sorted(row.stage for row in session.scalars(select(Reminder)))
        assert stages == ["leader", "overdue", "soon", "steward"]


def test_a_new_assessment_starts_the_reminders_again(db: Database, people: People) -> None:
    with frozen_at(START):
        ref = assessed_app(db, people)
    with frozen_at(at("2027-09-03")):
        assert remind(db)["overdue"] == 1
        with db.write(ME.actor) as session:
            assessment.record(session, ME, records.load(session, ME, APPLICATION, ref), GOOD)
        assert remind(db) == QUIET
    with frozen_at(at("2029-03-04")):
        assert remind(db)["overdue"] == 1  # late again, against the new one


def test_something_found_long_overdue_is_said_once_at_the_stage_it_has_reached(
    db: Database, people: People
) -> None:
    """The first run after an upgrade finds things that have been late for months. Each is
    told to the leader, once, and not also to everyone below in the same hour."""
    owner, above, top = (people.accounts[role] for role in ("member", "steward", "leader"))
    with frozen_at(START):
        assessed_app(db, people)
    with frozen_at(at("2028-01-01")):
        assert remind(db) == {"reminders": 0, "overdue": 0, "escalated": 1}
        assert remind(db) == QUIET
    assert notices_of(db, owner) == [] and notices_of(db, above) == []
    assert [kind for kind, _ in notices_of(db, top)] == ["escalated"]


def test_a_decision_review_reminds_its_decider_and_a_target_its_owner(
    db: Database, people: People
) -> None:
    owner, leader = people.accounts["member"], people.accounts["leader"]
    with frozen_at(START):
        ref = assessed_app(db, people)
        decide(db, people, "leader", ref, disposition="retire", target_on="2026-12-31")
    forget_notices(db)
    with frozen_at(at("2026-12-25")):
        assert remind(db)["reminders"] == 1
    assert notices_of(db, owner) == [("reminder", f"Due in 6 days: {ref} Sample Tracker: Retire")]
    with frozen_at(at("2027-02-20")):  # the review is a year on
        remind(db)
    assert (
        "reminder",
        f"Due in 10 days: review of the decision on {ref} Sample Tracker",
    ) in notices_of(db, leader)
    with frozen_at(at("2027-04-30")):
        remind(db)  # a review late by two months stays with the decider: it does not escalate
    told = notices_of(db, leader)
    assert (
        "overdue",
        f"Review overdue by 59 days: review of the decision on {ref} Sample Tracker",
    ) in told
    # The target, four months past, has reached the leader; the review never goes above them.
    assert [kind for kind, _ in told] == ["reminder", "escalated", "overdue"]
    assert notices_of(db, people.accounts["steward"]) == []


def test_the_review_of_a_decider_who_has_left_goes_to_the_units_leaders(
    db: Database, people: People
) -> None:
    with frozen_at(START):
        ref = assessed_app(db, people)
        decide(db, people, "manager", ref)
    with db.write(ME.actor) as session:
        account = accounts.get(session, people.accounts["manager"])
        account.status = "disabled"
    with frozen_at(at("2027-02-25")):
        remind(db)
    assert notices_of(db, people.accounts["leader"]) == [
        ("reminder", f"Due in 5 days: review of the decision on {ref} Sample Tracker")
    ]


def test_a_contracts_notice_date_reminds_its_owner(db: Database, people: People) -> None:
    owner = people.accounts["architect"]
    with db.write(ME.actor) as session, frozen_at(START):
        vendor = records.create(
            session, ME, VENDOR, {"name": "Larkfield", "kind": "software_vendor"}
        )
        contract = records.create(
            session, ME, CONTRACT,
            {"name": "Larkfield licenses", "vendor_id": vendor.id, "ends_on": "2026-12-31",
             "notice_days": 90, "owner_id": owner},
        )  # fmt: skip
        ref = contract.ref
    with frozen_at(at("2026-09-20")):
        assert remind(db)["reminders"] == 1
    assert notices_of(db, owner) == [
        ("reminder", f"Due in 12 days: notice date of {ref} Larkfield licenses")
    ]
    with frozen_at(at("2026-10-03")):
        assert remind(db)["overdue"] == 1
    with frozen_at(at("2026-11-20")):
        assert remind(db) == QUIET  # no escalation: a contract has no unit
    with db.write(ME.actor) as session, frozen_at(at("2026-11-20")):
        row = records.load(session, ME, CONTRACT, ref)
        records.update(session, ME, CONTRACT, row, {"ends_on": "2027-12-31"}, version=row.version)
    with frozen_at(at("2027-09-25")):
        assert remind(db)["reminders"] == 1  # the renewed term has its own notice date
    with frozen_at(at("2028-02-01")):
        assert remind(db) == QUIET  # once a contract is over, its notice date is history
    assert date(2027, 10, 2) == date(2027, 12, 31) - timedelta(days=90)


def test_nothing_is_reminded_of_for_an_application_out_of_service(
    db: Database, people: People
) -> None:
    with frozen_at(START):
        ref = assessed_app(db, people)
        with db.write(ME.actor) as session:
            row = records.load(session, ME, APPLICATION, ref)
            records.update(
                session, ME, APPLICATION, row, {"lifecycle": "retired"}, version=row.version
            )
    with frozen_at(at("2027-09-03")):
        assert remind(db) == QUIET
