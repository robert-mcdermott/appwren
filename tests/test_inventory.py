"""The inventory: applications and their parts, people in roles, capabilities, sensitive
fields, visibility, and the program that shapes them (slice 4 of wave 1)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from appwren.access.principal import Principal
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Capability, Event, RecordOwner
from appwren.inventory import access, applications, links, parts, records
from appwren.inventory.registry import APPLICATION, CAPABILITY, COMPONENT, TECHNOLOGY, VENDOR
from appwren.people import accounts
from appwren.program import catalog, packs
from tests.conftest import TESTER
from tests.people import ME, ROLES, People

Clients = Callable[[str | None], TestClient]


def who(db: Database, people: People, role: str) -> Principal:
    with db.read() as session:
        return accounts.principal_for(session, accounts.get(session, people.accounts[role]))


def add_app(
    db: Database, people: People, role: str = "steward", unit: str = "HALE", **values: Any
) -> str:
    principal = who(db, people, role)
    with db.write(principal.actor) as session:
        record = records.create(
            session,
            principal,
            APPLICATION,
            {"name": "Sample Tracker", "org_unit_id": people.units[unit], **values},
        )
        return record.ref


def shared(db: Database, record_type: Any, **values: Any) -> str:
    with db.write(ME.actor) as session:
        return records.create(session, ME, record_type, values).ref


def test_an_application_is_added_with_its_steward_as_accountable(
    db: Database, people: People
) -> None:
    ref = add_app(db, people, sourcing="built_here", data_classes=["internal", "health"])
    assert ref == "APP-0001"
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        assert (app.lifecycle, app.status, app.sensitivity) == ("active", "active", 3)
        assert app.lifecycle_since is not None
        owners = records.owners_of(session, APPLICATION, [app.id])[app.id]
        assert [(o["kind"], o["account_id"]) for o in owners] == [
            ("accountable", people.accounts["steward"])
        ]
        actions = {e.context.get("op") for e in session.scalars(select(Event))}
        assert "application.create" in actions


def test_who_may_add_an_application(db: Database, people: People) -> None:
    for role, allowed in [
        ("steward", True),
        ("architect", True),
        ("manager", True),
        ("member", False),
        ("leader", False),
        ("admin", False),
        ("auditor", False),
    ]:
        if allowed:
            add_app(db, people, role)
        else:
            with pytest.raises(PermissionDenied):
                add_app(db, people, role)
    with pytest.raises(PermissionDenied):  # a steward of Immunology, outside it
        add_app(db, people, "steward", unit="CANCER")


def test_values_are_checked_and_every_problem_reported(db: Database, people: People) -> None:
    principal = who(db, people, "steward")
    with db.write(principal.actor) as session, pytest.raises(Invalid) as caught:
        records.create(
            session,
            principal,
            APPLICATION,
            {
                "name": "",
                "org_unit_id": people.units["HALE"],
                "sourcing": "stolen",
                "users": -3,
                "grant_end": "soon",
                "home_url": "ftp://x",
                "tier": "9",
                "vendor_id": "VEN-0404",
            },
        )
    assert set(caught.value.errors) == {
        "name",
        "sourcing",
        "users",
        "grant_end",
        "home_url",
        "tier",
        "vendor_id",
    }


def test_lifecycle_moves_set_the_date_and_retire_the_record(db: Database, people: People) -> None:
    ref = add_app(db, people, lifecycle="evaluating", lifecycle_since="2026-01-01")
    principal = who(db, people, "steward")
    with db.write(principal.actor) as session:
        app = records.load(session, principal, APPLICATION, ref)
        assert app.lifecycle_since == date(2026, 1, 1)
        records.update(session, principal, APPLICATION, app, {"lifecycle": "retired"}, version=1)
        assert (app.status, app.version) == ("retired", 2)
        assert app.lifecycle_since != date(2026, 1, 1)
        with pytest.raises(Conflict):
            records.update(session, principal, APPLICATION, app, {"name": "x"}, version=1)


def test_exactly_one_accountable_owner(db: Database, people: People) -> None:
    ref = add_app(db, people)
    steward = who(db, people, "steward")
    member, auditor = people.accounts["member"], people.accounts["auditor"]
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        for wanted in (
            [],
            [{"account_id": member, "kind": "technical_owner"}],
            [
                {"account_id": member, "kind": "accountable"},
                {"account_id": auditor, "kind": "accountable"},
            ],
            [{"account_id": member, "kind": "emperor"}],
        ):
            with pytest.raises(Invalid):
                records.set_owners(session, steward, APPLICATION, app, wanted)
        records.set_owners(
            session,
            steward,
            APPLICATION,
            app,
            [
                {"account_id": member, "kind": "accountable"},
                {"account_id": auditor, "kind": "technical_owner"},
            ],
        )
    # The technical owner may edit it, but may not hand on who is accountable.
    technical = who(db, people, "auditor")
    with db.write(technical.actor) as session:
        app = records.load(session, technical, APPLICATION, ref)
        records.update(
            session, technical, APPLICATION, app, {"summary": "Tracks samples"}, version=app.version
        )
        with pytest.raises(PermissionDenied):
            records.set_owners(
                session,
                technical,
                APPLICATION,
                app,
                [
                    {"account_id": auditor, "kind": "accountable"},
                ],
            )
    # The database holds it too.
    with pytest.raises(IntegrityError), db.write(TESTER) as session:
        app = records.load(session, ME, APPLICATION, ref)
        session.add(
            RecordOwner(
                record_type="application", record_id=app.id, account_id=auditor, kind="accountable"
            )
        )
        session.flush()


def test_sensitive_fields_are_withheld_from_those_with_no_role(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people, annual_cost=60_000, sign_in="sso", users=300)
    seen = {}
    for role in ROLES:
        data = as_role(role).get(f"/api/v1/applications/{ref}").json()["data"]
        listed = as_role(role).get("/api/v1/applications").json()["data"][0]
        assert data["annual_cost"] == listed["annual_cost"], role  # one rule for both
        seen[role] = data["annual_cost"]
        assert data["users"] == 300  # not sensitive
    assert seen == {
        "admin": 60_000,
        "manager": 60_000,
        "architect": 60_000,
        "auditor": 60_000,
        "leader": 60_000,
        "steward": 60_000,
        "member": "withheld",
    }
    member = as_role("member")
    assert member.get("/api/v1/applications", params={"sort": "annual_cost"}).status_code == 403
    assert member.get("/api/v1/applications", params={"sign_in": "sso"}).status_code == 403
    assert (
        as_role("auditor").get("/api/v1/applications", params={"sort": "-annual_cost"}).status_code
        == 200
    )
    history = member.get(f"/api/v1/applications/{ref}/history").json()["data"]
    told = [line for item in history for line in item["lines"] if line["field"] == "annual_cost"]
    assert told == [] or all(line["after"] == "withheld" for line in told)
    # Named on it in any role, a member sees them.
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        records.set_owners(
            session,
            steward,
            APPLICATION,
            app,
            [
                {"account_id": people.accounts["steward"], "kind": "accountable"},
                {"account_id": people.accounts["member"], "kind": "support_contact"},
            ],
        )
    assert member.get(f"/api/v1/applications/{ref}").json()["data"]["annual_cost"] == 60_000


def test_a_restricted_application_is_known_only_to_those_with_a_part(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people, restricted=True)
    add_app(db, people)  # an ordinary one beside it
    for role in ROLES:
        client = as_role(role)
        listed = {row["ref"] for row in client.get("/api/v1/applications").json()["data"]}
        single = client.get(f"/api/v1/applications/{ref}").status_code
        expected = role != "member"
        assert (ref in listed) is expected and (single == 200) is expected, role
    with db.read() as session:
        member = who(db, people, "member")
        with pytest.raises(NotFound):
            records.load(session, member, APPLICATION, ref)


def test_capabilities_have_at_most_one_primary_provider(db: Database, people: People) -> None:
    with db.write(TESTER) as session:
        packs.install(session)
    with db.read() as session:
        surveys = session.scalars(select(Capability).where(Capability.key == "surveys")).one()
        assert session.get(Capability, surveys.parent_id).key == "research"  # type: ignore[union-attr]
        survey_ref = surveys.ref
    first, second = add_app(db, people), add_app(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        one = records.load(session, steward, APPLICATION, first)
        applications.set_capabilities(
            session, steward, one, [{"capability": survey_ref, "is_primary": True}]
        )
    with db.write(steward.actor) as session:
        two = records.load(session, steward, APPLICATION, second)
        with pytest.raises(Invalid) as caught:
            applications.set_capabilities(
                session, steward, two, [{"capability": survey_ref, "is_primary": True}]
            )
        assert first in caught.value.errors["capabilities"]
        applications.set_capabilities(session, steward, two, [{"capability": survey_ref}])
    with db.read() as session:
        capability = records.load(session, ME, CAPABILITY, survey_ref)
        served = parts.providers(session, ME, [capability.id])[capability.id]
        assert [(a["ref"], a["is_primary"]) for a in served] == [(first, True), (second, False)]


def test_components_technologies_and_their_support(db: Database, people: People) -> None:
    ref = add_app(db, people, sourcing="built_here")
    tech = shared(db, TECHNOLOGY, name="Python", kind="language", radar="adopt")
    today = date.today()
    with db.write(ME.actor) as session:
        python = records.load(session, ME, TECHNOLOGY, tech)
        parts.set_releases(
            session,
            ME,
            python,
            [
                {"cycle": "3.9", "support_ends": (today - timedelta(days=30)).isoformat()},
                {"cycle": "3.12", "support_ends": (today + timedelta(days=200)).isoformat()},
                {"cycle": "3.13", "support_ends": (today + timedelta(days=900)).isoformat()},
            ],
        )
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        component = records.create(
            session, steward, COMPONENT, {"name": "API", "kind": "service", "application_id": ref}
        )
        app = records.load(session, steward, APPLICATION, ref)
        assert component.org_unit_id == app.org_unit_id
        parts.set_technologies(
            session,
            steward,
            component,
            [{"technology": tech, "release": "3.9", "version": "3.9.18"}],
        )
        with pytest.raises(Invalid):
            parts.set_technologies(
                session, steward, component, [{"technology": tech, "release": "2.7"}]
            )
        used = parts.technologies_of(session, [component.id])[component.id]
        assert [(t["release"], t["support"]) for t in used] == [("3.9", "ended")]
    with db.read() as session:
        python = records.load(session, ME, TECHNOLOGY, tech)
        shown = records.detail(session, ME, TECHNOLOGY, python)
        assert {r["cycle"]: r["support"] for r in shown["releases"]} == {
            "3.9": "ended",
            "3.12": "ending",
            "3.13": "supported",
        }
        assert shown["use_count"] == 1
    with db.write(ME.actor) as session, pytest.raises(Invalid):
        python = records.load(session, ME, TECHNOLOGY, tech)
        parts.set_releases(session, ME, python, [{"cycle": "3.13"}])  # 3.9 is in use
    member = who(db, people, "member")
    with db.write(member.actor) as session, pytest.raises(PermissionDenied):
        records.create(
            session, member, COMPONENT, {"name": "Job", "kind": "batch_job", "application_id": ref}
        )


def test_shared_records_are_kept_by_architects_and_managers(db: Database, people: People) -> None:
    for role, allowed in [
        ("architect", True),
        ("manager", True),
        ("steward", False),
        ("member", False),
        ("admin", False),
    ]:
        principal = who(db, people, role)
        with db.write(principal.actor) as session:
            if allowed:
                records.create(session, principal, VENDOR, {"name": f"Vendor {role}"})
            else:
                with pytest.raises(PermissionDenied):
                    records.create(session, principal, VENDOR, {"name": f"Vendor {role}"})


def test_what_a_stage_still_requires(db: Database, people: People) -> None:
    ref = add_app(db, people, lifecycle="proposed")
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        found = applications.missing(session, app)
        assert found["now"] == ["summary", "sourcing", "capabilities"]
        assert found["next_stage"] == "evaluating"
        assert found["next"] == ["purpose", "data_classes"]  # someone is accountable already


def test_the_organizations_own_fields(db: Database, people: People) -> None:
    ref = add_app(
        db,
        people,
        sourcing="research_software",
        fields={"ethics_protocols": "EP-1234", "accessibility": "partial"},
    )
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        assert app.fields == {"ethics_protocols": "EP-1234", "accessibility": "partial"}
        for bad in (
            {"nonsense": "x"},
            {"accessibility": "perfect"},
            {"data_management_plan": "a drawer"},
        ):
            with pytest.raises(Invalid):
                records.update(
                    session, steward, APPLICATION, app, {"fields": bad}, version=app.version
                )
        records.update(
            session,
            steward,
            APPLICATION,
            app,
            {"fields": {"ethics_protocols": ""}},
            version=app.version,
        )
        assert app.fields == {"accessibility": "partial"}
        records.update(
            session, steward, APPLICATION, app, {"sourcing": "low_code"}, version=app.version
        )
        with pytest.raises(Invalid):  # ethics protocols do not apply to low-code
            records.update(
                session,
                steward,
                APPLICATION,
                app,
                {"fields": {"ethics_protocols": "EP-9"}},
                version=app.version,
            )
    with db.read() as session:
        app = records.load(session, ME, APPLICATION, ref)
        names = [f["key"] for f in records.detail(session, ME, APPLICATION, app)["own_fields"]]
        assert "ethics_protocols" not in names and "accessibility" in names


def test_applications_depend_on_each_other(db: Database, people: People) -> None:
    first, second = add_app(db, people), add_app(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        one = records.load(session, steward, APPLICATION, first)
        two = records.load(session, steward, APPLICATION, second)
        links.add(session, steward, APPLICATION, one, "depends_on", APPLICATION, two)
        with pytest.raises(Invalid):
            links.add(session, steward, APPLICATION, one, "depends_on", APPLICATION, one)
    with db.read() as session:
        two = records.load(session, ME, APPLICATION, second)
        shown = links.of(session, ME, APPLICATION, two)
        assert [(i["label"], i["record"]["ref"]) for i in shown["incoming"]] == [
            ("Is depended on by", first)
        ]


def test_the_program_moves_as_a_pack(db: Database, tmp_path: Any) -> None:
    with db.write(TESTER) as session:
        assert packs.install(session)["capabilities"] > 30
        assert packs.install(session)["capabilities"] == 0  # safe to run again
        exported = json.loads(json.dumps(packs.export(session), default=str))
    with db.write(ME.actor) as session:
        nothing = packs.load(session, ME, exported, dry_run=True)
        assert nothing == {"vocabularies": [], "settings": [], "capabilities": 0}
        bad = {
            **exported,
            "fields": [{"key": "users", "label": "", "type": "colour"}],
            "stage_requirements": {"active": ["magic"]},
        }
        with pytest.raises(Invalid) as caught:
            packs.load(session, ME, bad, dry_run=True)
        message = caught.value.errors["pack"]
        for words in ("users has the name", "needs a label", "must be one of", "magic"):
            assert words in message
        exported["vocabularies"]["sourcing"] = [
            item for item in exported["vocabularies"]["sourcing"] if item["key"] != "low_code"
        ]
        exported["sensitive_fields"] = ["annual_cost"]
        changed = packs.load(session, ME, exported, dry_run=False)
        assert changed["vocabularies"] == ["sourcing"]
        assert changed["settings"] == ["sensitive_fields"]
        assert catalog.sensitive_fields(session) == ["annual_cost"]
        from appwren.program import vocab

        assert "low_code" not in vocab.keys(session, "sourcing")  # retired, not removed
        assert "low_code" in vocab.keys(session, "sourcing", active_only=False)


def test_visibility_of_lists_and_records_agree_for_every_role(db: Database, people: People) -> None:
    open_ref, closed_ref = add_app(db, people), add_app(db, people, restricted=True)
    for role in ROLES:
        principal = who(db, people, role)
        with db.read() as session:
            rows, _ = records.search(session, principal, APPLICATION, {})
            listed = {row.ref for row in rows}
            for ref in (open_ref, closed_ref):
                app = records.load(session, ME, APPLICATION, ref)
                assert (ref in listed) == access.can_see(session, principal, APPLICATION, app)
