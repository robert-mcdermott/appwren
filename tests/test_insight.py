"""Trends between snapshots, scores over time, and shares of the portfolio (slice 1 of
wave 6)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren import assessment, decisions
from appwren.db.engine import Database
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.people import ME, People
from tests.test_decisions import add_app, decide, who

Clients = Callable[[str | None], TestClient]

QUESTIONS = ("strategic_fit", "functional_fit", "future_need", "reliability", "maintainability",
             "vendor_viability", "support_effort", "change_effort", "compliance")  # fmt: skip
POOR = dict.fromkeys(QUESTIONS, 1)


def snapshot(db: Database, people: People, name: str) -> str:
    manager = who(db, people, "manager")
    with db.write(manager.actor) as session:
        return decisions.take_portfolio_snapshot(session, manager, name).ref


def test_two_snapshots_say_what_moved_between_them(
    as_role: Clients, db: Database, people: People
) -> None:
    steady = add_app(db, people, name="Steady")
    falling = add_app(db, people, name="Falling")
    secret = add_app(db, people, name="Secret", restricted=True, unit="CANCER")
    first = snapshot(db, people, "Spring")
    with db.write(ME.actor) as session:  # its answers turn poor: its scores fall
        app = records.load(session, ME, APPLICATION, falling)
        assessment.record(session, ME, app, POOR)
    decide(db, people, "manager", steady, disposition="maintain")
    added = add_app(db, people, name="Added later")
    second = snapshot(db, people, "Summer")
    member = as_role("member")
    said = member.get("/api/v1/trends", params={"before": first, "after": second})
    assert said.status_code == 200, said.text
    found = said.json()["data"]
    assert found["before"]["figures"]["scored"] == 2  # the restricted one is not counted
    assert found["after"]["figures"]["scored"] == 3
    names = {item["name"] for item in found["moved"]["scores"]}
    assert names == {"Falling"}
    change = found["moved"]["scores"][0]["changes"]
    assert all(c["to"] < c["from"] for c in change.values())
    assert [item["name"] for item in found["added"]] == ["Added later"]
    assert [(d["name"], d["disposition"]) for d in found["decided"]] == [("Steady", "maintain")]
    assert all(item["name"] != "Secret" for group in found["moved"].values() for item in group)
    # The manager, who may see everything, sees the restricted one counted.
    whole = as_role("manager").get("/api/v1/trends", params={"before": first}).json()["data"]
    assert whole["before"]["figures"]["scored"] == 3 and whole["after"]["name"] == "Today"
    assert (
        member.get("/api/v1/trends", params={"before": second, "after": first}).status_code == 422
    )
    # An application's scores over time: a point at each snapshot, and one for its decision.
    points = member.get(f"/api/v1/applications/{falling}/score-history").json()["data"]
    assert [p["reason"] for p in points] == ["portfolio", "portfolio"]
    assert points[1]["scores"]["business_value"] < points[0]["scores"]["business_value"]
    assert len(member.get(f"/api/v1/applications/{steady}/score-history").json()["data"]) == 3
    assert secret and added


def test_shares_of_the_portfolio(as_role: Clients, db: Database, people: People) -> None:
    for index in range(10):
        add_app(db, people, name=f"App {index}", annual_cost=1000 * (index + 1),
                users=10 * (index + 1))  # fmt: skip
    add_app(db, people, name="No cost", annual_cost=None, users=None)
    found = as_role("manager").get("/api/v1/shares").json()["data"]
    by_key = {share["key"]: share for share in found["shares"]}
    costliest = by_key["costliest"]
    assert [item["name"] for item in costliest["items"]] == ["App 9"]
    assert (costliest["of"], costliest["not_known"]) == (10, 1)
    least = by_key["least_used"]
    assert [item["name"] for item in least["items"]] == ["App 0", "App 1"]  # a fifth of ten
    assert least["threshold"] == 20


def test_a_report_is_kept_as_it_was_made(as_role: Clients, db: Database, people: People) -> None:
    from datetime import timedelta

    from appwren.core import clock
    from appwren.db.models import Report

    kept = add_app(db, people, name="Kept", annual_cost=12_000)
    decide(db, people, "manager", kept, disposition="maintain")
    snapshot(db, people, "Start")
    snapshot(db, people, "End")
    manager = as_role("manager")
    on = clock.today()
    period = {"title": "This quarter", "period_from": (on - timedelta(days=90)).isoformat(),
              "period_to": on.isoformat()}  # fmt: skip
    assert as_role("leader").post("/api/v1/reports", json=period).status_code == 403
    late = {**period, "period_to": (on + timedelta(days=1)).isoformat()}
    assert manager.post("/api/v1/reports", json=late).status_code == 422
    backwards = {**period, "period_from": on.isoformat(),
                 "period_to": (on - timedelta(days=1)).isoformat()}  # fmt: skip
    assert manager.post("/api/v1/reports", json=backwards).status_code == 422
    made = manager.post("/api/v1/reports", json=period)
    assert made.status_code == 201, made.text
    report = made.json()["data"]
    assert report["ref"].startswith("RPT-") and report["intact"] and len(report["digest"]) == 64
    content = report["content"]
    assert content["decided"]["count"] == 1
    assert content["decided"]["items"][0]["name"] == "Kept"
    assert content["portfolio"]["total"] == 1 and content["portfolio"]["cost"] == 12_000
    assert content["movement"]["before"]["name"] == "Start"
    # The records change; the report does not.
    add_app(db, people, name="Added after")
    decide(db, people, "manager", kept, disposition="invest")
    again = as_role("auditor").get(f"/api/v1/reports/{report['ref']}").json()["data"]
    assert again["content"] == content and again["digest"] == report["digest"] and again["intact"]
    assert [row["ref"] for row in manager.get("/api/v1/reports").json()["data"]] == [report["ref"]]
    assert as_role("member").get(f"/api/v1/reports/{report['ref']}").status_code == 403
    # Anything altered behind it shows: the digest no longer matches.
    with db.read() as session:
        row = session.query(Report).one()
        tampered = {**row.content, "decided": {"count": 0}}
    with db.engine.begin() as connection:  # behind the application's back
        connection.execute(Report.__table__.update().values(content=tampered))
    assert not manager.get(f"/api/v1/reports/{report['ref']}").json()["data"]["intact"]


def test_an_application_and_the_portfolio_as_they_stood(
    as_role: Clients, db: Database, people: People
) -> None:
    from datetime import timedelta

    from appwren.core import clock

    now = clock.utc_now()
    ago = lambda days: now - timedelta(days=days)  # noqa: E731
    with clock.frozen_at(ago(10)):
        ref = add_app(db, people, name="Tissue Log", users=120, lifecycle="active")
    with clock.frozen_at(ago(8)):
        decide(db, people, "manager", ref, disposition="maintain")
        snapshot(db, people, "Back then")
    with clock.frozen_at(ago(2)):
        with db.write(ME.actor) as session:
            app = records.load(session, ME, APPLICATION, ref)
            records.update(session, ME, APPLICATION, app,
                           {"name": "Tissue Register", "users": 300,
                            "lifecycle": "phase_in"}, version=app.version)  # fmt: skip
        decide(db, people, "manager", ref, disposition="replace")
    later = add_app(db, people, name="Came later")
    member = as_role("member")
    then = (now - timedelta(days=5)).date().isoformat()
    found = member.get(f"/api/v1/applications/{ref}/as-of", params={"on": then}).json()["data"]
    assert found["existed"] and found["changes_since"] >= 1
    values = {row["field"]: row for row in found["fields"]}
    assert (values["name"]["then"], values["name"]["now"]) == ("Tissue Log", "Tissue Register")
    assert (values["users"]["then"], values["users"]["now"]) == (120, 300)
    assert values["lifecycle"]["then"] == "Active" and values["lifecycle"]["changed"]
    assert not values["tier"]["changed"]
    assert found["decision"]["disposition"] == "maintain"
    assert found["scores"]["snapshot"]["name"] == "Back then"
    # Before it was created, it was not on record.
    early = (now - timedelta(days=20)).date().isoformat()
    gone = member.get(f"/api/v1/applications/{ref}/as-of", params={"on": early}).json()["data"]
    assert gone["existed"] is False
    # The portfolio on that day: it, as it was, and not the one added since.
    whole = member.get("/api/v1/as-of", params={"on": then}).json()["data"]
    names = {row["name_then"]: row for row in whole["applications"]}
    assert "Came later" not in names and later
    row = names["Tissue Log"]
    assert (row["lifecycle"], row["lifecycle_now"]) == ("active", "phase_in")
    assert (row["decision"], row["decision_now"]) == ("maintain", "replace")
    assert whole["since"]["added"] == 1
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    assert member.get("/api/v1/as-of", params={"on": tomorrow}).status_code == 422
