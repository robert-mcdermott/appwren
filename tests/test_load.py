"""What the soak test of 0.9.0 found under load: each test failed before its fix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
import sqlalchemy.exc
from fastapi.testclient import TestClient
from sqlalchemy import event

from appwren import assessment
from appwren.auth import sessions
from appwren.db.engine import Database, make_engine
from tests.conftest import Instance
from tests.people import People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def test_a_signed_in_read_takes_no_write_lock(as_role: Clients) -> None:
    """On SQLite a transaction that may write takes the write lock, so checking a session in
    one made every request wait for whoever was writing."""
    member = as_role("member")
    engine = member.app.state.db.engine  # type: ignore[attr-defined]
    writes: list[bool] = []

    def begun(conn) -> None:  # type: ignore[no-untyped-def]
        writes.append(bool(conn.get_execution_options().get("appwren_write")))

    event.listen(engine, "begin", begun)
    try:
        for _ in range(3):
            assert member.get("/api/v1/session").status_code == 200
            assert member.get("/api/v1/vocabularies").status_code == 200
    finally:
        event.remove(engine, "begin", begun)
    assert writes and not any(writes), f"{writes.count(True)} of {len(writes)} began to write"


def test_a_busy_database_is_answered_503_when_checking_who_asks(
    as_role: Clients, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = as_role("member")

    def busy(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise sqlalchemy.exc.TimeoutError("QueuePool limit reached")

    monkeypatch.setattr(sessions, "load", busy)
    answer = member.get("/api/v1/vocabularies")
    assert answer.status_code == 503, answer.text
    assert answer.headers.get("Retry-After") == "5"
    assert "busy" in answer.json()["title"].lower() or "busy" in answer.text.lower()


def test_a_busy_database_is_answered_503_in_a_route(
    as_role: Clients, monkeypatch: pytest.MonkeyPatch
) -> None:
    from appwren import reporting

    member = as_role("member")

    def busy(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise sqlalchemy.exc.TimeoutError("QueuePool limit reached")

    monkeypatch.setattr(reporting, "owed", busy)
    answer = member.get("/api/v1/home")
    assert answer.status_code == 503 and answer.headers.get("Retry-After") == "5", answer.text


@pytest.mark.sqlite_only
def test_the_pool_has_a_connection_for_every_request_thread(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from appwren.db.engine import POOL

    engine = make_engine(f"sqlite:///{tmp_path / 'pool.db'}")
    try:
        assert engine.pool.size() == POOL["pool_size"]
        assert POOL["pool_size"] + POOL["max_overflow"] >= 40  # the server's request threads
    finally:
        engine.dispose()


def test_home_looks_only_at_what_the_person_needs(
    as_role: Clients, db: Database, people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    for n in range(6):
        add_app(db, people, name=f"Elsewhere {n}", unit="CANCER")
    scored: list[int] = []
    original = assessment.score_all

    def counting(session, apps, *args, **kwargs):  # type: ignore[no-untyped-def]
        scored.append(len(apps))
        return original(session, apps, *args, **kwargs)

    monkeypatch.setattr(assessment, "score_all", counting)
    member = as_role("member")  # named on nothing, keeps nothing
    assert member.get("/api/v1/home").status_code == 200
    assert max(scored, default=0) == 0, scored  # nothing to look at but their own
    scored.clear()
    assert as_role("manager").get("/api/v1/home").status_code == 200
    assert scored and max(scored) >= 6  # a manager over everything still sees all of it


# --- What the soak test of 0.10.0 found: the scheduler's first run held everyone up ----------


def test_reminders_are_told_a_batch_at_a_time(
    instance: Instance, db: Database, people: People, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first run that finds thousands to tell wrote them all in one transaction, and on
    SQLite nobody could sign in for the three and a half seconds that took at 5,000
    applications. Each batch now commits, and the same is told."""
    from datetime import UTC, datetime

    from appwren import jobs
    from appwren.core.clock import frozen_at
    from tests.test_schedule import assessed_app

    with frozen_at(datetime(2026, 3, 2, 9, tzinfo=UTC)):
        for _ in range(3):
            assessed_app(db, people)
    monkeypatch.setattr(jobs.reminders, "BATCH", 1)
    commits: list[int] = []
    real = db.bookkeeping

    def counting():  # type: ignore[no-untyped-def]
        commits.append(1)
        return real()

    monkeypatch.setattr(db, "bookkeeping", counting)
    with frozen_at(datetime(2027, 9, 23, 9, tzinfo=UTC)):  # three weeks late: up to the leader
        counts = jobs._reminders(db, instance.config)
        first = len(commits)
        assert jobs._reminders(db, instance.config)["escalated"] == 0  # said once
    assert counts["escalated"] == 3 and first == 3  # one batch for each


def test_a_snapshot_is_scored_by_reading_and_written_at_once(db: Database, people: People) -> None:
    """The monthly snapshot worked every score out inside its write. They are now worked out
    by reading first, and used only if nothing has changed since; if it has, they are worked
    out again inside the write, so the snapshot is still of one moment."""
    from appwren import decisions
    from appwren.events.actor import Actor

    for n in range(3):
        add_app(db, people, name=f"Snapshot {n}")
    with db.read() as session:
        scored = decisions.monthly_scores(session)
    assert scored is not None and len(scored.results) == 3
    calls: list[int] = []
    original = assessment.score_all

    def counting(session, apps, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(len(apps))
        return original(session, apps, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(assessment, "score_all", counting)
        with db.write(Actor.system("Scheduler")) as session:
            assert decisions.take_monthly(session, scored=scored) == 1
        assert calls == []  # nothing had changed: what was read is used
        with db.write(Actor.system("Scheduler")) as session:
            assert decisions.take_monthly(session, scored=scored) == 0  # once a month
    stale = replace(scored, generation=scored.generation - 1)
    with db.write(Actor.system("Scheduler")) as session:
        row = decisions.take_portfolio_snapshot(
            session, decisions.Principal.for_command("Test"), "Again", scored=stale
        )
        assert row.count == 3  # worked out again, inside the write
