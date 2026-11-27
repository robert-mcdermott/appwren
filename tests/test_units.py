from __future__ import annotations

import pytest

from appwren.access.principal import Principal
from appwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.engine import Database
from appwren.people import units
from tests.people import ME, People, seed


def test_the_tree_nests_and_sorts(db: Database) -> None:
    seed(db)
    with db.read() as session:
        [root] = units.tree(session)
    assert root["name"] == "Bramblewood Institute"
    assert [child["name"] for child in root["children"]] == ["Cancer Biology", "Immunology"]
    assert root["children"][1]["children"][0]["code"] == "HALE"


def test_descendants_and_ancestors(db: Database) -> None:
    people = seed(db)
    with db.read() as session:
        below = units.with_descendants(session, [people.units["IMM"]])
        assert below == {people.units["IMM"], people.units["HALE"]}
        assert units.with_descendants(session, []) == frozenset()
        assert len(units.with_descendants(session, [people.units["BIH"]])) == 4
        above = [unit.code for unit in units.ancestors(session, people.units["HALE"])]
        assert above == ["IMM", "BIH"]


def test_there_is_one_top_unit_and_codes_are_unique(db: Database) -> None:
    people = seed(db)
    with db.write(ME.actor) as session:
        with pytest.raises(Conflict, match="top unit"):
            units.create(session, ME, name="Another", kind="organization")
        with pytest.raises(Conflict, match="code HALE"):
            units.create(
                session,
                ME,
                name="Other Hale",
                kind="lab",
                code="HALE",
                parent_id=people.units["BIH"],
            )
        with pytest.raises(NotFound):
            units.create(session, ME, name="Orphan", kind="lab", parent_id=9999)
        with pytest.raises(Invalid) as caught:
            units.create(session, ME, name="  ", kind="", parent_id=people.units["BIH"])
        assert set(caught.value.errors) == {"name", "kind"}


def test_a_unit_cannot_be_moved_beneath_itself(db: Database) -> None:
    people = seed(db)
    with db.write(ME.actor) as session:
        immuno = units.get(session, people.units["IMM"])
        with pytest.raises(Conflict, match="beneath itself"):
            units.update(session, ME, immuno, {"parent_id": people.units["HALE"]})
        with pytest.raises(Conflict, match="no parent"):
            units.update(session, ME, immuno, {"parent_id": None})
        hale = units.get(session, people.units["HALE"])
        units.update(
            session, ME, hale, {"parent_id": people.units["CANCER"], "name": "Hale Laboratory"}
        )
    with db.read() as session:
        hale = units.get(session, people.units["HALE"])
        assert (hale.parent_id, hale.name) == (people.units["CANCER"], "Hale Laboratory")


def test_closing_a_unit_keeps_it(db: Database) -> None:
    people = seed(db)
    with db.write(ME.actor) as session:
        units.update(session, ME, units.get(session, people.units["HALE"]), {"status": "closed"})
        with pytest.raises(Invalid):
            units.update(session, ME, units.get(session, people.units["HALE"]), {"status": "gone"})
    with db.read() as session:
        assert units.get(session, people.units["HALE"]).status == "closed"


def test_only_administrators_change_units(db: Database, people: People) -> None:
    nobody = Principal(account_id=people.accounts["member"], name="Member Person")
    with db.write(nobody.actor) as session, pytest.raises(PermissionDenied):
        units.create(session, nobody, name="Mine", kind="lab", parent_id=people.units["BIH"])


def test_a_team_that_began_alone_puts_its_organization_above_itself(db: Database) -> None:
    """A team made itself the top unit; later the organization is put above it. There is
    still one top unit, everything beneath the team moves with it, and the history says so."""
    from sqlalchemy import select

    from appwren.db.models import Event

    with db.write(ME.actor) as session:
        team = units.create(session, ME, name="Research Applications", kind="team")
        lab = units.create(session, ME, name="Pilot Lab", kind="lab", parent_id=team.id)
        team_id, lab_id = team.id, lab.id
    with db.write(ME.actor) as session:
        org = units.create(session, ME, name="Northwind Institute", kind="organization", above=True)
        org_id = org.id
    with db.read() as session:
        tops = [unit for unit in units.all_units(session) if unit.parent_id is None]
        assert [unit.id for unit in tops] == [org_id]
        assert units.get(session, team_id).parent_id == org_id
        assert units.get(session, lab_id).parent_id == team_id
        assert units.with_descendants(session, [org_id]) == {org_id, team_id, lab_id}
        moved = session.scalars(
            select(Event).where(
                Event.subject_type == "org_unit", Event.subject_id == team_id,
                Event.action == "updated",
            )
        ).all()  # fmt: skip
        assert moved and "parent_id" in (moved[-1].changes or {})
