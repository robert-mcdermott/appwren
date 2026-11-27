"""What the second review of the threat table found, before 0.9.0: each test failed before
its fix. The record is spec/reviews/2026-11-security-and-accessibility.md."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from appwren.api.app import create_app
from appwren.db.engine import Database
from appwren.db.models import RecordLink
from appwren.inventory import parts, records
from appwren.inventory.registry import (
    APPLICATION,
    COMPONENT,
    CONTRACT,
    HOSTING_PLATFORM,
    TECHNOLOGY,
    VENDOR,
)
from appwren.landscape import costs
from appwren.people import accounts
from tests.conftest import Instance
from tests.people import ME, PASSWORD, People, email_of
from tests.test_decisions import add_app
from tests.test_inventory import add_app as add_kept_app
from tests.test_sso import NEW, World, admin_client, world  # noqa: F401  (world is a fixture)

Clients = Callable[[str | None], TestClient]
FROM = ("203.0.113.9", 50000)  # an address on the network, not this machine


def _version(client: TestClient, path: str) -> int:
    return client.get(path).json()["data"]["version"]


def mark(as_role: Clients, *names: str) -> None:
    admin = as_role("admin")
    program = admin.get("/api/v1/program").json()["data"]
    saved = admin.put(
        "/api/v1/program/fields",
        json={
            "fields": program["fields"],
            "sensitive_fields": [*program["sensitive_fields"], *names],
        },
    )
    assert saved.status_code == 200, saved.text


# --- Finding 1: a provider's person gives themselves no password ------------------------------


def test_a_provider_person_cannot_give_themselves_a_password(world: World) -> None:  # noqa: F811
    admin = admin_client(world)
    admin.put("/api/v1/sso/mappings", json={"mappings": [
        {"claim_value": "hale-lab", "role": "manager"}]})  # fmt: skip
    client = world.client()
    world.round_trip(client, NEW.subject)
    me = world.who(client)
    assert me["has_password"] is False
    client.headers["X-CSRF-Token"] = me["csrf_token"]
    made = client.post("/api/v1/session/password",
                       json={"new_password": "a password of my very own 42"})  # fmt: skip
    assert made.status_code == 403, made.text
    later = world.client()
    signed = later.post("/api/v1/session", json={
        "email": NEW.email, "password": "a password of my very own 42"})  # fmt: skip
    assert signed.status_code == 401


# --- Finding 2: a record is not moved onto an application one does not keep ------------------


def test_a_component_is_not_moved_onto_an_application_one_does_not_keep(
    as_role: Clients, db: Database, people: People
) -> None:
    mine = add_kept_app(db, people, name="Hale Samples", unit="HALE")
    theirs = add_kept_app(db, people, role="manager", name="Cancer Registry", unit="CANCER")
    steward = as_role("steward")
    made = steward.post("/api/v1/components", json={
        "name": "Old Server", "kind": "service", "application_id": mine})  # fmt: skip
    ref = made.json()["data"]["ref"]
    moved = steward.patch(
        f"/api/v1/components/{ref}",
        json={"version": _version(steward, f"/api/v1/components/{ref}"), "application_id": theirs},
    )
    assert moved.status_code == 403, moved.text
    assert steward.get(f"/api/v1/components/{ref}").json()["data"]["application"]["ref"] == mine
    # Moving one between two applications one keeps is still fine.
    other = add_kept_app(db, people, name="Hale Freezers", unit="HALE")
    again = steward.patch(
        f"/api/v1/components/{ref}",
        json={"version": _version(steward, f"/api/v1/components/{ref}"), "application_id": other},
    )
    assert again.status_code == 200, again.text


def test_a_deployment_is_not_moved_onto_an_application_one_does_not_keep(
    as_role: Clients, db: Database, people: People
) -> None:
    mine = add_kept_app(db, people, name="Hale Samples", unit="HALE")
    theirs = add_kept_app(db, people, role="manager", name="Cancer Registry", unit="CANCER")
    with db.write(ME.actor) as session:
        platform = records.create(session, ME, HOSTING_PLATFORM, {
            "name": "Basement rack", "kind": "data_center"}).ref  # fmt: skip
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/deployments",
        json={"application_id": mine, "platform_id": platform, "environment": "production"},
    )
    ref = made.json()["data"]["ref"]
    moved = steward.patch(
        f"/api/v1/deployments/{ref}",
        json={"version": _version(steward, f"/api/v1/deployments/{ref}"), "application_id": theirs},
    )
    assert moved.status_code == 403, moved.text


def test_an_interface_is_not_pointed_between_applications_one_does_not_keep(
    as_role: Clients, db: Database, people: People
) -> None:
    mine = add_kept_app(db, people, name="Hale Samples", unit="HALE")
    other = add_kept_app(db, people, role="manager", name="Cancer Registry", unit="CANCER")
    third = add_kept_app(db, people, role="manager", name="Cancer Billing", unit="CANCER")
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/interfaces",
        json={"name": "Samples feed", "source_id": mine, "target_id": other, "method": "api"},
    )
    ref = made.json()["data"]["ref"]
    moved = steward.patch(f"/api/v1/interfaces/{ref}", json={
        "version": _version(steward, f"/api/v1/interfaces/{ref}"),
        "source_id": third, "data_classes": ["health"]})  # fmt: skip
    assert moved.status_code == 403, moved.text


def test_a_contract_covers_only_applications_its_editor_keeps(
    as_role: Clients, db: Database, people: People
) -> None:
    mine = add_kept_app(db, people, name="Hale Samples", unit="HALE")
    theirs = add_kept_app(db, people, role="manager", name="Cancer Registry", unit="CANCER",
                          data_classes=["personal"])  # fmt: skip
    with db.write(ME.actor) as session:
        vendor = records.create(session, ME, VENDOR, {"name": "Sample Vendor"}).ref
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/contracts",
        json={"name": "Steward's contract", "vendor_id": vendor, "data_agreement": "missing"},
    )
    ref = made.json()["data"]["ref"]
    covered = steward.put(f"/api/v1/contracts/{ref}/applications",
                          json={"applications": [{"application": theirs}]})  # fmt: skip
    assert covered.status_code == 422, covered.text
    assert (
        steward.put(
            f"/api/v1/contracts/{ref}/applications", json={"applications": [{"application": mine}]}
        ).status_code
        == 200
    )


def test_a_contract_keeps_what_it_says_of_applications_its_editor_does_not_keep(
    as_role: Clients, db: Database, people: People
) -> None:
    mine = add_kept_app(db, people, name="Hale Samples", unit="HALE")
    theirs = add_kept_app(db, people, role="manager", name="Cancer Registry", unit="CANCER")
    with db.write(ME.actor) as session:
        vendor = records.create(session, ME, VENDOR, {"name": "Sample Vendor"})
        contract = records.create(
            session, ME, CONTRACT, {"name": "Shared", "vendor_id": vendor.ref}
        )
        costs.set_applications(session, ME, contract, [{"application": mine},
                                                       {"application": theirs}])  # fmt: skip
        ref = contract.ref
    steward = as_role("steward")
    assert (
        steward.put(
            f"/api/v1/contracts/{ref}/applications", json={"applications": [{"application": mine}]}
        ).status_code
        == 200
    )
    covers = as_role("manager").get(f"/api/v1/contracts/{ref}").json()["data"]["applications"]
    assert {item["ref"] for item in covers} == {mine, theirs}


# --- Finding 3: a field marked sensitive is withheld everywhere ------------------------------


def test_narrowing_by_a_marked_data_class_tells_nothing(
    as_role: Clients, db: Database, people: People
) -> None:
    mark(as_role, "data_classes")
    ref = add_app(db, people, name="Clinic Notes", unit="CANCER", data_classes=["health"])
    member = as_role("member")
    listed = member.get("/api/v1/applications", params={"data_class": "health"})
    assert ref not in listed.text
    handled = member.get("/api/v1/data-handling", params={"data_class": "health"})
    assert ref not in handled.text
    # Those who see its sensitive fields still find it.
    assert ref in as_role("manager").get("/api/v1/applications",
                                         params={"data_class": "health"}).text  # fmt: skip


def test_narrowing_by_a_marked_audience_tells_nothing(
    as_role: Clients, db: Database, people: People
) -> None:
    mark(as_role, "audiences", "org_wide")
    ref = add_app(db, people, name="Pay Review", unit="CANCER", audiences=["managers"])
    everyone = add_app(db, people, name="Mail", unit="CANCER", org_wide=True)
    member = as_role("member")
    assert member.get(f"/api/v1/applications/{ref}").json()["data"]["audiences"] == "withheld"
    assert ref not in member.get("/api/v1/applications", params={"audience": "managers"}).text
    assert everyone not in member.get("/api/v1/applications",
                                      params={"used_in": people.units["HALE"]}).text  # fmt: skip


def test_the_portfolio_withholds_a_marked_tier(
    as_role: Clients, db: Database, people: People
) -> None:
    mark(as_role, "tier", "sourcing")
    ref = add_app(db, people, name="Clinic Notes", unit="CANCER", tier="1")
    rows = as_role("member").get("/api/v1/portfolio").json()["data"]
    row = next(item for item in rows if item["ref"] == ref)
    assert row["tier"] == "withheld" and row["sourcing"] == "withheld"


def test_the_stage_cannot_be_marked_sensitive(as_role: Clients) -> None:
    admin = as_role("admin")
    program = admin.get("/api/v1/program").json()["data"]
    refused = admin.put(
        "/api/v1/program/fields",
        json={
            "fields": program["fields"],
            "sensitive_fields": [*program["sensitive_fields"], "lifecycle"],
        },
    )
    assert refused.status_code == 422 and "organized" in refused.text


def test_what_breaks_withholds_a_marked_tier_and_users(
    as_role: Clients, db: Database, people: People
) -> None:
    mark(as_role, "tier", "users")
    core = add_app(db, people, name="Lab Core", unit="CANCER", tier="1", users=4000)
    leaf = add_app(db, people, name="Lab Leaf", unit="CANCER", tier="2", users=250)
    with db.write(ME.actor) as session:
        a = records.load(session, ME, APPLICATION, leaf)
        b = records.load(session, ME, APPLICATION, core)
        session.add(RecordLink(from_type="application", from_id=a.id, to_type="application",
                               to_id=b.id, relation="depends_on"))  # fmt: skip
    told = as_role("member").get(f"/api/v1/applications/{core}/impact").json()["data"]
    assert told["users"] == "withheld" and told["people"] is None
    assert told["direct"][0]["tier"] == "withheld"


def test_a_flag_that_reads_a_marked_field_is_not_named(
    as_role: Clients, db: Database, people: People
) -> None:
    mark(as_role, "data_classes")
    ref = add_app(db, people, name="Clinic Notes", unit="CANCER", data_classes=["health"],
                  sourcing="built_here")  # fmt: skip
    with db.write(ME.actor) as session:
        tech = records.create(session, ME, TECHNOLOGY, {"name": "Java", "kind": "language"})
        parts.set_releases(
            session,
            ME,
            tech,
            [{"cycle": "8", "support_ends": (date.today() - timedelta(days=10)).isoformat()}],
        )
        component = records.create(session, ME, COMPONENT, {
            "name": "Server", "kind": "service", "application_id": ref})  # fmt: skip
        parts.set_technologies(session, ME, component, [{"technology": tech.ref, "release": "8"}])
    keys = {
        flag["key"]
        for flag in as_role("manager")
        .get("/api/v1/applications", params={"q": "Clinic Notes"})
        .json()["data"][0]["flags"]
    }
    assert "restricted_unsupported" in keys  # control: it is raised
    member = as_role("member")
    said = member.get(f"/api/v1/checkpoint/{ref}").json()["data"]
    assert not any("Restricted data" in text for text in said["flags"]), said["flags"]
    listed = member.get("/api/v1/applications", params={"q": "Clinic Notes"}).json()["data"][0]
    assert "restricted_unsupported" not in {flag["key"] for flag in listed["flags"]}


# --- Finding 4: flags do not tell a contract the reader may not see --------------------------


def test_flags_do_not_tell_a_contract_the_reader_may_not_see(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Payroll Plus", unit="CANCER", data_classes=["personal"])
    with db.write(ME.actor) as session:
        vendor = records.create(session, ME, VENDOR, {"name": "Payroll Vendor"})
        contract = records.create(session, ME, CONTRACT, {
            "name": "Payroll subscription", "vendor_id": vendor.ref,
            "ends_on": (date.today() + timedelta(days=60)).isoformat(), "notice_days": 30,
            "data_agreement": "missing", "annual_value": 90_000})  # fmt: skip
        costs.set_applications(session, ME, contract, [{"application": ref}])
    manager = as_role("manager").get("/api/v1/applications", params={"q": "Payroll Plus"})
    raised = {flag["key"] for flag in manager.json()["data"][0]["flags"]}
    assert {"no_data_agreement", "contract_notice"} <= raised  # control
    member = as_role("member")
    listed = member.get("/api/v1/applications", params={"q": "Payroll Plus"}).json()["data"][0]
    assert not {flag["key"] for flag in listed["flags"]} & raised - {"no_accountable"}
    assert member.get(f"/api/v1/checkpoint/{ref}").json()["data"]["flags"] == []
    rows = member.get("/api/v1/portfolio").json()["data"]
    assert not set(next(r for r in rows if r["ref"] == ref)["flags"]) & {
        "no_data_agreement",
        "contract_notice",
    }


# --- Finding 5: a right password does not clear an address's count ---------------------------


def _targets(db: Database, count: int) -> list[str]:
    with db.write(ME.actor) as session:
        for n in range(count):
            accounts.create(session, ME, email=f"person{n}@bramblewood.example",
                            display_name=f"Person {n}", password=PASSWORD)  # fmt: skip
    return [f"person{n}@bramblewood.example" for n in range(count)]


def test_a_right_password_does_not_reset_the_address(
    instance: Instance, db: Database, people: People
) -> None:
    targets = _targets(db, 10)
    answers = []
    with TestClient(create_app(instance.config), base_url="http://localhost", client=FROM) as c:
        for index, email in enumerate(targets):
            if index % 5 == 4:  # the guesser's own account, now and then
                c.post("/api/v1/session", json={"email": email_of("member"),
                                                 "password": PASSWORD})  # fmt: skip
            answers += [c.post("/api/v1/session", json={
                "email": email, "password": f"spring guess {n:04d}"}).status_code
                for n in range(4)]  # fmt: skip
    assert 429 in answers, f"{len(answers)} guesses from one address, none refused"


def test_people_signing_in_from_one_address_are_not_stopped(
    instance: Instance, db: Database, people: People
) -> None:
    """The other side: an office behind one address, everyone signing in right."""
    targets = _targets(db, 40)
    with TestClient(create_app(instance.config), base_url="http://localhost", client=FROM) as c:
        answers = [c.post("/api/v1/session", json={"email": email, "password": PASSWORD})
                   .status_code for email in targets]  # fmt: skip
    assert set(answers) == {200}


# --- Finding 6: the current password is not guessed without end -----------------------------


def test_the_password_change_stops_a_guesser(as_role: Clients, people: People) -> None:
    held = as_role("member")
    answers = [held.post("/api/v1/session/password", json={
        "current_password": f"wrong guess {n:04d}",
        "new_password": "taken over for good 99"}).status_code for n in range(8)]  # fmt: skip
    assert answers[:5] == [422] * 5 and set(answers[5:]) == {429}, answers
    last = held.post("/api/v1/session/password", json={
        "current_password": PASSWORD, "new_password": "taken over for good 99"})  # fmt: skip
    assert last.status_code == 429


def test_a_right_change_is_not_held_up(as_role: Clients, people: People) -> None:
    held = as_role("member")
    held.post(
        "/api/v1/session/password",
        json={"current_password": "one wrong guess 1", "new_password": "a better phrase 2024"},
    )
    changed = held.post(
        "/api/v1/session/password",
        json={"current_password": PASSWORD, "new_password": "a better phrase 2024"},
    )
    assert changed.status_code == 200, changed.text


# --- Finding 7: an import names nothing the importer may not see ----------------------------


def test_an_import_does_not_name_what_the_importer_may_not_see(
    as_role: Clients, db: Database, people: People
) -> None:
    with db.write(ME.actor) as session:
        hidden = records.create(session, ME, APPLICATION, {
            "name": "Merger Data Room", "org_unit_id": people.units["CANCER"],
            "restricted": True})  # fmt: skip
        ref = hidden.ref
    steward = as_role("steward")
    guessed = steward.post(
        "/api/v1/imports/applications", params={"dry_run": "true"},
        content="name,unit\nMerger Data Room,CANCER\nNothing Like It,CANCER\n",
        headers={"Content-Type": "text/csv"},
    )  # fmt: skip
    assert guessed.status_code == 200, guessed.text
    said = " ".join(item["message"] for item in guessed.json()["data"]["problems"])
    assert ref not in said and "already on record" not in said, said


# --- Finding 8: errors do not log what was typed --------------------------------------------


def _fail(db: Database, table: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(text(
            f"CREATE TRIGGER review_fails BEFORE UPDATE ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'the disk is failing'); END"))  # fmt: skip


@pytest.mark.sqlite_only
def test_a_failed_edit_does_not_log_what_was_typed(
    as_role: Clients, db: Database, people: People, caplog: pytest.LogCaptureFixture
) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    version = steward.get(f"/api/v1/applications/{ref}").json()["data"]["version"]
    _fail(db, "application")
    caplog.set_level(logging.ERROR)
    # The test client re-raises what the server logged and answered 500.
    with contextlib.suppress(Exception):
        steward.patch(f"/api/v1/applications/{ref}", json={
            "version": version, "summary": "Holds the board's merger notes"})  # fmt: skip
    assert "the disk is failing" in caplog.text  # control: the error itself is logged
    assert "merger notes" not in caplog.text


# --- Finding 9: one person takes at most their share of proposals ----------------------------


def test_one_person_cannot_take_every_slot(as_role: Clients, db: Database, people: People) -> None:
    ref = add_app(db, people, name="Sample Store")
    member = as_role("member")
    script = as_role(None)
    made = 0
    for n in range(3):
        token = member.post("/api/v1/tokens", json={"name": f"Helper {n}"}).json()["data"]["token"]
        head = {"Authorization": f"Bearer {token}"}
        for m in range(5):
            answer = script.post(f"/api/v1/applications/{ref}/suggestions", headers=head,
                                 json={"field": "users", "value": n * 10 + m})  # fmt: skip
            made += answer.status_code == 201
    assert made == 10, f"one person has {made} proposals waiting on {ref}"
