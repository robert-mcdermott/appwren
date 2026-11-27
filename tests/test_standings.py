"""How a linked record stands in another system of record (slice 4 of wave 8)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.db.engine import Database
from appwren.db.models import Event
from appwren.integration import standings
from appwren.program import packs, vocab
from tests.people import ME, People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def _systems(db: Database, **more: Any) -> None:
    with db.write(ME.actor) as session:
        items = [dict(item) for item in vocab.get(session, "external_systems")]
        for item in items:
            if item["key"] == "governance_record":
                item.update({"label": "AI-use review",
                             "url": "https://reviews.example.org/r/{id}",
                             "standing_url": "https://reviews.example.org/api/r/{id}",
                             "standing_field": "review.state", **more})  # fmt: skip
        vocab.put(session, "external_systems", items)


def test_a_linked_record_shows_how_it_stands_elsewhere(
    as_role: Clients, db: Database, people: People
) -> None:
    _systems(db, key_env="REVIEWS_TOKEN")
    ref = add_app(db, people, name="Triage Helper")
    steward = as_role("steward")
    current = steward.get(f"/api/v1/applications/{ref}").json()["data"]
    linked = steward.patch(f"/api/v1/applications/{ref}", json={
        "version": current["version"],
        "external_refs": [{"system": "governance_record", "value": "UC-0042"}]})  # fmt: skip
    assert linked.status_code == 200, linked.text
    asked: list[tuple[str, dict[str, str]]] = []
    answers: dict[str, Any] = {"review": {"state": "approved"}}

    def other_system(url: str, headers: dict[str, str]) -> Any:
        asked.append((url, headers))
        if answers.get("fail"):
            raise standings.StandingError("The system answered 503.")
        return answers

    import os

    os.environ["REVIEWS_TOKEN"] = "secret-for-reviews"
    try:
        assert standings.run_once(db, None, other_system) == {"read": 1, "changed": 1, "failed": 0}
    finally:
        del os.environ["REVIEWS_TOKEN"]
    assert asked[0][0] == "https://reviews.example.org/api/r/UC-0042"
    assert asked[0][1]["Authorization"] == "Bearer secret-for-reviews"
    shown = steward.get(f"/api/v1/applications/{ref}").json()["data"]["external_refs"][0]
    assert (shown["label"], shown["standing"]) == ("AI-use review", "approved")
    assert shown["url"] == "https://reviews.example.org/r/UC-0042"
    with db.read() as session:  # a change of standing is history
        changed = session.scalars(select(Event).where(Event.subject_type == "external_ref")
                                  .order_by(Event.id.desc())).first()  # fmt: skip
        assert changed.changes["standing"] == [None, "approved"]
        assert changed.actor_label == "Standings"
    # A failed read says why, and leaves the standing as it was.
    answers["fail"] = True
    assert standings.run_once(db, None, other_system)["failed"] == 1
    shown = steward.get(f"/api/v1/applications/{ref}").json()["data"]["external_refs"][0]
    assert shown["standing"] == "approved" and "503" in shown["standing_error"]


def test_nothing_is_read_until_the_program_says_where(db: Database, people: People) -> None:
    add_app(db, people, name="Triage Helper")

    def never(url: str, headers: dict[str, str]) -> Any:
        raise AssertionError("asked")

    assert standings.run_once(db, None, never) == {"read": 0, "changed": 0, "failed": 0}


def test_a_standing_address_is_checked_like_any_pack() -> None:
    pack = {"pack": {"key": "x", "kind": "program"}, "vocabularies": {"external_systems": [
        {"key": "a", "label": "A", "standing_url": "http://inside/{id}"},
        {"key": "b", "label": "B", "standing_url": "https://b.example.org/{id}",
         "key_env": "APPWREN_SSO_CLIENT_SECRET"}]}}  # fmt: skip
    problems = " ".join(packs.check(pack))
    assert "standing address for a" in problems and "server's own" in problems


def test_only_an_administrator_says_where_a_standing_is_read(as_role: Clients) -> None:
    """A manager shapes the lists, but not where AppWren reaches out, or with which key."""
    manager, admin = as_role("manager"), as_role("admin")
    items = manager.get("/api/v1/program").json()["data"]["vocabularies"]["external_systems"]
    changed = [{**item, "standing_url": "https://elsewhere.example.org/{id}",
                "key_env": "SOME_TOKEN"} if item["key"] == "governance_record" else item
               for item in items]  # fmt: skip
    refused = manager.put("/api/v1/program/vocabularies/external_systems", json={"items": changed})
    assert refused.status_code == 422 and "administrator" in refused.text
    renamed = [{**item, "label": "Reviews"} if item["key"] == "governance_record" else item
               for item in items]  # fmt: skip
    assert manager.put("/api/v1/program/vocabularies/external_systems",
                       json={"items": renamed}).status_code == 200  # fmt: skip
    assert admin.put("/api/v1/program/vocabularies/external_systems",
                     json={"items": changed}).status_code == 200  # fmt: skip
