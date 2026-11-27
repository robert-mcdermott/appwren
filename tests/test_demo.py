"""The demo organization: built through the real services, the same for the same seed, and
every storyline in spec/demo-organization.md as it says (slice 8 of wave 1)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, decisions, reporting
from appwren.api.app import create_app
from appwren.db.engine import Database
from appwren.db.models import Application, HostingPlatform, PortfolioSnapshot, Technology
from appwren.demo import build
from appwren.events import chain
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION, CONTRACT, DEPLOYMENT, INTERFACE, TECHNOLOGY
from appwren.landscape import costs, graph, hosting, interfaces, overlap
from tests.conftest import Instance
from tests.people import ME

TODAY = date.today()


def app_named(session: Any, name: str) -> Application:
    return session.scalars(select(Application).where(Application.name == name)).one()


def scored(session: Any, name: str) -> dict[str, Any]:
    return assessment.score_one(session, app_named(session, name))


def flags(result: dict[str, Any]) -> set[str]:
    return {flag["key"] for flag in result["flags"]}


def test_the_demo_tells_every_storyline(db: Database) -> None:
    summary = build.build(db, seed=1)
    assert summary.counts["applications"] >= 100 and summary.counts["decisions"] >= 50
    assert summary.counts["portfolio snapshots"] == 4
    assert {a["email"].split("@")[1] for a in summary.sample_accounts} == {"bramblewood.example"}
    with db.engine.connect() as conn:
        assert chain.verify(conn).ok
    with db.read() as session:
        # The worked example, exactly as spec/engine.md has it.
        tracker = scored(session, "Specimen Tracker")
        assert tracker["scores"] == {
            "business_value": 4.1,
            "technical_health": 2.5,
            "cost_burden": 2.7,
            "risk_exposure": 2.1,
        }
        assert (tracker["confidence"], tracker["recommendation"]) == (95, "modernize")
        assert flags(tracker) == {"restricted_unsupported", "grant_ending", "single_maintainer"}
        # Three tools for one job: one consolidates into the primary; the clinic's stays.
        old = scored(session, "Old Surveys")
        assert old["recommendation"] == "consolidate"
        assert old["overlap_with"]["name"] == "Survey Hub"
        clinic = app_named(session, "Clinic Questionnaires")
        assert clinic.disposition == "maintain"
        # The grant ends; the single maintainer; the incubator.
        assert "grant_ending" in flags(scored(session, "Imaging Pipeline"))
        assert "single_maintainer" in flags(scored(session, "Cohort Analysis Platform"))
        assert scored(session, "Electronic Lab Notebook Pilot")["recommendation"] == "incubate"
        # The mismatch, due for review next month.
        scheduler = app_named(session, "Clinic Scheduler")
        result = assessment.score_one(session, scheduler)
        assert (result["recommendation"], scheduler.disposition) == ("replace", "maintain")
        assert "mismatch" in flags(result)
        assert TODAY < scheduler.review_on <= TODAY + timedelta(days=30)
        # The orphans: what the person who left answered for.
        rows = reporting.rows(session, ME, {})
        orphaned = {r["name"] for r in rows if "no_accountable" in r["quality"]}
        assert {
            "Executive Dashboards",
            "Applicant Tracking",
            "Space Planning",
            "Contracts Repository",
        } <= orphaned
        # Most records are complete, so what is missing stands out; the worked example lacks
        # nothing its stage requires.
        in_service = [r for r in rows if r["lifecycle"] not in ("retired", "archived")]
        assert sum(1 for r in in_service if r["missing_now"]) < len(in_service) / 2
        assert next(r for r in rows if r["name"] == "Specimen Tracker")["missing_now"] == []
        # Not enough to say: the spreadsheet nobody assessed.
        assess = [r for r in rows if r["recommendation"] == "assess"]
        assert len(assess) >= 12
        # The end of support: a database release used widely ends next quarter.
        postgres = session.scalars(select(Technology).where(Technology.name == "PostgreSQL")).one()
        shown = records.detail(session, ME, TECHNOLOGY, postgres)
        thirteen = next(r for r in shown["releases"] if r["cycle"] == "13")
        assert thirteen["support"] == "ending" and len(thirteen["used_by"]) >= 10
        # Retired properly, with its decision and successor.
        retired = app_named(session, "Old Reports Server")
        assert (retired.lifecycle, retired.status, retired.disposition) == (
            "retired",
            "retired",
            "retire",
        )
        history = decisions.history(session, retired)
        assert history[-1]["successor"]["name"] == "Executive Dashboards"
        # What passes between them: the worked example keeps exactly its three dependents,
        # and one flow delivers research data to dashboards whose record does not list it.
        tracker_value = tracker["dimensions"]["business_value"]["factors"]
        depends = next(f for f in tracker_value if f["key"] == "dependents")
        assert depends["why"] == "3 active applications depend on it"
        # What breaks if it goes: its three dependents, and the capability it alone provides.
        broken = graph.impact(session, ME, app_named(session, "Specimen Tracker"))
        assert {row["name"] for row in broken["direct"]} == {
            "Biorepository Request Portal",
            "Freezer Watch",
            "Research Data Warehouse",
        }
        assert [row["name"] for row in broken["capabilities_left"]] == ["Biospecimen management"]
        assert len(broken["beyond"]) >= 2 and len(broken["interfaces"]) == 3
        flows = interfaces.flows(session, ME, "identifiable_research")
        lost = [row["target"]["name"] for row in flows["interfaces"] if row["undeclared"]]
        assert lost == ["Executive Dashboards"] and flows["total"] >= 20
        everything, _ = records.search(session, ME, INTERFACE, {}, limit=200)
        marked = [
            c["name"] for c in records.cards(session, ME, INTERFACE, everything) if c["undeclared"]
        ]
        assert marked == ["Enrollment figures"]
        # Where it runs: what a vendor hosts has no deployment of ours, a tier 1 system in
        # the data center has a standby, and a platform's page lists what would stop with it.
        room = session.scalars(
            select(HostingPlatform).where(HostingPlatform.name == "Campus data center")
        ).one()
        running = hosting.running_on(session, ME, room)
        assert len({row["application"]["ref"] for row in running}) >= 10
        environments = {row["environment"] for row in running}
        assert environments == {"production", "staging"}
        standby, _ = records.search(session, ME, DEPLOYMENT, {"environment": "disaster_recovery"})
        assert standby and all(row.platform_id != room.id for row in standby)
        hosted, _ = records.search(
            session, ME, DEPLOYMENT, {"application": app_named(session, "Survey Hub").ref}
        )
        assert hosted == []  # a vendor runs it
        # What it costs: lines add up to the cost on record, so no score moved; a notice date
        # two weeks off; health data with no data agreement; and licenses going unused.
        lined = 0
        for app in session.scalars(select(Application).where(Application.status == "active")):
            lines = costs.lines_of(session, app)
            if lines:
                lined += 1
                assert sum(line["amount"] for line in lines) == app.annual_cost, app.name
        assert lined >= 60
        scheduler_flags = flags(scored(session, "Clinic Scheduler"))
        assert "contract_notice" in scheduler_flags
        assert "no_data_agreement" in flags(scored(session, "Clinic Questionnaires"))
        assert "no_data_agreement" not in flags(scored(session, "Survey Hub"))
        learning = scored(session, "Learning Management")["dimensions"]["cost_burden"]["factors"]
        unused = next(f for f in learning if f["key"] == "license_use")
        assert (unused["value"], unused["level"]) == (28, 1)
        due, _ = records.search(session, ME, CONTRACT, {"ending_within": "90"})
        assert "Calendra agreement" in [row.name for row in due]
        money = costs.breakdown(session, ME, [r["id"] for r in rows])
        assert money is not None and money["total"] == sum(
            r["annual_cost"] or 0 for r in rows if isinstance(r["annual_cost"], int | type(None))
        )
        assert {row["label"] for row in money["by_category"]} >= {
            "License or subscription", "Our own people's time", "Not broken down",
        }  # fmt: skip
        # Three tools for one job, side by side, with the hub as primary; and the map measured.
        twice = overlap.overlap(session, ME, {})
        surveys = next(c for c in twice["capabilities"] if c["name"] == "Participant surveys")
        assert [a["name"] for a in surveys["applications"]] == [
            "Survey Hub", "Clinic Questionnaires", "Old Surveys",
        ]  # fmt: skip
        assert surveys["applications"][0]["is_primary"] and surveys["consolidate"] >= 1
        assert len(reporting.portfolio_list(session, ME, surveys["filters"])) == 3
        heat = overlap.heat(session, ME, {})
        assert all(root["measures"]["applications"] > 0 for root in heat)
        # Quarterly snapshots, the last within a quarter of today.
        snaps = session.scalars(
            select(PortfolioSnapshot).order_by(PortfolioSnapshot.taken_at)
        ).all()
        assert len(snaps) == 4 and snaps[-1].taken_at.date() >= TODAY - timedelta(days=100)
        # Every application that is not retired has a unit and is visible to the organization.
        assert records.search(session, ME, APPLICATION, {"status": "active"})[1] >= 100


def _names(session: Any) -> list[tuple[str, str, str | None]]:
    rows = session.scalars(select(Application).order_by(Application.ref))
    return [(row.ref, row.name, row.disposition) for row in rows]


def test_the_same_seed_gives_the_same_organization(db: Database, tmp_path: Any) -> None:
    from appwren.db import migrate

    other = Database(f"sqlite:///{tmp_path / 'again.db'}")
    migrate.upgrade(other.engine)
    try:
        first = build.build(db, seed=3, today=TODAY)
        second = build.build(other, seed=3, today=TODAY)
        assert first.counts == second.counts
        with db.read() as a, other.read() as b:
            assert _names(a) == _names(b)
    finally:
        other.dispose()


def test_a_demo_signs_in_its_sample_people_and_nobody_else(instance: Instance) -> None:
    summary = build.build(instance.db, seed=1)
    with TestClient(create_app(instance.config), base_url="http://localhost") as client:
        meta = client.get("/api/v1/meta").json()["data"]
        assert meta["demo"]["accounts"][0]["email"] == summary.sample_accounts[0]["email"]
        sample = summary.sample_accounts[1]["email"]
        assert client.post("/api/v1/session/demo", json={"email": sample}).status_code == 200
        assert client.get("/api/v1/session").json()["data"]["account"]["email"] == sample
        # Signed in already, the sign-in page can switch to another sample person, as it can
        # sign in again with a password: a new session needs no token from the old one.
        another = summary.sample_accounts[2]["email"]
        assert client.post("/api/v1/session/demo", json={"email": another}).status_code == 200
        assert client.get("/api/v1/session").json()["data"]["account"]["email"] == another
    with TestClient(create_app(instance.config), base_url="http://localhost") as other:
        nobody = other.post("/api/v1/session/demo", json={"email": "someone@bramblewood.example"})
        assert nobody.status_code == 404
