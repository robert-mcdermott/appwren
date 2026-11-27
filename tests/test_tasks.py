"""Triggers raise tasks for whoever must act, once per cause, and settle them when the cause is
settled (CUR-06); everything a person holds passes on in one step (CUR-07)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.core.clock import frozen_at
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Notice, Task
from appwren.inventory import parts, records
from appwren.inventory.registry import APPLICATION, COMPONENT, CONTRACT, TECHNOLOGY, VENDOR
from appwren.oversight import handover, tasks
from appwren.people import accounts
from tests.people import ME, People
from tests.test_decisions import decide, who

Clients = Callable[[str | None], TestClient]


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(hour=9, tzinfo=UTC)


def turn(db: Database, day: str) -> dict[str, int]:
    with db.write(ME.actor) as session, frozen_at(at(day)):
        return tasks.run(session)


def open_tasks(db: Database) -> list[tuple[str, int | None, str]]:
    with db.read() as session:
        rows = session.scalars(select(Task).where(Task.status == "open").order_by(Task.id))
        return [(row.kind, row.account_id, row.title) for row in rows]


def add(db: Database, people: People, name: str = "Sample Tracker", **values: Any) -> str:
    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION,
            {"name": name, "org_unit_id": people.units["HALE"], "tier": "3",
             "sourcing": "built_here", **values},
            accountable=people.accounts["member"],
        )  # fmt: skip
        return app.ref


def contract(db: Database, people: People, **values: Any) -> str:
    with db.write(ME.actor) as session:
        vendor = records.create(
            session, ME, VENDOR, {"name": "Larkfield", "kind": "software_vendor"}
        )
        row = records.create(
            session, ME, CONTRACT,
            {"name": "Larkfield licenses", "vendor_id": vendor.id, "ends_on": "2026-12-31",
             "notice_days": 90, "owner_id": people.accounts["architect"], **values},
        )  # fmt: skip
        return row.ref


def test_a_contract_raises_one_task_and_a_renewal_settles_it(db: Database, people: People) -> None:
    ref = contract(db, people, auto_renews=True)
    assert turn(db, "2026-07-01") == {"tasks_raised": 0, "tasks_settled": 0}  # too far ahead
    assert turn(db, "2026-08-10") == {"tasks_raised": 1, "tasks_settled": 0}
    assert turn(db, "2026-08-11") == {"tasks_raised": 0, "tasks_settled": 0}  # never twice
    [(kind, owner, title)] = open_tasks(db)
    assert (kind, owner) == ("contract_notice", people.accounts["architect"])
    assert title == f"Decide whether {ref} Larkfield licenses renews"
    with db.read() as session:
        task = session.scalars(select(Task)).one()
        assert "renews by itself unless notice is given" in task.reason
        told = session.scalars(select(Notice.text).where(Notice.kind == "task")).all()
    assert told == [f"New task: {title}"]
    with db.write(ME.actor) as session:
        row = records.load(session, ME, CONTRACT, ref)
        records.update(session, ME, CONTRACT, row, {"ends_on": "2027-12-31"}, version=row.version)
    assert turn(db, "2026-08-20") == {"tasks_raised": 0, "tasks_settled": 1}
    with db.read() as session:
        settled = session.scalars(select(Task)).one()
        assert (settled.status, settled.closed_by_name) == ("done", "AppWren")
        assert "term changed" in (settled.note or "")


def test_a_release_reaching_end_of_support_raises_a_task_for_each_application(
    db: Database, people: People
) -> None:
    ref = add(db, people)
    with db.write(ME.actor) as session:
        tech = records.create(session, ME, TECHNOLOGY, {"name": "Python", "kind": "language"})
        parts.set_releases(session, ME, tech, [{"cycle": "3.9", "support_ends": "2026-10-31"}])
        app = records.load(session, ME, APPLICATION, ref)
        component = records.create(
            session, ME, COMPONENT,
            {"name": "Tracker API", "application_id": app.id, "kind": "service"},
        )  # fmt: skip
        parts.set_technologies(session, ME, component, [{"technology": tech.ref, "release": "3.9"}])
        component_ref = component.ref
    assert turn(db, "2026-03-01")["tasks_raised"] == 0
    assert turn(db, "2026-06-01")["tasks_raised"] == 1
    assert open_tasks(db) == [
        (
            "end_of_support",
            people.accounts["member"],
            f"Plan for Python 3.9 in {ref} Sample Tracker",
        ),
    ]
    with db.write(ME.actor) as session:
        component = records.load(session, ME, COMPONENT, component_ref)
        parts.set_technologies(session, ME, component, [])
    assert turn(db, "2026-06-02") == {"tasks_raised": 0, "tasks_settled": 1}


def test_a_grant_ending_raises_a_task_that_a_decision_settles(db: Database, people: People) -> None:
    ref = add(db, people, funding="grant", grant_end="2026-12-31")
    with frozen_at(at("2026-08-01")):
        assert turn(db, "2026-08-01")["tasks_raised"] == 1
        decide(db, people, "leader", ref, disposition="retire", rationale="The grant ends.")
    assert turn(db, "2026-08-02") == {"tasks_raised": 0, "tasks_settled": 1}


def test_a_departure_raises_a_task_at_once_and_naming_someone_settles_it(
    db: Database, people: People
) -> None:
    ref = add(db, people)
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        accounts.set_status(
            session, admin, accounts.get(session, people.accounts["member"]), "disabled"
        )
    assert open_tasks(db) == [
        (
            "departure",
            people.accounts["steward"],
            f"Name who is accountable for {ref} Sample Tracker",
        ),
    ]
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, ref)
        records.set_owners(
            session, ME, APPLICATION, app,
            [{"account_id": people.accounts["architect"], "kind": "accountable"}],
        )  # fmt: skip
    assert turn(db, "2026-08-02")["tasks_settled"] == 1


def test_who_may_close_a_task_and_why(db: Database, people: People) -> None:
    contract(db, people)
    turn(db, "2026-08-10")
    with db.read() as session:
        task_id = session.scalars(select(Task.id)).one()
    for role in ("member", "steward"):  # a contract has no unit: only its owner or a manager
        principal = who(db, people, role)
        with db.write(principal.actor) as session, pytest.raises(PermissionDenied):
            task = tasks.load(session, who(db, people, "manager"), task_id)
            tasks.close(session, principal, task, how="done", note="Done.")
    architect = who(db, people, "architect")
    with db.write(architect.actor) as session:
        task = tasks.load(session, architect, task_id)
        with pytest.raises(Invalid):
            tasks.close(session, architect, task, how="done", note=" ")
        tasks.close(session, architect, task, how="done", note="Gave notice; moving to Calendra.")
    with db.read() as session:
        assert session.get(Task, task_id).closed_by_name == "Architect Person"


def test_each_person_sees_their_own_tasks(as_role: Clients, db: Database, people: People) -> None:
    contract(db, people)
    add(db, people, funding="grant", grant_end="2026-12-31")
    turn(db, "2026-08-10")
    mine = as_role("architect").get("/api/v1/tasks", params={"mine": "true"}).json()["data"]
    assert [task["kind"] for task in mine] == ["contract_notice"]
    member = as_role("member").get("/api/v1/tasks").json()["data"]
    assert [task["kind"] for task in member] == ["grant_end"]
    assert len(as_role("auditor").get("/api/v1/tasks").json()["data"]) == 2
    steward = as_role("steward").get("/api/v1/tasks").json()["data"]
    assert [task["kind"] for task in steward] == ["grant_end"]  # in Immunology, not a contract
    assert as_role("leader").get(f"/api/v1/tasks/{mine[0]['id']}").status_code == 404
    home = as_role("member").get("/api/v1/home").json()["data"]["items"]
    assert [item["kind"] for item in home].count("task") == 1


def test_everything_a_person_holds_passes_on_in_one_step(
    as_role: Clients, db: Database, people: People
) -> None:
    first = add(db, people)
    second = add(db, people, "Lab Notebook")
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, second)
        records.set_owners(
            session, ME, APPLICATION, app,
            [{"account_id": people.accounts["steward"], "kind": "accountable"},
             {"account_id": people.accounts["member"], "kind": "technical_owner"}],
        )  # fmt: skip
    contract(db, people, owner_id=people.accounts["member"])
    turn(db, "2026-08-10")
    member, to = people.accounts["member"], people.accounts["architect"]
    with db.read() as session:
        held = handover.holdings(session, member)
    assert (len(held["named"]), len(held["owned"]), len(held["tasks"])) == (2, 1, 1)
    assert (
        as_role("steward").post(f"/api/v1/accounts/{member}/hand-over", json={"to": to}).status_code
        == 403
    )
    done = as_role("admin").post(f"/api/v1/accounts/{member}/hand-over", json={"to": to}).json()
    assert done["data"]["moved"] == {"named": 2, "owned": 1, "tasks": 1, "asked": 0}
    assert done["data"]["left"]["total"] == 0
    with db.read() as session:
        after = handover.holdings(session, to)
        roles = {(item["record"]["ref"], item["role"]) for item in after["named"]}
    assert roles == {(first, "accountable"), (second, "technical owner")}
    with db.read() as session:
        told = session.scalars(select(Notice.text).where(Notice.account_id == to)).all()
    assert "You now hold 4 things that Member Person held" in told
