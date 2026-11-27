"""Stage gates: what each stage requires, required (slice 4 of wave 5)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from tests.people import People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def move(client: TestClient, ref: str, stage: str) -> object:
    app = client.get(f"/api/v1/applications/{ref}").json()["data"]
    return client.patch(f"/api/v1/applications/{ref}",
                        json={"version": app["version"], "lifecycle": stage})  # fmt: skip


def test_a_move_short_of_the_stage_is_refused_with_what_is_missing(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Thin", lifecycle="proposed", summary="Thin.",
                  purpose="operations", data_classes=["internal"])  # fmt: skip
    steward = as_role("steward")
    said = move(steward, ref, "phase_in")
    assert said.status_code == 422  # type: ignore[attr-defined]
    message = said.json()["errors"][0]["message"]  # type: ignore[attr-defined]
    assert message.startswith("Before it moves to Phase-in, record ")
    assert "the capabilities it serves" in message and "hosting" in message
    # A move back, and a retirement, need nothing.
    ok = add_app(db, people, name="Kept", lifecycle="active")
    assert move(steward, ok, "phase_in").status_code == 200  # type: ignore[attr-defined]
    assert move(steward, ref, "retired").status_code == 200  # type: ignore[attr-defined]


def test_with_the_gates_off_a_move_is_allowed_and_the_gaps_still_shown(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Thin", lifecycle="proposed")
    manager, steward = as_role("manager"), as_role("steward")
    assert steward.put("/api/v1/program/decision-rules",
                       json={"stage_gates": False}).status_code == 403  # fmt: skip
    rules = manager.put("/api/v1/program/decision-rules", json={"stage_gates": False})
    assert rules.json()["data"] == {"owners_may_decide": False, "stage_gates": False}
    assert move(steward, ref, "active").status_code == 200  # type: ignore[attr-defined]
    shown = steward.get(f"/api/v1/applications/{ref}").json()["data"]
    assert shown["lifecycle"] == "active" and "capabilities" in shown["missing"]["now"]
    # Switching owners_may_decide alone leaves the gates as they are.
    again = manager.put("/api/v1/program/decision-rules", json={"owners_may_decide": True})
    assert again.json()["data"] == {"owners_may_decide": True, "stage_gates": False}
