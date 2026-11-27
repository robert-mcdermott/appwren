"""API tokens an administrator issues, and signed webhooks (slice 4 of wave 7)."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren.core.clock import frozen_at, today, utc_now
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Event, Reminder, WebhookDelivery
from appwren.integration import tokens, webhooks
from appwren.inventory import records
from appwren.inventory.registry import APPLICATION
from tests.conftest import Instance
from tests.people import ME, People
from tests.test_decisions import add_app, decide, who

Clients = Callable[[str | None], TestClient]


def _bearer(client: TestClient, token: str) -> dict[str, str]:
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_a_token_acts_as_its_role_and_reads_only_if_told(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Specimen Log")
    secret = add_app(db, people, name="Secret", restricted=True, unit="CANCER")
    admin = as_role("admin")
    assert as_role("manager").post("/api/v1/admin/tokens", json={"name": "x", "role": "member"}
                                   ).status_code == 403  # fmt: skip
    for bad, field in (
        ({"name": "", "role": "member"}, "name"),
        ({"name": "x", "role": "admin"}, "role"),
        ({"name": "x", "role": "steward"}, "org_unit_id"),  # a steward's token needs its unit
        ({"name": "x", "role": "auditor", "org_unit_id": people.units["HALE"]}, "org_unit_id"),
        ({"name": "x", "role": "member",
          "expires_on": (today() + timedelta(days=400)).isoformat()}, "expires_on"),
    ):  # fmt: skip
        said = admin.post("/api/v1/admin/tokens", json=bad)
        named = {error["location"][-1] for error in said.json()["errors"]}
        assert said.status_code == 422 and field in named, (bad, said.text)
    reader = admin.post("/api/v1/admin/tokens", json={"name": "Reporting", "role": "auditor"})
    assert reader.status_code == 201, reader.text
    shown = reader.json()["data"]
    assert shown["token"].startswith("awt_") and shown["read_only"] is True
    writer = admin.post("/api/v1/admin/tokens", json={
        "name": "Catalog sync", "role": "steward", "org_unit_id": people.units["HALE"],
        "read_only": False})  # fmt: skip
    script = as_role(None)
    # The reading token reads everything an auditor may, and changes nothing.
    head = _bearer(script, shown["token"])
    assert script.get(f"/api/v1/applications/{secret}", headers=head).status_code == 200
    refused = script.patch(f"/api/v1/applications/{ref}", headers=head,
                           json={"summary": "Changed", "version": 1})  # fmt: skip
    assert refused.status_code == 403 and "may read" in refused.json()["detail"]
    # The steward's token keeps the unit's applications, recorded against its name.
    head = _bearer(script, writer.json()["data"]["token"])
    current = script.get(f"/api/v1/applications/{ref}", headers=head).json()["data"]
    change = {"summary": "Kept by a script", "version": current["version"]}
    changed = script.patch(f"/api/v1/applications/{ref}", headers=head, json=change)
    assert changed.status_code == 200, changed.text
    with db.read() as session:
        event = session.scalars(select(Event).where(Event.subject_ref == ref)
                                .order_by(Event.id.desc())).first()  # fmt: skip
        assert event.actor_kind == "token" and event.actor_label.startswith("Catalog sync")
    assert script.get(f"/api/v1/applications/{secret}", headers=head).status_code == 404
    assert script.get("/api/v1/admin/tokens", headers=head).status_code == 403  # never an admin
    # Revoked, it stops at once; listed, its secret is never shown again.
    listed = admin.get("/api/v1/admin/tokens").json()["data"]["tokens"]
    assert all("token" not in row and "token_hash" not in row for row in listed)
    assert listed[0]["last_used_at"] is not None
    admin.delete(f"/api/v1/admin/tokens/{writer.json()['data']['id']}")
    assert script.get(f"/api/v1/applications/{ref}", headers=head).status_code == 401
    assert script.get("/api/v1/applications", headers=_bearer(script, "awt_nonsense")
                      ).status_code == 401  # fmt: skip


def test_tokens_expire(db: Database, people: People) -> None:
    admin = who(db, people, "admin")
    with db.write(admin.actor) as session:
        soon = (today() + timedelta(days=2)).isoformat()
        _row, secret = tokens.create(
            session, admin, {"name": "Short", "role": "member", "expires_on": soon}
        )
        with pytest.raises(PermissionDenied):
            tokens.create(session, who(db, people, "manager"), {"name": "x", "role": "member"})
    with db.bookkeeping() as session:
        assert tokens.authenticate(session, secret) is not None
    with frozen_at(utc_now() + timedelta(days=4)), db.bookkeeping() as session:
        assert tokens.authenticate(session, secret) is None


def test_a_webhook_goes_only_to_the_public_internet_and_follows_no_redirect() -> None:
    for inside in (
        "http://10.0.0.5/hook",
        "https://169.254.169.254/latest",
        "https://192.168.1.1/",
        "https://localhost/hook",
        "https://127.0.0.1:8000/api",
    ):  # fmt: skip  (finding 6: not even this machine)
        with pytest.raises(ValueError, match="public internet"):
            webhooks._post(inside, b"{}", {})
    assert webhooks._public("127.0.0.1") is False
    assert (
        webhooks._NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://x/") is None
    )


class Receiver:
    """Stands in for the other system: remembers what it was sent, and answers as told."""

    def __init__(self) -> None:
        self.got: list[tuple[str, bytes, dict[str, str]]] = []
        self.answer = 204

    def __call__(self, url: str, body: bytes, headers: dict[str, str]) -> int:
        self.got.append((url, body, headers))
        if self.answer == 0:
            raise OSError("no route")
        return self.answer


def test_webhooks_are_told_signed_and_tried_again(
    instance: Instance, db: Database, people: People
) -> None:
    admin = who(db, people, "admin")
    receiver = Receiver()
    start = utc_now()
    with frozen_at(start - timedelta(hours=1)), db.write(admin.actor) as session:
        for bad, field in (
            ({"name": "x", "url": "ftp://example.org", "topics": ["decision.recorded"]}, "url"),
            ({"name": "x", "url": "http://example.org/h", "topics": ["decision.recorded"]}, "url"),
            ({"name": "x", "url": "https://u:p@example.org/", "topics": ["decision.recorded"]},
             "url"),
            ({"name": "x", "url": "https://localhost/hook", "topics": ["decision.recorded"]},
             "url"),
            ({"name": "x", "url": "https://10.1.2.3/hook", "topics": ["decision.recorded"]},
             "url"),
            ({"name": "x", "url": "https://example.org/hook", "topics": []}, "topics"),
            ({"name": "x", "url": "https://example.org/hook", "topics": ["weather"]}, "topics"),
        ):  # fmt: skip
            with pytest.raises(Invalid) as refused:
                webhooks.create(session, admin, bad)
            assert field in refused.value.errors
        with pytest.raises(PermissionDenied):
            webhooks.create(session, who(db, people, "manager"), {})
        hook, secret = webhooks.create(session, admin, {
            "name": "Service desk", "url": "https://desk.example.org/hooks/appwren",
            "topics": list(webhooks.TOPICS)})  # fmt: skip
        hook_id = hook.id
        made = session.scalars(select(Event).where(Event.subject_type == "webhook")).one()
        assert secret.startswith("whsec_") and secret not in json.dumps(made.changes)
    ref = add_app(db, people, name="Old Billing", lifecycle="active")
    decide(db, people, "manager", ref, disposition="retire")
    with db.write(ME.actor) as session:
        app = records.load(session, ME, APPLICATION, ref)
        records.update(session, ME, APPLICATION, app, {"lifecycle": "phase_in"},
                       version=app.version)  # fmt: skip
        session.add(Reminder(subject_type="confirmation", subject_id=app.id,
                             due_on=today(), stage="overdue", sent_on=today()))  # fmt: skip
    ran = webhooks.run_once(db, None, receiver)
    assert ran == {"queued": 3, "sent": 3, "failed": 0}, ran
    assert webhooks.run_once(db, None, receiver) == {"queued": 0, "sent": 0, "failed": 0}
    bodies = {json.loads(body)["topic"]: json.loads(body) for _u, body, _h in receiver.got}
    assert set(bodies) == {"decision.recorded", "application.stage_changed",
                           "confirmation.lapsed"}  # fmt: skip
    assert bodies["decision.recorded"]["data"]["disposition"] == "retire"
    moved = bodies["application.stage_changed"]["data"]
    assert (moved["ref"], moved["from"], moved["to"]) == (ref, "active", "phase_in")
    assert bodies["confirmation.lapsed"]["data"]["name"] == "Old Billing"
    url, body, headers = receiver.got[0]
    assert url == "https://desk.example.org/hooks/appwren"
    expected = hmac.new(secret.encode(), headers["X-AppWren-Timestamp"].encode() + b"." + body,
                        hashlib.sha256).hexdigest()  # fmt: skip
    assert headers["X-AppWren-Signature"] == f"sha256={expected}"
    # A receiver that fails is tried again later, and the webhook says how it is going.
    receiver.answer = 500
    decide(db, people, "manager", ref, disposition="replace")
    assert webhooks.run_once(db, None, receiver)["failed"] == 1
    assert webhooks.run_once(db, None, receiver)["failed"] == 0  # not yet due again
    receiver.answer = 204
    with frozen_at(utc_now() + timedelta(minutes=3)):
        assert webhooks.run_once(db, None, receiver)["sent"] == 1
    with db.read() as session:
        shown = webhooks.view(session, webhooks.find(session, hook_id))
        assert shown["last_status"] == "Delivered" and "secret" not in shown
        assert max(session.scalars(select(WebhookDelivery.attempts))) == 2
    assert webhooks.send_test(db, admin, hook_id, receiver) == "Delivered"
    with db.write(admin.actor) as session:
        webhooks.change(session, admin, webhooks.find(session, hook_id), {"active": False})
    decide(db, people, "manager", ref, disposition="tolerate")
    assert webhooks.run_once(db, None, receiver)["queued"] == 0  # switched off: nothing queued


def test_webhooks_over_the_api(as_role: Clients) -> None:
    admin = as_role("admin")
    admin.app.state.webhook_send = Receiver()  # type: ignore[attr-defined]
    body = {"name": "Chat", "url": "https://chat.example.org/in", "topics": ["decision.recorded"]}
    made = admin.post("/api/v1/admin/webhooks", json=body)
    assert made.status_code == 201 and made.json()["data"]["secret"].startswith("whsec_")
    hook = made.json()["data"]["id"]
    listed = admin.get("/api/v1/admin/webhooks").json()["data"]
    assert listed["webhooks"][0]["name"] == "Chat" and "secret" not in listed["webhooks"][0]
    assert len(listed["topics"]) == 4
    assert admin.post(f"/api/v1/admin/webhooks/{hook}/test").json()["data"]["result"] == "Delivered"
    assert admin.patch(f"/api/v1/admin/webhooks/{hook}", json={"active": False}
                       ).json()["data"]["active"] is False  # fmt: skip
    assert admin.delete(f"/api/v1/admin/webhooks/{hook}").json()["data"]["webhooks"] == []


def test_a_token_matches_nothing_by_its_missing_account(
    as_role: Clients, db: Database, people: People
) -> None:
    """Records the command line made, and contracts nobody owns, have no account on them. A
    token has none either, and must not be taken for their maker (review finding 1)."""
    from tests.test_costs import contract

    secret = add_app(db, people, name="Secret", restricted=True, unit="CANCER")
    shown = add_app(db, people, name="Open")
    deal = contract(db, [(secret, None)], name="Secret licenses", annual_value=123_456)
    issued = as_role("admin").post(
        "/api/v1/admin/tokens", json={"name": "Reader", "role": "member"}
    )
    script = as_role(None)
    head = _bearer(script, issued.json()["data"]["token"])
    listed = script.get("/api/v1/applications", headers=head).json()["data"]
    assert [row["ref"] for row in listed] == [shown]
    exported = script.get("/api/v1/exports/applications", headers=head)
    assert exported.status_code == 200 and "Secret" not in exported.text
    contracts = script.get("/api/v1/contracts", headers=head).json()["data"]
    assert deal not in [row["ref"] for row in contracts] and "123456" not in str(contracts)


def test_a_hidden_application_is_named_nowhere(
    as_role: Clients, db: Database, people: People
) -> None:
    """A restricted application is not named through a reference, a message, a scenario, or
    the history of one that points at it (review finding 2)."""
    from tests.test_intake import capability, serves

    with db.write(ME.actor) as session:  # owned by someone the steward is not
        secret = records.create(session, ME, APPLICATION, {
            "name": "Hidden Ledger", "org_unit_id": people.units["CANCER"], "restricted": True,
        }, accountable=people.accounts["admin"]).ref  # fmt: skip
    shown = add_app(db, people, name="Open Ledger")
    with db.write(ME.actor) as session:
        hidden = records.load(session, ME, APPLICATION, secret)
        hidden.successor_id = records.load(session, ME, APPLICATION, shown).id
        hidden_id = hidden.id
        app = records.load(session, ME, APPLICATION, shown)
        records.update(session, ME, APPLICATION, app, {"successor_id": secret},
                       version=app.version)  # fmt: skip
    member, steward = as_role("member"), as_role("steward")
    page = member.get(f"/api/v1/applications/{shown}").json()["data"]
    assert page["replaces"] == [] and page["successor"] is None
    told = member.get(f"/api/v1/applications/{shown}/history").text
    assert "Hidden Ledger" not in told and "may not see" in told
    # Trying ids one by one names nothing.
    current = steward.get(f"/api/v1/applications/{shown}").json()["data"]
    change = {"successor_id": str(hidden_id), "version": current["version"]}
    tried = steward.patch(f"/api/v1/applications/{shown}", json=change)
    assert tried.status_code == 422 and "Hidden Ledger" not in tried.text
    # A capability's primary provider is not named either.
    cap = capability(db, "Ledgers")
    serves(db, secret, cap, primary=True)
    wanted = {"capabilities": [{"capability": cap, "is_primary": True}]}
    refused = steward.put(f"/api/v1/applications/{shown}/capabilities", json=wanted)
    assert refused.status_code == 422 and "Hidden Ledger" not in refused.text
    # Nor the application a scenario would move work into.
    architect = as_role("manager")
    made = architect.post("/api/v1/scenarios", json={"name": "Fold the ledgers"}).json()["data"]
    architect.put(f"/api/v1/scenarios/{made['ref']}/changes", json={"changes": [
        {"application": shown, "action": "consolidate", "into": secret}]})  # fmt: skip
    seen = member.get(f"/api/v1/scenarios/{made['ref']}").text
    assert "Hidden Ledger" not in seen and "may not see" in seen
