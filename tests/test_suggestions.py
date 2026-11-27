"""A person's own token, and the changes it proposes (slice 2 of wave 8)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.db.engine import Database
from appwren.db.models import Event
from tests.people import People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def _bearer(client: TestClient, token: str) -> dict[str, str]:
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_a_token_of_your_own_reads_and_proposes(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Sample Store", users=40)
    member = as_role("member")
    made = member.post("/api/v1/tokens", json={"name": "My assistant"})
    assert made.status_code == 201, made.text
    token = made.json()["data"]["token"]
    assert made.json()["data"]["personal"] is True
    assert [row["name"] for row in member.get("/api/v1/tokens").json()["data"]["tokens"]] == [
        "My assistant"
    ]
    script = as_role(None)
    head = _bearer(script, token)
    # It reads as the person does, and changes nothing.
    page = script.get(f"/api/v1/applications/{ref}", headers=head)
    assert page.status_code == 200
    change = {"users": 90, "version": page.json()["data"]["version"]}
    refused = script.patch(f"/api/v1/applications/{ref}", headers=head, json=change)
    assert refused.status_code == 403 and "propose" in refused.json()["detail"]
    assert script.post("/api/v1/tokens", headers=head, json={"name": "More"}).status_code == 403
    # It proposes; nothing on the record moves.
    proposal = {"field": "users", "value": 90, "note": "From the sign-in log"}
    proposed = script.post(f"/api/v1/applications/{ref}/suggestions", headers=head, json=proposal)
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["data"]["source"].startswith("Member Person (token")
    assert member.get(f"/api/v1/applications/{ref}").json()["data"]["users"] == 40
    bad = script.post(f"/api/v1/applications/{ref}/suggestions", headers=head,
                      json={"field": "annual_cost", "value": 1})  # fmt: skip
    assert bad.status_code == 422  # a sensitive field the person may not see
    waiting = as_role("steward").get(f"/api/v1/applications/{ref}/suggestions").json()["data"]
    assert [s["field_label"] for s in waiting["pending"]] == ["People who use it"]
    assert waiting["may_decide"] is True
    suggestion = waiting["pending"][0]["id"]
    # The token may not accept it; someone who keeps the application does, as their own edit.
    assert script.post(f"/api/v1/suggestions/{suggestion}/accept", headers=head).status_code == 403
    assert member.post(f"/api/v1/suggestions/{suggestion}/accept").status_code == 403
    accepted = as_role("steward").post(f"/api/v1/suggestions/{suggestion}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["decided"][0]["status"] == "accepted"
    assert member.get(f"/api/v1/applications/{ref}").json()["data"]["users"] == 90
    with db.read() as session:
        edit = session.scalars(select(Event).where(Event.subject_ref == ref)
                               .order_by(Event.id.desc())).first()  # fmt: skip
        assert edit.actor_label == "Steward Person"
    assert as_role("steward").post(f"/api/v1/suggestions/{suggestion}/accept").status_code == 409
    # Revoked, it stops.
    member.delete(f"/api/v1/tokens/{made.json()['data']['id']}")
    assert script.get(f"/api/v1/applications/{ref}", headers=head).status_code == 401


def test_a_proposal_that_does_not_hold_is_not_made_on_acceptance(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Sample Store")
    member, steward = as_role("member"), as_role("steward")
    made = member.post(f"/api/v1/applications/{ref}/suggestions",
                       json={"field": "tier", "value": "nine"})  # fmt: skip
    assert made.status_code == 201  # checked when it is accepted, by the usual rules
    refused = steward.post(f"/api/v1/suggestions/{made.json()['data']['id']}/accept")
    assert refused.status_code == 422
    dismissed = steward.post(f"/api/v1/suggestions/{made.json()['data']['id']}/dismiss")
    assert dismissed.json()["data"]["decided"][0]["status"] == "dismissed"
