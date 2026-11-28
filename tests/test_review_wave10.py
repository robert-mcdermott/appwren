"""What the review of wave 10's code found, before 0.10.0: each test failed before its fix.
The record is spec/reviews/2026-11-security-and-accessibility.md."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from appwren import assessment, connectors, jobs
from appwren.api.app import create_app
from appwren.assessment import kept
from appwren.assistant_servers import AssistantError, ask
from appwren.config import AssistantConfig
from appwren.core.clock import utc_now
from appwren.core.errors import ConfigError
from appwren.db.engine import Database
from appwren.db.models import Application, AssistantExchange, Event
from appwren.inventory import applications, records
from appwren.inventory.registry import APPLICATION, CAPABILITY, CONTRACT, VENDOR
from appwren.landscape import costs
from tests.conftest import Instance
from tests.people import ME, People, email_of, sign_in
from tests.test_assessment import GOOD, assess
from tests.test_config import parse
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]
QUESTION = {"question": "Which applications watch freezers?"}
ASKED = [{"role": "user", "content": "Are you there?"}]


def _assistant(instance: Instance, answer: Callable[..., str], **settings: Any):  # type: ignore[no-untyped-def]
    config = replace(instance.config, assistant=AssistantConfig(
        url="https://models.example.org/v1", model="small-model", **settings))  # fmt: skip
    app = create_app(config)
    app.state.assistant_ask = answer
    opened: list[TestClient] = []

    def as_role(role: str) -> TestClient:
        client = TestClient(app, base_url="http://localhost")
        client.__enter__()
        opened.append(client)
        sign_in(client, email_of(role))
        return client

    return as_role, opened


@pytest.fixture
def closing() -> Iterator[list[TestClient]]:
    opened: list[TestClient] = []
    yield opened
    for client in opened:
        client.__exit__(None, None, None)


# --- Finding 1: the AWS variables are the server's own -------------------------------------


@pytest.mark.parametrize("name", ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                                  "AWS_SESSION_TOKEN", "AWS_BEARER_TOKEN_BEDROCK"])  # fmt: skip
def test_a_connector_or_standing_never_sends_the_aws_keys(name: str) -> None:
    assert connectors.server_variable(name)


# --- Finding 2: the day's limit holds against questions asked at once ----------------------


def test_questions_asked_at_once_wait_one_behind_the_other(
    instance: Instance, people: People, closing: list[TestClient]
) -> None:
    release = threading.Event()

    def slow(config: AssistantConfig, messages: list[dict[str, str]]) -> str:
        release.wait(10)
        return "Freezer Watch."

    as_role, opened = _assistant(instance, slow, daily_limit=5)
    closing.extend(opened)
    clients = [as_role("member") for _ in range(4)]
    codes: list[int] = []
    first = threading.Thread(target=lambda: codes.append(
        clients[0].post("/api/v1/assistant/ask", json=QUESTION).status_code))  # fmt: skip
    first.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:  # until the first is waiting on the server
        with instance.db.read() as session:
            if session.scalar(select(AssistantExchange.id)):
                break
        time.sleep(0.05)
    others = [client.post("/api/v1/assistant/ask", json=QUESTION) for client in clients[1:]]
    release.set()
    first.join(10)
    assert codes == [200]
    assert [answer.status_code for answer in others] == [429, 429, 429]
    assert "still answering" in others[0].json()["detail"]
    with instance.db.read() as session:
        assert len(list(session.scalars(select(AssistantExchange.id)))) == 1


# --- Finding 3: a page's kept scores are of one moment -------------------------------------


def test_a_score_kept_from_a_page_is_of_one_moment(db: Database, people: People) -> None:
    """On PostgreSQL a session that read each statement afresh could keep a score worked out
    from an application read before a change under the counter after it."""
    ref = add_app(db, people, name="One Moment")
    kept.forget()
    with db.read() as page:
        app = page.scalars(select(Application).where(Application.ref == ref)).one()
        with db.write(ME.actor) as other:
            row = other.scalars(select(Application).where(Application.ref == ref)).one()
            row.annual_cost, row.tier = 900_000, "1"
        assessment.score_all(page, [app])  # kept, from what the page saw
    with db.read() as later:
        app = later.scalars(select(Application).where(Application.ref == ref)).one()
        assessment.score_all(later, [app])  # under CHECK: a stale kept score would fail here
    kept.forget()


# --- Findings 4 and 7: a misbehaving server is answered within the time allowed -------------


def _server(reply: Callable[[socket.socket], None]) -> tuple[str, socket.socket]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def serve() -> None:
        with contextlib_suppress():
            conn, _ = listener.accept()
            conn.recv(65536)
            reply(conn)
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    return f"http://127.0.0.1:{listener.getsockname()[1]}/v1", listener


class contextlib_suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> bool:
        return True


def test_a_refusal_sent_a_byte_at_a_time_does_not_hold_the_request(tmp_path: Path) -> None:
    def trickle(conn: socket.socket) -> None:
        conn.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n"
                     b"Content-Length: 1000\r\n\r\n")  # fmt: skip
        for _ in range(40):
            conn.sendall(b" ")
            time.sleep(0.5)

    url, listener = _server(trickle)
    began = time.monotonic()
    with pytest.raises(AssistantError, match=r"refused the request \(400\)"):
        ask(AssistantConfig(url=url, model="m", timeout_seconds=1), ASKED, env={})
    listener.close()
    assert time.monotonic() - began < 7


def test_a_server_that_does_not_speak_http_is_a_failed_exchange() -> None:
    url, listener = _server(lambda conn: conn.sendall(b"NOT-HTTP garbage\r\n\r\n"))
    with pytest.raises(AssistantError, match="could not be reached"):
        ask(AssistantConfig(url=url, model="m", timeout_seconds=5), ASKED, env={})
    listener.close()


# --- Finding 5: old exchanges go whether or not the assistant is on ------------------------


def test_old_exchanges_go_when_the_assistant_is_off(instance: Instance) -> None:
    with instance.db.write(ME.actor) as session:
        old = utc_now() - timedelta(days=400)
        session.add(AssistantExchange(
            account_id=None, asked_by_name="Someone", purpose="question", model="m",
            prompt="What did we buy?", response="Things.", ok=True, created_at=old))  # fmt: skip
    off = replace(instance.config, assistant=AssistantConfig(keep_days=30))
    assert not off.assistant.enabled
    assert jobs._tidy(instance.db, off)["old_assistant_exchanges_removed"] == 1


# --- Finding 6: the server's own words are not told to the person, nor kept in the history --


def test_what_a_server_says_stays_with_the_exchange(
    instance: Instance, people: People, closing: list[TestClient]
) -> None:
    def refuses(config: AssistantConfig, messages: list[dict[str, str]]) -> str:
        raise AssistantError("The assistant's server refused the request (401).",
                             said="Incorrect API key provided: sk-abc1****wxyz.")  # fmt: skip

    as_role, opened = _assistant(instance, refuses)
    closing.extend(opened)
    answer = as_role("member").post("/api/v1/assistant/ask", json=QUESTION)
    assert answer.status_code == 200
    assert answer.json()["data"]["failed"] == "The assistant's server refused the request (401)."
    with instance.db.read() as session:
        row = session.scalars(select(AssistantExchange)).one()
        told = list(session.scalars(
            select(Event).where(Event.subject_type == "assistant_exchange")))  # fmt: skip
    assert "sk-abc1" in (row.error or "")  # for an administrator, in the exchanges
    assert all("error" not in event.changes for event in told)
    assert "sk-abc1" not in str([event.changes for event in told])


# --- Finding 8: the assistant's key is not one of the server's own secrets ------------------


@pytest.mark.parametrize("name", ["APPWREN_DATABASE_URL", "APPWREN_SSO_CLIENT_SECRET",
                                  "PGPASSWORD", "AWS_SECRET_ACCESS_KEY"])  # fmt: skip
def test_the_assistant_s_key_is_never_one_of_the_server_s_own(name: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        parse(f'[assistant]\nurl = "https://m.example.org/v1"\nmodel = "m"\nkey_env = "{name}"\n',
              tmp_path)  # fmt: skip
    assert any("one of the server's own secrets" in p for p in caught.value.problems)
    bedrock = parse('[assistant]\nprovider = "bedrock"\nregion = "us-east-1"\nmodel = "m"\n'
                    'key_env = "AWS_BEARER_TOKEN_BEDROCK"\n', tmp_path)  # fmt: skip
    assert bedrock.assistant.key_env == "AWS_BEARER_TOKEN_BEDROCK"


# --- Finding A: a restricted primary provider is not named in another's scores -------------


def test_a_restricted_primary_is_not_named_in_another_s_scores(
    as_role: Clients, db: Database, people: People
) -> None:
    second = add_app(db, people, name="Old Surveys", tier="4", users=20)
    with db.write(ME.actor) as session:
        hidden = records.create(session, ME, APPLICATION, {
            "name": "Secret Surveys", "org_unit_id": people.units["HALE"], "tier": "2",
            "users": 900, "restricted": True})  # fmt: skip
        primary = hidden.ref
        capability = records.create(session, ME, CAPABILITY, {"name": "Participant surveys"})
        for ref, is_primary in ((primary, True), (second, False)):
            app = records.load(session, ME, APPLICATION, ref)
            applications.set_capabilities(
                session, ME, app, [{"capability": capability.ref, "is_primary": is_primary}]
            )
    assess(db, people, primary, GOOD)
    assess(db, people, second, {**GOOD, "strategic_fit": 2})
    manager = as_role("manager").get(f"/api/v1/applications/{second}/scores").json()["data"]
    assert manager["overlap_with"]["ref"] == primary  # control: it does overlap
    member = as_role("member")
    assert member.get(f"/api/v1/applications/{primary}").status_code == 404
    shown = member.get(f"/api/v1/applications/{second}/scores").json()["data"]
    assert shown["overlap_with"] == assessment.UNSEEN_PEER
    assert "Secret Surveys" not in str(shown)


# --- Finding B: a scenario names only the flags the reader may be told of -------------------


def test_a_scenario_does_not_tell_a_contract_the_reader_may_not_see(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Payroll Plus", unit="CANCER", data_classes=["personal"])
    with db.write(ME.actor) as session:
        vendor = records.create(session, ME, VENDOR, {"name": "Payroll Vendor"})
        contract = records.create(session, ME, CONTRACT, {
            "name": "Payroll subscription", "vendor_id": vendor.ref,
            "ends_on": (date.today() + timedelta(days=60)).isoformat(), "notice_days": 30,
            "data_agreement": "missing", "annual_value": 90_000})  # fmt: skip
        costs.set_applications(session, ME, contract, [{"application": ref}])
    architect = as_role("architect")
    made = architect.post("/api/v1/scenarios", json={"name": "Without payroll"})
    scenario = made.json()["data"]["ref"]
    said = architect.put(f"/api/v1/scenarios/{scenario}/changes",
                         json={"changes": [{"application": ref, "action": "retire"}]})  # fmt: skip
    assert said.status_code == 200, said.text
    whole = as_role("manager").get(f"/api/v1/scenarios/{scenario}").json()["data"]["effect"]
    assert "no_data_agreement" in {f["key"] for f in whole["risk"]["flags"]}  # control
    risk = as_role("member").get(f"/api/v1/scenarios/{scenario}").json()["data"]["effect"]["risk"]
    assert not {"no_data_agreement", "contract_notice"} & {f["key"] for f in risk["flags"]}
