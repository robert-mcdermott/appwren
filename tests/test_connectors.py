"""Connectors and the values they supply: the framework (slice 1 of wave 4) and the
end-of-life source (slice 3). Every source here is a fake one inside the test."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import connectors
from appwren.connectors import Kind, Reading, Setting, sourced
from appwren.connectors.kinds import endoflife
from appwren.core.errors import Conflict, Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Connector, ConnectorRun, FactValue, TechnologyRelease
from appwren.inventory import history, records
from appwren.inventory.registry import TECHNOLOGY
from tests.people import ME, People
from tests.test_inventory import shared, who
from tests.test_lifecycle import with_releases

Clients = Callable[[str | None], TestClient]

PYTHON = [
    {"cycle": "3.13", "releaseDate": "2024-10-07", "eol": "2029-10-31", "latest": "3.13.1"},
    {"cycle": "3.9", "releaseDate": "2020-10-05", "eol": "2025-10-31", "extendedSupport": False},
    {"cycle": "2.7", "eol": True},
]


class Source:
    """A fake source: it answers from a map of paths, and remembers what it was asked."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.asked: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked.append(request)
        answer = self.answers.get(request.url.path)
        if answer is None:
            return httpx.Response(404)
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=answer)

    @property
    def paths(self) -> list[str]:
        return [request.url.path for request in self.asked]


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch) -> Source:
    fake = Source({"/api/python.json": PYTHON, "/api/all.json": ["python", "nodejs"]})
    monkeypatch.setattr(connectors, "TRANSPORT", httpx.MockTransport(fake))
    return fake


def set_up(db: Database, people: People, *, on: bool = True, **values: Any) -> str:
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        row = connectors.add(
            session, admin, {"key": "eol", "kind": "endoflife", "name": "End-of-life data",
                             **values},
        )  # fmt: skip
        if on:
            connectors.change(session, admin, row, {"enabled": True})
        return row.key


def releases(db: Database, ref: str) -> dict[str, TechnologyRelease]:
    with db.read() as session:
        record = records.load(session, ME, TECHNOLOGY, ref)
        return {
            row.cycle: row
            for row in session.scalars(
                select(TechnologyRelease).where(TechnologyRelease.technology_id == record.id)
            )
        }


def python(db: Database) -> str:
    ref = shared(db, TECHNOLOGY, name="Python", kind="language", eol_key="python")
    with_releases(db, ref, [{"cycle": "3.9", "support_ends": "2025-12-31"}])
    return ref


# --- Nothing unless switched on --------------------------------------------------------------


def test_nothing_is_reached_until_a_connector_is_switched_on(
    db: Database, people: People, source: Source
) -> None:
    python(db)
    assert connectors.run_due(db) == {"connectors_run": 0, "connectors_failed": 0}
    set_up(db, people, on=False)
    assert connectors.run_due(db)["connectors_run"] == 0
    assert source.paths == []  # a connector set up but off makes no connection
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        connectors.change(session, admin, connectors.load(session, "eol"), {"enabled": True})
    assert connectors.run_due(db) == {"connectors_run": 1, "connectors_failed": 0}
    assert source.paths == ["/api/python.json"]  # only the key of a technology is sent
    assert connectors.run_due(db)["connectors_run"] == 0  # not due again for a day


def test_setting_up_a_connector(db: Database, people: People) -> None:
    with db.write(ME.actor) as session, pytest.raises(PermissionDenied):
        connectors.add(session, who(db, people, "architect"), {"key": "eol", "kind": "endoflife",
                                                              "name": "EOL"})  # fmt: skip
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        with pytest.raises(Invalid) as bad:
            connectors.add(session, admin, {"key": "EOL!", "kind": "endoflife", "name": "x"})
        assert "key" in bad.value.errors
        with pytest.raises(Invalid) as bad:
            connectors.add(session, admin, {"key": "x1", "kind": "nothing", "name": "x"})
        assert "kind" in bad.value.errors
        with pytest.raises(Invalid) as bad:
            connectors.add(session, admin, {"key": "x2", "kind": "endoflife", "name": "x",
                                            "settings": {"base_url": "http://plain"}})  # fmt: skip
        assert "settings.base_url" in bad.value.errors
        row = connectors.add(session, admin, {"key": "eol", "kind": "endoflife", "name": "EOL"})
        assert row.enabled is False and row.settings == {"base_url": "https://endoflife.date"}
        with pytest.raises(Conflict):
            connectors.add(session, admin, {"key": "eol", "kind": "endoflife", "name": "Again"})


# --- A run, and its values ---------------------------------------------------------------------


def test_end_of_life_dates_arrive_with_their_source(
    as_role: Clients, db: Database, people: People, source: Source
) -> None:
    ref = python(db)
    shared(db, TECHNOLOGY, name="Gone", kind="language", eol_key="gone")
    set_up(db, people)
    done = connectors.run(db, "eol")
    assert done["status"] == "ok", done
    # 3.9 has two values (its extended support is not a date), 3.13 three, 2.7 none.
    assert done["counts"] == {"asked": 2, "read": 5, "changed": 5, "unchanged": 0, "kept": 0,
                              "unmatched": 1}  # fmt: skip
    assert done["unmatched"] == [
        {"what": "Gone (gone)", "why": "the dataset has no product by that key"}
    ]
    found = releases(db, ref)
    assert set(found) == {"3.13", "3.9", "2.7"}  # added, and nothing removed
    assert str(found["3.9"].support_ends) == "2025-10-31"
    assert found["3.13"].latest == "3.13.1" and found["2.7"].support_ends is None
    with db.read() as session:
        record = records.load(session, ME, TECHNOLOGY, ref)
        told = history.for_record(session, TECHNOLOGY, record)
        assert told[0]["actor"] == "Connector: End-of-life data"
        run = session.scalars(select(ConnectorRun)).one()
        assert run.status == "ok" and run.counts["changed"] == 5
        row = session.scalars(select(Connector)).one()
        assert row.last_status == "ok" and row.next_run_at > row.last_run_at
    shown = as_role("member").get(f"/api/v1/sourced/{ref}").json()["data"]
    by_cycle = {
        item["cycle"]: {v["field"]: v for v in item["values"]} for item in shown["releases"]
    }
    ends = by_cycle["3.9"]["support_ends"]
    assert ends["shown"] == "2025-10-31" and ends["source_name"] == "End-of-life data"
    assert ends["read_at"] and ends["overridden"] is False
    # The second run reads the same and changes nothing.
    again = connectors.run(db, "eol")
    assert again["counts"]["changed"] == 0 and again["counts"]["unchanged"] == 5
    assert len(releases(db, ref)) == 3


def test_an_override_wins_until_it_is_removed(
    as_role: Clients, db: Database, people: People, source: Source
) -> None:
    ref = python(db)
    set_up(db, people)
    connectors.run(db, "eol")
    url = f"/api/v1/sourced/{ref}/support_ends/override"
    architect = as_role("architect")
    body = {"value": "2026-03-31", "release": "3.9"}
    no_reason = architect.post(url, json=body)
    assert no_reason.status_code == 422
    assert as_role("member").post(url, json={**body, "reason": "Mine"}).status_code == 403
    assert architect.post(url, json={**body, "release": "1.0", "reason": "x"}).status_code == 404
    said = architect.post(url, json={**body, "reason": "We pay for extended support"})
    assert said.status_code == 200, said.text
    assert said.json()["data"]["override_by"] == "Architect Person"
    assert str(releases(db, ref)["3.9"].support_ends) == "2026-03-31"
    again = connectors.run(db, "eol")
    assert again["counts"]["kept"] == 1
    assert str(releases(db, ref)["3.9"].support_ends) == "2026-03-31"  # the person's holds
    removed = architect.delete(url, params={"release": "3.9"})
    assert removed.status_code == 200 and removed.json()["data"]["overridden"] is False
    assert str(releases(db, ref)["3.9"].support_ends) == "2025-10-31"  # the source's again


def test_a_change_by_hand_is_an_override(db: Database, people: People, source: Source) -> None:
    ref = python(db)
    set_up(db, people)
    connectors.run(db, "eol")
    with_releases(db, ref, [
        {"cycle": "3.13", "released_on": "2024-10-07", "support_ends": "2029-10-31",
         "latest": "3.13.1"},
        {"cycle": "3.9", "released_on": "2020-10-05", "support_ends": "2027-01-01"},
        {"cycle": "2.7"},
    ])  # fmt: skip
    again = connectors.run(db, "eol")
    assert again["counts"]["kept"] == 1 and again["counts"]["changed"] == 0
    assert str(releases(db, ref)["3.9"].support_ends) == "2027-01-01"
    with db.read() as session:
        row = session.scalars(
            select(FactValue).where(
                FactValue.record_id == releases(db, ref)["3.9"].id,
                FactValue.field == "support_ends",
            )
        ).one()
        assert row.overridden and row.override_reason == "Changed by hand on the record"
        assert row.value == "2025-10-31"  # the source's reading waits beside it
    # A release removed by hand takes what sources supplied for it with it.
    with_releases(db, ref, [{"cycle": "3.9", "support_ends": "2027-01-01"}])
    with db.read() as session:
        ids = {row.record_id for row in session.scalars(select(FactValue))}
        assert ids == {releases(db, ref)["3.9"].id}


# --- Failing safely ----------------------------------------------------------------------------


def test_a_failed_run_changes_nothing(db: Database, people: People, source: Source) -> None:
    ref = python(db)
    shared(db, TECHNOLOGY, name="Node.js", kind="language", eol_key="nodejs")
    source.answers["/api/nodejs.json"] = httpx.Response(500)
    set_up(db, people)
    done = connectors.run(db, "eol")
    assert done["status"] == "failed" and "500" in done["error"]
    found = releases(db, ref)
    assert set(found) == {"3.9"} and str(found["3.9"].support_ends) == "2025-12-31"
    with db.read() as session:
        assert session.scalars(select(FactValue)).all() == []
        run = session.scalars(select(ConnectorRun)).one()
        assert run.status == "failed" and run.counts == {} and "500" in run.error
        view = connectors.view(session, connectors.load(session, "eol"))
        assert view["last_status"] == "failed" and view["runs"][0]["error"] == run.error


@pytest.mark.parametrize(
    ("limit", "said"),
    [("MOST_BYTES", "larger than the limit"), ("DEADLINE", "time limit")],
)
def test_a_run_has_limits(
    db: Database, people: People, source: Source, monkeypatch: pytest.MonkeyPatch,
    limit: str, said: str,
) -> None:  # fmt: skip
    ref = python(db)
    monkeypatch.setattr(connectors, limit, 100 if limit == "MOST_BYTES" else timedelta(0))
    set_up(db, people)
    done = connectors.run(db, "eol")
    assert done["status"] == "failed" and said in done["error"]
    assert set(releases(db, ref)) == {"3.9"}


def _whoami(reading: Reading) -> None:
    with reading.client(
        "https://source.test", {"Authorization": f"token {reading.credential}"}
    ) as c:
        reading.extra["me"] = reading.get(c, "/whoami")


TOKENED = Kind(
    key="tokened", label="A source with a credential", describes="For the tests",
    access="Read", settings=(Setting("org", "Organization"),), credential="TEST_SOURCE_TOKEN",
    read=_whoami, check=lambda reading: "fine",
)  # fmt: skip


def test_a_credential_comes_only_from_the_environment(
    db: Database, people: People, source: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(connectors.KINDS, "tokened", TOKENED)
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        with pytest.raises(Invalid) as bad:
            connectors.add(session, admin, {"key": "t1", "kind": "tokened", "name": "T",
                                            "settings": {"org": "lab"},
                                            "credential_env": "ghp_secret"})  # fmt: skip
        assert "credential_env" in bad.value.errors  # a credential is not a variable's name
        row = connectors.add(session, admin, {"key": "tok", "kind": "tokened", "name": "T",
                                              "settings": {"org": "lab"}})  # fmt: skip
        assert row.credential_env == "TEST_SOURCE_TOKEN"
        connectors.change(session, admin, row, {"enabled": True})
    done = connectors.run(db, "tok")
    assert done["status"] == "failed"
    assert done["error"] == "the environment variable TEST_SOURCE_TOKEN is not set"
    assert source.asked == []
    monkeypatch.setenv("TEST_SOURCE_TOKEN", "s3cret-value")
    source.answers["/whoami"] = httpx.Response(401)
    done = connectors.run(db, "tok")
    assert "refused the credential (401)" in done["error"]
    assert source.asked[-1].headers["Authorization"] == "token s3cret-value"
    source.answers["/whoami"] = {"login": "reader"}
    assert connectors.run(db, "tok")["status"] == "ok"
    with db.read() as session:  # the credential was used and never kept
        view = connectors.view(session, connectors.load(session, "tok"))
        assert view["credential_set"] is True and "s3cret" not in str(view)
        for table in (Connector, ConnectorRun):
            assert "s3cret" not in str([vars(row) for row in session.scalars(select(table))])


# --- On the pages ------------------------------------------------------------------------------


def test_connectors_on_admin(
    as_role: Clients, db: Database, people: People, source: Source
) -> None:
    python(db)
    admin = as_role("admin")
    found = admin.get("/api/v1/connectors").json()["data"]
    assert "endoflife" in {kind["key"] for kind in found["kinds"]} and found["connectors"] == []
    added = admin.post(
        "/api/v1/connectors", json={"key": "eol", "kind": "endoflife", "name": "End-of-life data"}
    )
    assert added.status_code == 201 and added.json()["data"]["enabled"] is False
    checked = admin.post("/api/v1/connectors/eol/check").json()["data"]
    assert checked["said"] == "The dataset answers, with 2 products. 1 technologies have a key."
    on = admin.patch("/api/v1/connectors/eol", json={"enabled": True}).json()["data"]
    assert on["enabled"] is True and on["next_run_at"]
    ran = admin.post("/api/v1/connectors/eol/run").json()["data"]
    assert ran["status"] == "ok" and ran["counts"]["changed"] == 5
    page = admin.get("/api/v1/connectors/eol").json()["data"]
    assert page["last_status"] == "ok" and page["runs"][0]["counts"]["changed"] == 5
    assert admin.get("/api/v1/connectors/nothing").status_code == 404


def test_the_scheduler_runs_connectors(instance: Any, people: People, source: Source) -> None:
    from appwren import jobs

    python(instance.db)
    set_up(instance.db, people)
    result = jobs.run_job(instance.db, instance.config, "connectors", force=True)
    assert result is not None
    assert result["status"] == "ok" and result["counts"]["connectors_run"] == 1
    assert sourced.FIELDS[("technology_release", "support_ends")] is endoflife.ENDS


# --- Source code hosting (slice 2) --------------------------------------------------------------

COMMITS = [
    {"author": {"login": "Ana"}, "commit": {"author": {"email": "ana@lab.test"}}},
    {"author": {"login": "ana"}, "commit": {"author": {"email": "ana@lab.test"}}},
    {"author": None, "commit": {"author": {"email": "bo@lab.test"}}},
    {"author": {"login": "dependabot[bot]"}, "commit": {"author": {"email": "bot@x.test"}}},
]
GITHUB = {
    "/orgs/lab": {"login": "lab"},
    "/repos/lab/tracker": {"pushed_at": "2026-11-20T10:00:00Z"},
    "/repos/lab/tracker/languages": {"JavaScript": 1200, "Python": 5000},
    "/repos/lab/tracker/commits": COMMITS,
    "/repos/lab/tracker/dependabot/alerts": [
        {"security_advisory": {"severity": "critical"}},
        {"security_advisory": {"severity": "high"}},
        {"security_advisory": {"severity": "high"}},
    ],
    "/repos/lab/tracker/contents": [{"name": "README.md"}, {"name": "tests"},
                                    {"name": ".github"}, {"name": "catalog-info.yaml"}],
    "/repos/lab/tracker/contents/.github": [{"name": "workflows"}, {"name": "dependabot.yml"}],
    "/repos/lab/tracker-ui": {"pushed_at": "2026-10-01T08:00:00Z"},
    "/repos/lab/tracker-ui/languages": {"TypeScript": 900},
    "/repos/lab/tracker-ui/commits": [{"author": {"login": "cy"}, "commit": {}}],
    "/repos/lab/tracker-ui/dependabot/alerts": httpx.Response(403),
    "/repos/lab/tracker-ui/contents": [{"name": "src"}],
    "/repos/lab/other": {"pushed_at": "2025-01-01T00:00:00Z"},
    "/repos/lab/other/languages": {"R": 10},
    "/repos/lab/other/commits": [],
    "/repos/lab/other/contents": [{"name": "readme"}],
}  # fmt: skip


def component(db: Database, people: People, app: str, name: str, repo: str | None) -> str:
    from appwren.inventory.registry import COMPONENT

    steward = who(db, people, "steward")
    with db.write(steward.actor) as session:
        return records.create(session, steward, COMPONENT, {
            "name": name, "application_id": app, "kind": "service", "repo_url": repo,
        }).ref  # fmt: skip


def facts(db: Database, record_type: str, ref: str) -> dict[str, Any]:
    from appwren.inventory.registry import TYPES

    with db.read() as session:
        record = records.load(session, ME, TYPES[record_type], ref)
        return {
            row.field: row.value
            for row in session.scalars(
                select(FactValue).where(
                    FactValue.record_type == record_type, FactValue.record_id == record.id
                )
            )
        }


def test_what_the_repositories_know(
    as_role: Clients, db: Database, people: People, source: Source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from tests.test_inventory import add_app

    source.answers.update(GITHUB)
    tracker = add_app(db, people, name="Tracker", maintainers=1)
    api = component(db, people, tracker, "Tracker API", "https://github.com/Lab/tracker.git")
    ui = component(db, people, tracker, "Tracker UI", "https://github.com/lab/tracker-ui")
    other = add_app(db, people, name="Other", maintainers=4)
    component(db, people, other, "Other app", "https://github.com/lab/other")
    component(db, people, other, "Other secret", "https://github.com/lab/secret")
    component(db, people, other, "Elsewhere", "https://gitlab.example.org/lab/x")
    component(db, people, other, "Another org", "https://github.com/someone-else/x")
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        row = connectors.add(session, admin, {"key": "github", "kind": "codehost", "name": "GitHub",
                                              "settings": {"organization": "lab"}})  # fmt: skip
        assert row.credential_env == "APPWREN_GITHUB_TOKEN"
        connectors.change(session, admin, row, {"enabled": True})
    monkeypatch.setenv("APPWREN_GITHUB_TOKEN", "read-only")
    assert as_role("admin").post("/api/v1/connectors/github/check").json()["data"]["said"] == (
        "lab answers. 4 components have a repository there."
    )
    done = connectors.run(db, "github")
    assert done["status"] == "ok", done
    # Nine facts of the API, eight of each other repository whose alerts are not known, and
    # Tracker's maintainers: all of them new.
    assert done["counts"]["changed"] == done["counts"]["read"] == 9 + 8 + 8 + 1
    assert done["unmatched"] == [{"what": "Other secret (lab/secret)",
                                  "why": "the token cannot read this repository, or it does not "
                                         "exist"}]  # fmt: skip
    asked = set(source.paths)
    assert "/repos/someone-else/x" not in asked and not any("gitlab" in p for p in asked)
    assert all(r.headers["Authorization"] == "Bearer read-only" for r in source.asked)
    assert facts(db, "component", api) == {
        "languages": ["Python", "JavaScript"], "last_change": "2026-11-20", "contributors": 2,
        "dependency_alerts": {"critical": 1, "high": 2, "medium": 0, "low": 0},
        "has_readme": True, "has_tests": True, "has_ci": True, "has_dependency_updates": True,
        "has_catalog_file": True,
    }  # fmt: skip
    ui_facts = facts(db, "component", ui)
    assert "dependency_alerts" not in ui_facts  # the host would not say: not known, not none
    assert ui_facts["has_readme"] is False and ui_facts["contributors"] == 1
    # Tracker's repositories were all read: its maintainers are the three people who changed
    # them. Other's were not, so its own count stands.
    with db.read() as session:
        from appwren.inventory.registry import APPLICATION

        assert records.load(session, ME, APPLICATION, tracker).maintainers == 3
        assert records.load(session, ME, APPLICATION, other).maintainers == 4
    shown = as_role("member").get(f"/api/v1/sourced/{api}").json()["data"]["values"]
    assert {item["field"]: item["source_name"] for item in shown}["languages"] == "GitHub"
    # A second run changes nothing.
    again = connectors.run(db, "github")
    assert (
        again["counts"]["changed"] == 0 and again["counts"]["unchanged"] == again["counts"]["read"]
    )


def test_a_component_value_has_no_field_of_its_own_to_override_by_hand(
    as_role: Clients, db: Database, people: People, source: Source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from tests.test_inventory import add_app

    source.answers.update(GITHUB)
    tracker = add_app(db, people, name="Tracker")
    api = component(db, people, tracker, "Tracker API", "https://github.com/lab/tracker")
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        row = connectors.add(session, admin, {"key": "github", "kind": "codehost", "name": "GitHub",
                                              "settings": {"organization": "lab"}})  # fmt: skip
        connectors.change(session, admin, row, {"enabled": True})
    monkeypatch.setenv("APPWREN_GITHUB_TOKEN", "read-only")
    connectors.run(db, "github")
    url = f"/api/v1/sourced/{api}/has_tests/override"
    steward = as_role("steward")
    said = steward.post(url, json={"value": False, "reason": "Those are fixtures, not tests"})
    assert said.status_code == 200, said.text
    assert connectors.run(db, "github")["counts"]["kept"] == 1
    shown = {v["field"]: v for v in steward.get(f"/api/v1/sourced/{api}").json()["data"]["values"]}
    assert shown["has_tests"]["shown"] is False and shown["has_tests"]["value"] is True
    assert as_role("member").post(url, json={"value": True, "reason": "x"}).status_code == 403
