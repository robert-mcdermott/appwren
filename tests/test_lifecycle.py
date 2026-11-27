"""The technology lifecycle: the timeline, the radar, and support dates from a file
(slice 6 of wave 2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from appwren.cli import main
from appwren.core import clock
from appwren.core.errors import PermissionDenied
from appwren.db.engine import Database
from appwren.inventory import history, parts, records
from appwren.inventory.registry import COMPONENT, TECHNOLOGY
from appwren.landscape import lifecycle
from tests.conftest import Instance
from tests.people import ME, ROLES, People
from tests.test_inventory import add_app, shared, who

Clients = Callable[[str | None], TestClient]
TODAY = clock.today()


def day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def built_on(db: Database, app: str, name: str, technology: str, release: str | None) -> str:
    with db.write(ME.actor) as session:
        component = records.create(
            session, ME, COMPONENT, {"name": name, "application_id": app, "kind": "service"}
        )
        parts.set_technologies(
            session, ME, component, [{"technology": technology, "release": release}]
        )
        return component.ref


def with_releases(db: Database, ref: str, releases: list[dict[str, Any]]) -> None:
    with db.write(ME.actor) as session:
        parts.set_releases(session, ME, records.load(session, ME, TECHNOLOGY, ref), releases)


def test_the_timeline_counts_what_runs_on_each_release(
    as_role: Clients, db: Database, people: People
) -> None:
    python = shared(db, TECHNOLOGY, name="Python", kind="language", radar="adopt")
    with_releases(db, python, [
        {"cycle": "3.9", "support_ends": day(-30)},
        {"cycle": "3.12", "support_ends": day(200)},
        {"cycle": "3.13", "support_ends": day(900)},
    ])  # fmt: skip
    ours = add_app(db, people, name="Ours", retire_planned=day(400))
    secret = add_app(db, people, role="manager", unit="CANCER", name="Secret", restricted=True)
    built_on(db, ours, "Ours API", python, "3.9")
    built_on(db, ours, "Ours jobs", python, "3.9")
    built_on(db, secret, "Secret API", python, "3.9")
    built_on(db, secret, "Secret jobs", python, "3.12")
    for role in ROLES:
        client = as_role(role)
        found = client.get("/api/v1/lifecycle").json()["data"]
        sees = role in ("manager", "architect", "auditor", "admin")
        rows = {
            r["cycle"]: (r["support"], r["components"], r["applications"])
            for r in found["releases"]
        }
        expected = {"3.9": ("ended", 3 if sees else 2, 2 if sees else 1)}
        if sees:
            expected["3.12"] = ("ending", 1, 1)
        assert rows == expected, role  # a release nothing visible runs on is left out
        assert next(r["cycle"] for r in found["releases"]) == "3.9"  # soonest end first
        assert [r["name"] for r in found["retiring"]] == ["Ours"]
        # The counts are the technology's own page's.
        page = client.get(f"/api/v1/technologies/{python}").json()["data"]
        old = next(r for r in page["releases"] if r["cycle"] == "3.9")
        assert len(old["used_by"]) == rows["3.9"][1]
    everything = as_role("member").get("/api/v1/lifecycle", params={"every": "true"})
    assert {r["cycle"] for r in everything.json()["data"]["releases"]} == {"3.9", "3.12", "3.13"}


def test_the_radar_places_what_is_in_use(as_role: Clients, db: Database, people: People) -> None:
    python = shared(db, TECHNOLOGY, name="Python", kind="language", radar="adopt")
    perl = shared(db, TECHNOLOGY, name="Perl", kind="language", radar="hold")
    cobol = shared(db, TECHNOLOGY, name="Cobol", kind="language")
    shared(db, TECHNOLOGY, name="Unused and unplaced", kind="language")
    shared(db, TECHNOLOGY, name="Trial of something", kind="framework", radar="trial")
    app = add_app(db, people, name="Ours")
    built_on(db, app, "A", python, None)
    built_on(db, app, "B", python, None)
    built_on(db, app, "C", perl, None)
    built_on(db, app, "D", cobol, None)
    found = as_role("member").get("/api/v1/radar").json()["data"]
    rings = {
        ring["key"]: [(t["name"], t["components"]) for t in ring["technologies"]]
        for ring in found["rings"]
    }
    assert rings == {
        "adopt": [("Python", 2)],
        "trial": [("Trial of something", 0)],  # placed, though nothing uses it yet
        "assess": [],
        "hold": [("Perl", 1)],
    }
    assert [(t["name"], t["components"]) for t in found["unplaced"]] == [("Cobol", 1)]
    assert found["unused"] == 1


FILE = {
    "python": [
        {"cycle": "3.13", "releaseDate": "2024-10-07", "eol": "2029-10-31", "latest": "3.13.1"},
        {
            "cycle": "3.9",
            "releaseDate": "2020-10-05",
            "eol": "2025-10-31",
            "extendedSupport": False,
        },
        {"cycle": "2.7", "eol": True},
    ],
    "nothing-we-use": [{"cycle": "1", "eol": "2030-01-01"}],
    "broken": "not a list",
}


def test_support_dates_come_in_from_a_file(db: Database, people: People) -> None:
    python = shared(db, TECHNOLOGY, name="Python", kind="language", eol_key="Python")
    shared(db, TECHNOLOGY, name="Unkeyed", kind="language")
    shared(db, TECHNOLOGY, name="Broken", kind="language", eol_key="broken")
    with_releases(db, python, [
        {"cycle": "3.9", "support_ends": "2025-12-31", "extended_ends": "2026-06-30"},
        {"cycle": "3.8", "support_ends": "2024-10-31"},
    ])  # fmt: skip
    architect = who(db, people, "architect")
    with pytest.raises(PermissionDenied), db.write(ME.actor) as session:
        lifecycle.import_end_of_life(session, who(db, people, "steward"), FILE, dry_run=True)
    with db.write(architect.actor) as session:
        dry = lifecycle.import_end_of_life(session, architect, FILE, dry_run=True)
    assert dry["dry_run"] is True and [t["name"] for t in dry["matched"]] == ["Python"]
    assert [(a["cycle"]) for a in dry["added"]] == ["3.13", "2.7"]
    assert [(c["cycle"], c["field"], str(c["from"]), str(c["to"])) for c in dry["changed"]] == [
        ("3.9", "released_on", "None", "2020-10-05"),
        ("3.9", "support_ends", "2025-12-31", "2025-10-31"),
    ]
    assert dry["unmatched"] == ["nothing-we-use"] and dry["without_key"] == 1
    assert dry["problems"] == ["broken: its releases should be a list."]
    with db.read() as session:  # a dry run changed nothing
        page = records.detail(
            session, ME, TECHNOLOGY, records.load(session, ME, TECHNOLOGY, python)
        )
        assert {r["cycle"] for r in page["releases"]} == {"3.9", "3.8"}
    with db.write(architect.actor) as session:
        done = lifecycle.import_end_of_life(session, architect, FILE, dry_run=False)
    assert (len(done["added"]), len(done["changed"])) == (2, 2)
    with db.read() as session:
        record = records.load(session, ME, TECHNOLOGY, python)
        page = records.detail(session, ME, TECHNOLOGY, record)
        releases = {r["cycle"]: r for r in page["releases"]}
        assert set(releases) == {"3.13", "3.9", "3.8", "2.7"}  # nothing is removed
        assert str(releases["3.9"]["support_ends"]) == "2025-10-31"
        # What the file does not give is left as it was.
        assert str(releases["3.9"]["extended_ends"]) == "2026-06-30"
        assert releases["2.7"]["support_ends"] is None and releases["3.13"]["latest"] == "3.13.1"
        told = history.for_record(session, TECHNOLOGY, record)
        assert told and told[0]["actor"] == "Architect Person"
    with db.write(architect.actor) as session:  # and the second time, nothing changes
        again = lifecycle.import_end_of_life(session, architect, FILE, dry_run=False)
    assert again["added"] == [] and again["changed"] == []


def test_the_import_from_the_command_line(
    instance: Instance,
    db: Database,
    people: People,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    shared(db, TECHNOLOGY, name="Python", kind="language", eol_key="python")
    file = tmp_path / "eol.json"
    file.write_text(json.dumps(FILE))
    config = ["--config", str(instance.config.path)]
    assert main([*config, "technologies", "import-eol", str(file), "--dry-run"]) == 0
    assert "1 technologies matched: 3 releases would be added" in capsys.readouterr().out
    assert main([*config, "technologies", "import-eol", str(file)]) == 0
    assert "3 releases added, 0 dates changed" in capsys.readouterr().out
    with db.read() as session:
        record = records.load(session, ME, TECHNOLOGY, "TEC-0001")
        assert len(records.detail(session, ME, TECHNOLOGY, record)["releases"]) == 3
