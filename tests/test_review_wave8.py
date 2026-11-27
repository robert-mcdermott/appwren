"""What the review of wave 8 found, each fixed (see spec/reviews/)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from appwren.db.engine import Database
from appwren.integration import standings
from tests.people import PASSWORD, People
from tests.test_decisions import add_app
from tests.test_standings import _systems

Clients = Callable[[str | None], TestClient]


def _bearer(client: TestClient, token: str) -> dict[str, str]:
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_a_new_password_ends_your_tokens(as_role: Clients) -> None:
    """Finding A: a token made with a stolen session does not outlive the password."""
    member = as_role("member")
    token = member.post("/api/v1/tokens", json={"name": "Mine"}).json()["data"]["token"]
    script = as_role(None)
    assert script.get("/api/v1/home", headers=_bearer(script, token)).status_code == 200
    changed = member.post("/api/v1/session/password", json={
        "current_password": PASSWORD, "new_password": "another long password 77"})  # fmt: skip
    assert changed.status_code in (200, 204), changed.text
    assert script.get("/api/v1/home", headers=_bearer(script, token)).status_code == 401


def test_a_token_never_administers(as_role: Clients) -> None:
    """Finding E: an administrator's own token reads as them, but administers nothing."""
    admin = as_role("admin")
    token = admin.post("/api/v1/tokens", json={"name": "Mine"}).json()["data"]["token"]
    script = as_role(None)
    head = _bearer(script, token)
    assert script.get("/api/v1/home", headers=head).status_code == 200
    for route in ("/api/v1/admin/tokens", "/api/v1/admin/webhooks", "/api/v1/connectors"):
        assert script.get(route, headers=head).status_code == 403, route


def test_the_checkpoint_keeps_sensitive_fields(
    as_role: Clients, db: Database, people: People
) -> None:
    """Finding B: a field the program marks sensitive is not told by the checkpoint."""
    admin = as_role("admin")
    current = admin.get("/api/v1/program").json()["data"]["sensitive_fields"]
    saved = admin.put("/api/v1/program/fields", json={
        "fields": admin.get("/api/v1/program").json()["data"]["fields"],
        "sensitive_fields": [*current, "data_classes", "lifecycle"]})  # fmt: skip
    assert saved.status_code == 200, saved.text
    ref = add_app(db, people, name="Clinic Notes", unit="CANCER", data_classes=["health"])
    said = as_role("member").get(f"/api/v1/checkpoint/{ref}",
                                 params={"data_class": "health"}).json()["data"]  # fmt: skip
    assert said["data_classes"] is None and said["stage"] is None and said["allowed"] is None
    assert "Active" not in str(said["reasons"]) and "health" not in str(said["reasons"])


def test_a_proposed_value_has_a_size(as_role: Clients, db: Database, people: People) -> None:
    """Finding C: a proposal cannot carry megabytes, nor one person fill every slot."""
    ref = add_app(db, people, name="Sample Store")
    member = as_role("member")
    big = member.post(f"/api/v1/applications/{ref}/suggestions",
                      json={"field": "summary", "value": "x" * 5000})  # fmt: skip
    assert big.status_code == 422
    for n in range(10):
        member.post(f"/api/v1/applications/{ref}/suggestions",
                    json={"field": "users", "value": n})  # fmt: skip
    more = member.post(
        f"/api/v1/applications/{ref}/suggestions", json={"field": "users", "value": 99}
    )
    assert more.status_code == 422 and "waiting" in more.text


def test_an_identifier_cannot_climb_the_address(
    as_role: Clients, db: Database, people: People
) -> None:
    """Finding D: '..' as an identifier is not put into a keyed address."""
    _systems(db)
    ref = add_app(db, people, name="Triage Helper")
    steward = as_role("steward")
    current = steward.get(f"/api/v1/applications/{ref}").json()["data"]
    steward.patch(f"/api/v1/applications/{ref}", json={
        "version": current["version"],
        "external_refs": [{"system": "governance_record", "value": ".."}]})  # fmt: skip
    asked: list[str] = []

    def other(url: str, headers: dict[str, str]) -> Any:
        asked.append(url)
        return {"review": {"state": "approved"}}

    assert standings.run_once(db, None, other)["failed"] == 1 and asked == []
