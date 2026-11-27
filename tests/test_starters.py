"""Starter programs: the default program as one kind of organization would first change it
(slice 3 of wave 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from appwren import assessment
from appwren.core.errors import Invalid, NotFound
from appwren.db.engine import Database
from appwren.db.models import Capability
from appwren.events.actor import Actor
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from appwren.program import packs, vocab
from tests.people import ME, People
from tests.test_cli import run

STARTERS = ["starter-academic-medical-center", "starter-company", "starter-nonprofit",
            "starter-research-institute", "starter-university"]  # fmt: skip
SAMPLE = {"name": "Shared Tracker", "tier": "3", "users": 120, "maintainers": 2,
          "annual_cost": 20_000, "sign_in": "sso", "monitoring": "alerting",
          "backup": "vendor", "data_classes": ["internal"], "sourcing": "saas"}  # fmt: skip


def test_every_starter_is_listed_and_says_what_it_is_for() -> None:
    found = packs.starters()
    assert [item["key"] for item in found] == STARTERS
    assert all(item["description"] and item["title"].startswith("Starter: ") for item in found)
    for key in STARTERS:
        assert packs.check(packs.starter(key)) == []
    with pytest.raises(NotFound, match="There are: starter-academic"):
        packs.starter("starter-castle")


@pytest.mark.parametrize("key", STARTERS)
def test_a_new_installation_begins_from_a_starter(key: str, db: Database, people: People) -> None:
    pack = packs.starter(key)
    with db.write(Actor.command("Setup")) as session:
        packs.start(session, key)
        packs.install(session)  # the default program fills in the rest
    with db.read() as session:
        tops = [row.key for row in session.scalars(
            select(Capability).where(Capability.parent_id.is_(None)).order_by(Capability.position)
        )]  # fmt: skip
        assert tops == [item["key"] for item in pack["capabilities"]]
        domains = vocab.keys(session, "domains")  # those it leaves out are kept, retired
        assert domains == [item["key"] for item in pack["vocabularies"]["domains"]]
        assert vocab.get(session, "lifecycle") == vocab.DEFAULTS["lifecycle"]  # left as it was
    # The same sample application scores under every starter.
    with db.write(ME.actor) as session:
        app = records.create(
            session, ME, APPLICATION, {**SAMPLE, "org_unit_id": people.units["HALE"]}
        )
        scored = assessment.score_one(session, app)
    assert scored["scores"]["cost_burden"] is not None and scored["recommendation"]
    # Over a program already there, a starter is refused: it is imported instead.
    with db.write(Actor.command("Setup")) as session, pytest.raises(Invalid) as refused:
        packs.start(session, key)
    assert "program import" in refused.value.errors["pack"]


def test_from_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "appwren.toml"
    assert run("init", "--program", "starter-company", "--organization", "Acme Example",
               config=config) == 0  # fmt: skip
    out = capsys.readouterr().out
    assert "started from company" in out
    assert run("program", "starters", config=config) == 0
    assert "starter-university" in capsys.readouterr().out
    assert run("program", "import", "starter-university", "--dry-run", config=config) == 0
    assert "Would change" in capsys.readouterr().out
    assert run("program", "import", "starter-castle", config=config) == 1
    assert "no starter program" in capsys.readouterr().err

