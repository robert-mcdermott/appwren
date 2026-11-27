"""Who uses an application: everyone, units, and kinds of people across the organization."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.db.engine import Database
from appwren.db.models import Event
from appwren.inventory import applications, records
from appwren.inventory.registry import APPLICATION
from appwren.program import packs, vocab
from tests.people import ME, People
from tests.test_inventory import add_app, who

Clients = Callable[[str | None], TestClient]


def use_of(client: TestClient, ref: str) -> dict:
    data = client.get(f"/api/v1/applications/{ref}").json()["data"]
    return {key: data.get(key) for key in ("org_wide", "audiences", "users", "external_users",
                                           "used_by", "version")}  # fmt: skip


def put_use(client: TestClient, ref: str, **body: object):  # type: ignore[no-untyped-def]
    version = client.get(f"/api/v1/applications/{ref}").json()["data"]["version"]
    return client.put(f"/api/v1/applications/{ref}/use", json={"version": version, **body})


def test_units_and_kinds_of_people_together(db: Database, people: People, as_role: Clients) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    answer = put_use(steward, ref, units=[people.units["IMM"]], audiences=["managers", "hourly"],
                     users=120, external_users=False)  # fmt: skip
    assert answer.status_code == 200, answer.text
    use = use_of(steward, ref)
    assert use["org_wide"] is False
    assert use["audiences"] == ["managers", "hourly"]
    assert use["used_by"] == [people.units["IMM"]]
    assert use["users"] == 120


def test_everyone_clears_the_units_and_kinds(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    put_use(steward, ref, units=[people.units["HALE"]], audiences=["researchers"])
    assert put_use(steward, ref, org_wide=True, units=[people.units["HALE"]],
                   audiences=["researchers"], users=900).status_code == 200  # fmt: skip
    use = use_of(steward, ref)
    assert use["org_wide"] is True
    assert not use["audiences"] and use["used_by"] == []
    assert use["users"] == 900


def test_only_kinds_on_the_list_are_taken(db: Database, people: People, as_role: Clients) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    refused = put_use(steward, ref, audiences=["managers", "astronauts"])
    assert refused.status_code == 422
    assert "audiences" in {item["location"][-1] for item in refused.json()["errors"]}
    # Nothing was half saved: neither the kinds nor anything else.
    assert not use_of(steward, ref)["audiences"]


def test_a_retired_kind_is_not_taken_for_new_use(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people)
    with db.write(ME.actor) as session:
        listed = vocab.get(session, "audiences")
        vocab.put(session, "audiences", [{**item, "retired": item["key"] == "hourly"}
                                         for item in listed])  # fmt: skip
    assert put_use(as_role("steward"), ref, audiences=["hourly"]).status_code == 422


def test_only_those_who_keep_it_say_who_uses_it(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people)
    assert put_use(as_role("member"), ref, org_wide=True).status_code == 403
    assert put_use(as_role("auditor"), ref, org_wide=True).status_code == 403
    assert put_use(as_role("manager"), ref, org_wide=True).status_code == 200


def test_a_change_made_against_an_old_version_is_refused(
    db: Database, people: People, as_role: Clients
) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    old = use_of(steward, ref)["version"]
    assert put_use(steward, ref, audiences=["managers"]).status_code == 200
    stale = steward.put(f"/api/v1/applications/{ref}/use",
                        json={"version": old, "org_wide": True})  # fmt: skip
    assert stale.status_code == 409
    assert use_of(steward, ref)["audiences"] == ["managers"]


def test_the_history_says_what_changed(db: Database, people: People, as_role: Clients) -> None:
    ref = add_app(db, people)
    steward = as_role("steward")
    put_use(steward, ref, units=[people.units["HALE"]], audiences=["researchers"])
    history = steward.get(f"/api/v1/applications/{ref}/history").json()["data"]
    said = " ".join(str(entry) for entry in history)
    assert "Kinds of people who use it" in said
    assert "Hale Lab" in said
    with db.read() as session:
        ops = {event.context.get("op") for event in session.scalars(select(Event))}
    assert {"application.edit", "application.units"} <= ops


def test_the_service_is_the_same_change(db: Database, people: People) -> None:
    ref = add_app(db, people)
    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        app = records.load(session, steward, APPLICATION, ref)
        applications.set_use(session, steward, app, {"org_wide": True}, version=app.version)
    with db.read() as session:
        app = records.load(session, steward, APPLICATION, ref)
        assert app.org_wide is True
        assert applications.units_of(session, [app.id]) == {}


def test_every_starter_keeps_kinds_of_people_that_fit_it() -> None:
    shipped = [item["key"] for item in vocab.DEFAULTS["audiences"]]
    assert {"leadership", "managers", "hourly", "contractors"} <= set(shipped)
    for key in (entry["key"] for entry in packs.starters()):
        listed = packs.starter(key).get("vocabularies", {}).get("audiences")
        kept = [item["key"] for item in listed] if listed else shipped
        # Everyone has leaders and managers, and people paid by the hour or on contract.
        assert {"leadership", "managers", "hourly", "contractors"} <= set(kept), key


def test_the_list_filters_by_who_uses_it(db: Database, people: People, as_role: Clients) -> None:
    steward = as_role("steward")
    everyone, division, hourly, lab = (
        add_app(db, people, name=name)
        for name in ("Email", "Division tool", "Timesheets", "Lab tool")
    )
    put_use(steward, everyone, org_wide=True)
    put_use(steward, division, units=[people.units["IMM"]])
    put_use(steward, hourly, audiences=["hourly", "contractors"])
    put_use(steward, lab, units=[people.units["HALE"]])

    def names(**params: object) -> set[str]:
        found = as_role("manager").get("/api/v1/applications", params=params)
        assert found.status_code == 200, found.text
        return {row["name"] for row in found.json()["data"]}

    assert names(audience="everyone") == {"Email"}
    assert names(audience="hourly") == {"Timesheets"}
    # Everyone in the Hale Lab uses what the whole organization uses, the lab's own, and what
    # everyone in Immunology, which the lab is part of, uses. Not what kinds of people use.
    assert names(used_in=people.units["HALE"]) == {"Email", "Division tool", "Lab tool"}
    assert names(used_in=people.units["CANCER"]) == {"Email"}
    assert (
        as_role("manager").get("/api/v1/applications", params={"audience": "x')"}).status_code
        == 422
    )
