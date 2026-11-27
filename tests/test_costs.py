"""What applications cost, what pays, and the contracts behind them; the cost factors; and
what an upgrade does to the scoring model (slice 4 of wave 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from appwren import assessment
from appwren.core import clock
from appwren.core.errors import Invalid
from appwren.db.engine import Database
from appwren.inventory import history, records
from appwren.inventory.registry import APPLICATION, CONTRACT, FUNDING_SOURCE, VENDOR
from appwren.landscape import costs
from appwren.program import packs
from tests.people import ME, ROLES, People
from tests.test_inventory import add_app, shared, who

Clients = Callable[[str | None], TestClient]
TODAY = clock.today()  # the application works in UTC


def contract(db: Database, covers: list[tuple[str, int | None]], **values: Any) -> str:
    with db.write(ME.actor) as session:
        vendor = values.pop("vendor_id", None) or shared_in(session, "Larkfield")
        record = records.create(
            session, ME, CONTRACT, {"name": "Larkfield licenses", "vendor_id": vendor, **values}
        )
        costs.set_applications(
            session, ME, record, [{"application": a, "licenses_used": used} for a, used in covers]
        )
        return record.ref


def shared_in(session: Any, name: str) -> str:
    return records.create(session, ME, VENDOR, {"name": name, "kind": "software_vendor"}).ref


def factor(result: dict[str, Any], key: str) -> dict[str, Any]:
    return next(f for f in result["dimensions"]["cost_burden"]["factors"] if f["key"] == key)


def test_cost_lines_add_up_to_the_annual_cost(
    as_role: Clients, db: Database, people: People
) -> None:
    grant = shared(db, FUNDING_SOURCE, name="Award R01", kind="grant", code="R01-BW-1")
    app = add_app(db, people, name="Tracker", annual_cost=1000, users=40)
    steward = as_role("steward")
    assert steward.get(f"/api/v1/applications/{app}/costs").json()["data"]["lines"] == []
    saved = steward.put(
        f"/api/v1/applications/{app}/cost-lines",
        json={"lines": [
            {"category": "hosting", "amount": 12000, "funding_source": grant},
            {"category": "internal", "amount": 30000, "note": "A third of an engineer"},
        ]},
    )  # fmt: skip
    assert saved.status_code == 200, saved.text
    found = saved.json()["data"]
    assert found["annual_cost"] == 42000 and found["per_user"] == 1050
    assert found["by_category"] == {"hosting": 12000, "internal": 30000}
    assert found["lines"][0]["funding_source"]["ref"] == grant
    record = steward.get(f"/api/v1/applications/{app}").json()["data"]
    assert record["annual_cost"] == 42000
    # The figure is the sum of the lines now, and is no longer typed in.
    typed = steward.patch(
        f"/api/v1/applications/{app}", json={"version": record["version"], "annual_cost": 5}
    )
    assert typed.status_code == 422 and "sum of its cost lines" in typed.text
    same = steward.patch(
        f"/api/v1/applications/{app}",
        json={"version": record["version"], "annual_cost": 42000, "users": 60},
    )
    assert same.status_code == 200
    wrong = steward.put(
        f"/api/v1/applications/{app}/cost-lines",
        json={"lines": [{"category": "magic", "amount": 1}]},
    )
    assert wrong.status_code == 422
    # A funding source's page adds up what it pays for.
    source = steward.get(f"/api/v1/funding-sources/{grant}").json()["data"]
    assert (source["cost_total"], len(source["cost_lines"])) == (12000, 1)


def test_cost_lines_are_withheld_with_the_cost(
    as_role: Clients, db: Database, people: People
) -> None:
    grant = shared(db, FUNDING_SOURCE, name="Award R01", kind="grant")
    app = add_app(db, people, name="Tracker", users=40)
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, app)
        costs.set_lines(
            session, ME, record,
            [{"category": "license", "amount": 9000, "funding_source": grant}],
        )  # fmt: skip
    for role in ROLES:
        client = as_role(role)
        sees = role != "member"  # everyone else here has a role over it, or reads everything
        answer = client.get(f"/api/v1/applications/{app}/costs").json()["data"]
        assert answer["withheld"] is (not sees), role
        assert ("lines" in answer) is sees
        shown = client.get(f"/api/v1/applications/{app}").json()["data"]
        assert shown["annual_cost"] == (9000 if sees else "withheld")
        told = client.get(f"/api/v1/applications/{app}/history").json()["data"]
        assert any("cost line" in item["title"] for item in told) is sees, role
        source = client.get(f"/api/v1/funding-sources/{grant}").json()["data"]
        assert source["cost_lines"][0]["amount"] == (9000 if sees else "withheld")
        assert source["cost_total"] == (9000 if sees else None)
        row = client.get("/api/v1/funding-sources").json()["data"][0]
        whole = role in ("manager", "architect", "auditor", "admin")
        assert row["application_count"] == 1 and row["total"] == (9000 if whole else None)
    refused = as_role("member").put(f"/api/v1/applications/{app}/cost-lines", json={"lines": []})
    assert refused.status_code == 403
    with db.read() as session:
        record = records.load(session, ME, APPLICATION, app)
        quiet = history.for_record(
            session, APPLICATION, record, withheld=frozenset({"annual_cost"})
        )
        assert not any("cost line" in item["title"] for item in quiet)


def test_who_may_see_and_keep_a_contract(as_role: Clients, db: Database, people: People) -> None:
    ours = add_app(db, people, name="Ours")  # the steward's and the leader's
    theirs = add_app(db, people, role="manager", unit="CANCER", name="Theirs")
    secret = add_app(db, people, role="manager", unit="CANCER", name="Secret", restricted=True)
    joint = contract(db, [(ours, 10), (secret, 5)], licenses=20, annual_value=50000)
    apart = contract(db, [(theirs, None)], name="Their support")
    empty = contract(db, [], name="Signed, not yet used")
    expect = {
        "member": set(),
        "steward": {joint},
        "leader": {joint},
        "manager": {joint, apart, empty},
        "architect": {joint, apart, empty},
        "auditor": {joint, apart, empty},
        "admin": {joint, apart, empty},
    }
    for role, seen in expect.items():
        client = as_role(role)
        listed = client.get("/api/v1/contracts").json()
        assert {row["ref"] for row in listed["data"]} == seen, role
        assert listed["meta"]["total"] == len(seen)
        for ref in (joint, apart, empty):
            assert client.get(f"/api/v1/contracts/{ref}").status_code == (
                200 if ref in seen else 404
            ), (role, ref)
        exported = client.get("/api/v1/exports/contracts", params={"format": "json"}).json()
        assert {row["ref"] for row in exported["rows"]} == seen
        around = client.get(f"/api/v1/graph/{ours}").json()["data"]
        covered = [g for g in around["groups"] if g["key"] == "covered_by"]
        assert bool(covered) is (joint in seen)
    # Seen through one application, a contract does not name another the reader may not see.
    shown = as_role("steward").get(f"/api/v1/contracts/{joint}").json()["data"]
    assert [a["name"] for a in shown["applications"]] == ["Ours"]
    assert shown["licenses_used"] == 15  # the count is the contract's own
    # The steward keeps it, through the application; what they cannot see stays as it was.
    kept = as_role("steward").put(
        f"/api/v1/contracts/{joint}/applications",
        json={"applications": [{"application": ours, "licenses_used": 12}]},
    )
    assert kept.status_code == 200
    whole = as_role("manager").get(f"/api/v1/contracts/{joint}").json()["data"]
    assert {a["name"]: a["licenses_used"] for a in whole["applications"]} == {
        "Ours": 12,
        "Secret": 5,
    }
    assert (
        as_role("leader")
        .patch(f"/api/v1/contracts/{joint}", json={"version": whole["version"], "number": "X"})
        .status_code
        == 403
    )
    naming = as_role("steward").put(
        f"/api/v1/contracts/{joint}/applications",
        json={"applications": [{"application": secret}]},
    )
    assert naming.status_code == 422 and f"There is no application {secret}" in naming.text
    # Who may add one.
    for role, allowed in [
        ("steward", True),
        ("architect", True),
        ("manager", True),
        ("member", False),
        ("leader", False),
    ]:
        made = as_role(role).post(
            "/api/v1/contracts", json={"name": f"By {role}", "vendor_id": "VEN-0001"}
        )
        assert made.status_code == (201 if allowed else 403), role
    with pytest.raises(Invalid):
        contract(db, [], name="Backwards", starts_on="2026-05-01", ends_on="2026-04-01")


def test_the_cost_factors_and_what_they_withhold(db: Database, people: People) -> None:
    lean = add_app(db, people, name="Lean", annual_cost=3000, users=300, sourcing="saas")
    idle = add_app(db, people, name="Idle", annual_cost=40000, users=20, sourcing="saas")
    bare = add_app(db, people, name="Bare", users=20)
    contract(db, [(lean, 30), (idle, 25)], licenses=100)
    with db.read() as session:
        apps = {name: records.load(session, ME, APPLICATION, ref) for name, ref in
                (("lean", lean), ("idle", idle), ("bare", bare))}  # fmt: skip
        scored = {name: assessment.score_one(session, app) for name, app in apps.items()}
        per_user = factor(scored["lean"], "cost_per_user")
        assert (per_user["value"], per_user["level"]) == (10, 5)  # 3,000 over 300 people
        assert factor(scored["idle"], "cost_per_user")["level"] == 2  # 2,000 a person
        missing = factor(scored["bare"], "cost_per_user")
        assert (missing["state"], missing["where"]) == ("unknown", "annual_cost")
        # 55 of the 100 licenses bought are in use, whichever application is asked.
        for name in ("lean", "idle"):
            use = factor(scored[name], "license_use")
            assert (use["value"], use["level"]) == (55, 2), name
        assert factor(scored["bare"], "license_use")["state"] == "not_applicable"
        # A member sees the scores, and none of what would give the cost away.
        hidden = assessment.shown(session, who(db, people, "member"), apps["lean"], scored["lean"])
        for key in ("annual_cost", "cost_per_user", "license_use"):
            assert factor(hidden, key)["value"] == "withheld", key
        assert hidden["scores"] == scored["lean"]["scores"]


def test_contracts_raise_flags(db: Database, people: People) -> None:
    clinic = add_app(db, people, name="Clinic", data_classes=["health"], sourcing="saas")
    plain = add_app(db, people, name="Plain", data_classes=["internal"], sourcing="saas")
    calm = add_app(db, people, name="Calm", data_classes=["health"], sourcing="saas")
    soon = (TODAY + timedelta(days=100)).isoformat()
    far = (TODAY + timedelta(days=900)).isoformat()
    contract(db, [(clinic, None), (plain, None)], ends_on=soon, notice_days=60,
             data_agreement="missing")  # fmt: skip
    contract(db, [(calm, None)], name="Calm's", ends_on=far, notice_days=60,
             data_agreement="in_place")  # fmt: skip
    with db.read() as session:

        def flags(ref: str) -> set[str]:
            app = records.load(session, ME, APPLICATION, ref)
            return {f["key"] for f in assessment.score_one(session, app)["flags"]}

        assert {"contract_notice", "no_data_agreement"} <= flags(clinic)
        assert "contract_notice" in flags(plain) and "no_data_agreement" not in flags(plain)
        assert not {"contract_notice", "no_data_agreement"} & flags(calm)
        ending, _ = records.search(session, ME, CONTRACT, {"ending_within": "120"})
        assert [row.name for row in ending] == ["Larkfield licenses"]
        card = records.cards(session, ME, CONTRACT, ending)[0]
        assert (card["days_to_notice"], card["days_to_end"]) == (40, 100)


def test_the_breakdown_is_for_those_who_see_every_cost(db: Database, people: People) -> None:
    grant = shared(db, FUNDING_SOURCE, name="Award R01", kind="grant")
    lined = add_app(db, people, name="Lined")
    typed = add_app(db, people, name="Typed", annual_cost=5000, funding="operating")
    add_app(db, people, name="Unknown")
    with db.write(ME.actor) as session:
        record = records.load(session, ME, APPLICATION, lined)
        costs.set_lines(session, ME, record, [
            {"category": "hosting", "amount": 7000, "funding_source": grant},
            {"category": "license", "amount": 3000},
        ])  # fmt: skip
    with db.read() as session:
        ids = [records.load(session, ME, APPLICATION, ref).id for ref in (lined, typed)]
        ids.append(records.load(session, ME, APPLICATION, "APP-0003").id)
        found = costs.breakdown(session, who(db, people, "manager"), ids)
        assert found is not None and (found["total"], found["unknown"]) == (15000, 1)
        assert {row["label"]: row["amount"] for row in found["by_category"]} == {
            "Hosting": 7000, "Not broken down": 5000, "License or subscription": 3000,
        }  # fmt: skip
        assert {row["label"]: row["amount"] for row in found["by_funding"]} == {
            "Award R01": 7000, "Operating budget": 5000, "No source named": 3000,
        }  # fmt: skip
        assert costs.breakdown(session, who(db, people, "steward"), ids) is None
        assert costs.breakdown(session, who(db, people, "member"), ids) is None


def test_an_upgrade_brings_the_new_model_only_to_an_unshaped_one(
    db: Database, people: People
) -> None:
    earlier = json.loads(
        Path(__file__).parent.joinpath("fixtures", "scoring-0.1.0.json").read_text()
    )
    assert assessment.digest(earlier) in assessment.earlier_defaults("scoring")
    with db.write(ME.actor) as session:
        # As 0.1.0 left it: its default model, unchanged.
        assessment.publish_model(session, earlier, "Program pack")
        assert assessment.current_model(session).definition == earlier
        assert packs.install(session)["scoring"] == 1
        current = assessment.current_model(session)
        keys = [f["key"] for f in current.definition["profiles"][-1]["factors"]["cost_burden"]]
        assert "cost_per_user" in keys and current.published_by == "AppWren upgrade"
        assert packs.install(session)["scoring"] == 0  # and nothing the second time
        # An organization that has shaped its model keeps it.
        shaped = json.loads(json.dumps(earlier))
        shaped["thresholds"]["confidence"] = 60
        assessment.publish_model(session, shaped, "Portfolio team")
        assert packs.install(session)["scoring"] == 0
        assert assessment.current_model(session).definition["thresholds"]["confidence"] == 60
