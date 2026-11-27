"""Decisions, mismatches, the portfolio, and its snapshots (slice 6 of wave 1)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, decisions
from appwren.access.principal import Principal
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Decision, Event, ScoreSnapshot
from appwren.inventory import applications, records
from appwren.inventory.registry import APPLICATION
from appwren.people import accounts
from tests.conftest import TESTER
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


def who(db: Database, people: People, role: str) -> Principal:
    with db.read() as session:
        return accounts.principal_for(session, accounts.get(session, people.accounts[role]))


def add_app(db: Database, people: People, unit: str = "HALE", **values: Any) -> str:
    with db.write(ME.actor) as session:
        values = {
            "name": "Sample Tracker",
            "org_unit_id": people.units[unit],
            "tier": "3",
            "users": 120,
            "maintainers": 3,
            "annual_cost": 20_000,
            "sign_in": "sso",
            "monitoring": "alerting",
            "backup": "vendor",
            "data_classes": ["internal"],
            "sourcing": "saas",
            **values,
        }
        app = records.create(
            session, ME, APPLICATION, values, accountable=people.accounts["steward"]
        )
        assessment.record(session, ME, app, GOOD)
        return app.ref


def decide(db: Database, people: People, role: str, ref: str, **values: Any) -> Decision:
    principal = who(db, people, role) if role != "me" else ME
    with db.write(principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        row = decisions.record(
            session,
            principal,
            app,
            {"disposition": "invest", "rationale": "It is doing well.", **values},
        )
        session.expunge(row)
        return row


def test_who_may_record_a_decision(db: Database, people: People) -> None:
    ref = add_app(db, people)
    for role, allowed in [
        ("manager", True),
        ("leader", True),
        ("steward", False),
        ("architect", False),
        ("member", False),
        ("admin", False),
        ("auditor", False),
    ]:
        if allowed:
            decide(db, people, role, ref)
        else:
            with pytest.raises(PermissionDenied):
                decide(db, people, role, ref)
    outside = add_app(db, people, unit="CANCER")
    with pytest.raises(PermissionDenied):  # a leader of Immunology, outside it
        decide(db, people, "leader", outside)
    mine = add_app(db, people)
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, mine)
        records.set_owners(
            session,
            ME,
            APPLICATION,
            app,
            [{"account_id": people.accounts["manager"], "kind": "accountable"}],
        )
    with pytest.raises(PermissionDenied, match="accountable"):
        decide(db, people, "manager", mine)


def test_a_decision_is_checked(db: Database, people: People) -> None:
    ref = add_app(db, people)
    for bad in (
        {"disposition": "panic"},
        {"rationale": ""},
        {"review_on": (date.today() - timedelta(days=1)).isoformat()},
        {"disposition": "consolidate"},
        {"disposition": "replace", "successor": ref},
    ):
        with pytest.raises(Invalid):
            decide(db, people, "manager", ref, **bad)


def test_a_decision_keeps_what_was_recommended_and_supersedes_the_last(
    db: Database, people: People
) -> None:
    ref = add_app(db, people)
    first = decide(db, people, "manager", ref)
    assert (first.ref, first.recommendation, first.disposition) == ("DEC-0001", "invest", "invest")
    assert (
        first.review_on == date.today().replace(year=date.today().year + 1)
        or first.review_on > date.today()
    )
    second = decide(
        db,
        people,
        "manager",
        ref,
        disposition="tolerate",
        rationale="Budget is tight.",
        review_on=(date.today() + timedelta(days=90)).isoformat(),
    )
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert (app.disposition, app.review_on) == ("tolerate", second.review_on)
        told = decisions.history(session, app)
        assert [(d["ref"], d["superseded"], d["differed"]) for d in told] == [
            ("DEC-0002", False, True),
            ("DEC-0001", True, False),
        ]
        kept = session.get(ScoreSnapshot, second.snapshot_id)
        assert kept.digest == second.snapshot_digest and kept.recommendation == "invest"
        assert decisions.snapshot_of(session, ME, second.snapshot_id)["intact"] is True
        event = session.scalars(
            select(Event)
            .where(Event.subject_type == "decision", Event.action == "created")
            .order_by(Event.id.desc())
        ).first()
        assert event.changes["snapshot_digest"][1] == second.snapshot_digest
        assert applications.missing(session, app)["now"].count("decision") == 0


def test_a_mismatch_is_shown_and_changes_nothing(db: Database, people: People) -> None:
    ref = add_app(db, people)
    decide(db, people, "manager", ref, disposition="retire", rationale="Moving to the new system.")
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        result = assessment.score_one(session, app)
        assert result["recommendation"] == "invest"
        assert "mismatch" in [f["key"] for f in result["flags"]]
        row = next(r for r in decisions.portfolio(session, ME, {}) if r["ref"] == ref)
        assert (row["mismatch"], row["decision"], row["recommendation"]) == (
            True,
            "retire",
            "invest",
        )
    decide(db, people, "manager", ref, disposition="invest", rationale="We changed our minds.")
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert "mismatch" not in [f["key"] for f in assessment.score_one(session, app)["flags"]]


def test_the_decision_on_record_is_a_fact(db: Database, people: People) -> None:
    ref = add_app(
        db, people, funding="grant", grant_end=(date.today() + timedelta(days=100)).isoformat()
    )
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert "grant_ending" in [f["key"] for f in assessment.score_one(session, app)["flags"]]
    row = decide(db, people, "manager", ref)
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert "grant_ending" not in [f["key"] for f in assessment.score_one(session, app)["flags"]]
    with db.write(TESTER) as session:
        kept = session.get(Decision, row.id)
        kept.review_on = date.today() - timedelta(days=1)
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert "decision_review_due" in [
            f["key"] for f in assessment.score_one(session, app)["flags"]
        ]


def test_portfolio_snapshots(db: Database, people: People, as_role: Clients) -> None:
    refs = [add_app(db, people, name=f"App {n}") for n in range(3)]
    with db.write(ME.actor) as session:
        records.update(
            session,
            ME,
            APPLICATION,
            records.load(session, ME, APPLICATION, refs[0]),
            {"lifecycle": "retired"},
            version=1,
        )
    manager, member = as_role("manager"), as_role("member")
    assert member.post("/api/v1/portfolio-snapshots", json={"name": "Q4"}).status_code == 403
    taken = manager.post("/api/v1/portfolio-snapshots", json={"name": "2026 Q4"})
    assert taken.status_code == 201
    data = taken.json()["data"]
    assert (data["ref"], data["count"], len(data["rows"])) == ("PSN-0001", 2, 2)
    assert member.get("/api/v1/portfolio-snapshots").json()["data"][0]["name"] == "2026 Q4"
    with db.read() as session:
        digest = session.scalars(
            select(Event).where(Event.action == "portfolio.snapshot.digest")
        ).one()
        assert len(digest.changes["digest"]) == 64


def test_the_portfolio_withholds_cost_and_agrees_with_the_list_for_every_role(
    db: Database, people: People, as_role: Clients
) -> None:
    add_app(db, people)
    add_app(db, people, unit="CANCER", restricted=True)
    for role in ROLES:
        client = as_role(role)
        rows = client.get("/api/v1/portfolio").json()["data"]
        listed = client.get("/api/v1/applications", params={"limit": 200}).json()["data"]
        assert {r["ref"] for r in rows} == {r["ref"] for r in listed}, role
        for row in rows:
            card = next(r for r in listed if r["ref"] == row["ref"])
            assert row["annual_cost"] == card["annual_cost"], role
            assert row["recommendation"] == card["recommendation"]
    member_rows = as_role("member").get("/api/v1/portfolio").json()["data"]
    assert [r["annual_cost"] for r in member_rows] == ["withheld"]
    filtered = as_role("manager").get("/api/v1/portfolio", params={"unit": people.units["CANCER"]})
    assert filtered.json()["meta"]["total"] == 1


def test_deciding_through_the_api(db: Database, people: People, as_role: Clients) -> None:
    ref = add_app(db, people)
    leader = as_role("leader")
    page = leader.get(f"/api/v1/applications/{ref}").json()["data"]
    assert page["can"]["decide"] is True and page["decision"] is None
    assert (
        as_role("steward").get(f"/api/v1/applications/{ref}").json()["data"]["can"]["decide"]
        is False
    )
    done = leader.post(
        f"/api/v1/applications/{ref}/decisions",
        json={"disposition": "maintain", "rationale": "Steady as it is."},
    )
    assert done.status_code == 201 and done.json()["data"]["differed"] is True
    page = leader.get(f"/api/v1/applications/{ref}").json()["data"]
    assert page["decision"]["disposition"] == "maintain"
    mismatches = leader.get("/api/v1/portfolio", params={"mismatch": True}).json()["data"]
    assert [r["ref"] for r in mismatches] == [ref]
    snapshot = leader.get(f"/api/v1/score-snapshots/{done.json()['data']['snapshot_id']}")
    assert snapshot.status_code == 200 and snapshot.json()["data"]["intact"] is True


def test_owners_record_their_own_decisions_only_where_the_program_allows_and_it_shows(
    db: Database, people: People
) -> None:
    """Off by default: nobody decides about their own application. A team too small for
    anyone else to may switch it on; then a manager or leader who is also the accountable
    owner may decide, and the decision says so everywhere it is shown."""
    from appwren.inventory import history as record_history
    from appwren.program import catalog, editing, packs
    from appwren.reporting import portfolio_list

    mine = add_app(db, people)
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, mine)
        records.set_owners(
            session, ME, APPLICATION, app,
            [{"account_id": people.accounts["manager"], "kind": "accountable"}],
        )  # fmt: skip
    with pytest.raises(PermissionDenied, match="accountable"):
        decide(db, people, "manager", mine)
    with db.write(ME.actor) as session, pytest.raises(PermissionDenied):
        editing.save_decision_rules(
            session, who(db, people, "steward"), {"owners_may_decide": True}
        )
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        assert editing.save_decision_rules(session, manager, {"owners_may_decide": True}) == {
            "owners_may_decide": True, "stage_gates": True,
        }  # fmt: skip
    row = decide(db, people, "manager", mine)
    assert row.self_recorded is True
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, mine)
        shown = decisions.history(session, app)[0]
        assert shown["self_recorded"] is True
        titles = [item["title"] for item in record_history.for_record(session, APPLICATION, app)]
        assert any(t.endswith("as its own accountable owner") for t in titles)
        listed = next(r for r in portfolio_list(session, manager, {}) if r["ref"] == mine)
        assert listed["self_decided"] is True
        rules = packs.export(session)["decision_rules"]
        assert rules == {"owners_may_decide": True, "stage_gates": True}
        assert catalog.check_decision_rules({"owners_may_decide": "yes"})
    # Only the exclusion is lifted: an owner without a manager's or leader's role still cannot.
    member_app = add_app(db, people)
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, member_app)
        records.set_owners(
            session, ME, APPLICATION, app,
            [{"account_id": people.accounts["member"], "kind": "accountable"}],
        )  # fmt: skip
    with pytest.raises(PermissionDenied, match="manager"):
        decide(db, people, "member", member_app)
    other = decide(db, people, "leader", member_app)
    assert other.self_recorded is False
    with db.write(manager.actor) as session:
        editing.save_decision_rules(session, manager, {"owners_may_decide": False})
    with pytest.raises(PermissionDenied, match="accountable"):
        decide(db, people, "manager", mine)
