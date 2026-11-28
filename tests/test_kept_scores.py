"""Scores kept between changes (slice 3 of wave 10): reused while nothing a score reads has
changed, worked out again when it has, and checked against a fresh working in every test."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from appwren import assessment
from appwren.assessment import kept
from appwren.core.clock import frozen_at, utc_now
from appwren.db import changes
from appwren.db.engine import Database
from appwren.db.models import Application, FactValue, Notice
from appwren.events.actor import Actor
from tests.people import People
from tests.test_decisions import add_app

TESTER = Actor.command("Test")


@pytest.fixture
def portfolio(db: Database, people: People) -> Iterator[list[str]]:
    kept.forget()
    yield [add_app(db, people, name=f"Tracker {n}") for n in range(3)]
    kept.forget()


def _scores(db: Database) -> tuple[dict[int, dict], dict[str, int]]:
    before = dict(kept.counts)
    with db.read() as session:
        apps = list(session.scalars(select(Application).order_by(Application.id)))
        found = assessment.score_all(session, apps)
    return found, {key: kept.counts[key] - before[key] for key in before}


def test_scores_are_reused_while_nothing_changes(db: Database, portfolio: list[str]) -> None:
    first, worked = _scores(db)
    assert worked == {"reused": 0, "worked_out": 3}
    again, worked = _scores(db)
    assert worked == {"reused": 3, "worked_out": 0} and again == first


def test_a_change_works_them_out_again(db: Database, portfolio: list[str]) -> None:
    first, _ = _scores(db)
    with db.write(TESTER) as session:
        app = session.scalars(select(Application).where(Application.ref == portfolio[0])).one()
        app.users = 4000
    again, worked = _scores(db)
    assert worked == {"reused": 0, "worked_out": 3}
    assert again[app.id] != first[app.id]


def test_a_write_no_score_reads_keeps_them(
    db: Database, people: People, portfolio: list[str]
) -> None:
    _scores(db)
    with db.write(TESTER) as session:
        before = changes.generation(session)
        session.add(Notice(account_id=people.accounts["member"], kind="test", href="/",
                           text="Nothing a score reads", created_at=utc_now()))  # fmt: skip
        session.flush()
        assert changes.generation(session) == before
    _, worked = _scores(db)
    assert worked == {"reused": 3, "worked_out": 0}


def test_a_source_s_fact_counts_although_it_is_not_history(
    db: Database, portfolio: list[str]
) -> None:
    _scores(db)
    with db.write(TESTER) as session:
        app = session.scalars(select(Application).where(Application.ref == portfolio[1])).one()
        session.add(FactValue(record_type="application", record_id=app.id, field="incidents_90d",
                              value=12, source="push", source_name="Service desk",
                              read_at=utc_now()))  # fmt: skip
    _, worked = _scores(db)
    assert worked["worked_out"] == 3


def test_a_change_taken_back_leaves_them_good(db: Database, portfolio: list[str]) -> None:
    _scores(db)
    with pytest.raises(RuntimeError), db.write(TESTER) as session:
        app = session.scalars(select(Application).where(Application.ref == portfolio[0])).one()
        app.users = 1
        session.flush()
        raise RuntimeError("never committed")
    _, worked = _scores(db)
    assert worked == {"reused": 3, "worked_out": 0}


def test_a_new_day_works_them_out_again(db: Database, portfolio: list[str]) -> None:
    _scores(db)
    with frozen_at(utc_now() + timedelta(days=1)):
        _, worked = _scores(db)
    assert worked == {"reused": 0, "worked_out": 3}


def test_a_session_that_writes_never_keeps_or_reuses(db: Database, portfolio: list[str]) -> None:
    _scores(db)
    before = dict(kept.counts)
    with db.write(TESTER) as session:
        apps = list(session.scalars(select(Application)))
        assessment.score_all(session, apps)
    assert kept.counts == before


def test_part_of_the_portfolio_is_scored_from_what_is_kept(
    db: Database, portfolio: list[str]
) -> None:
    whole, _ = _scores(db)
    before = dict(kept.counts)
    with db.read() as session:
        one = session.scalars(select(Application).where(Application.ref == portfolio[2])).one()
        part = assessment.score_all(session, [one])
    assert part == {one.id: whole[one.id]}
    assert kept.counts["reused"] - before["reused"] == 1


def test_a_change_made_around_the_counter_is_caught(db: Database, portfolio: list[str]) -> None:
    """Only the history, references, and a restore may write around the session. If anything
    else did, the check the suite runs under would fail rather than show a stale score."""
    _scores(db)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE application SET users = 9999"))
    with pytest.raises(kept.KeptScoresDiffer):
        _scores(db)
