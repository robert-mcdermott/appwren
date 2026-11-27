"""What the soak test of 0.9.0 found under load: each test failed before its fix."""

from __future__ import annotations

from collections.abc import Callable

import pytest
import sqlalchemy.exc
from fastapi.testclient import TestClient
from sqlalchemy import event

from appwren import assessment
from appwren.auth import sessions
from appwren.db.engine import Database, make_engine
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
