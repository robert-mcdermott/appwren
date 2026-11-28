"""The assistant, for paid models (slice 2 of wave 10): who may use it, how often, how long
what it was told is kept, headers for a gateway, and what `appwren doctor` says of it."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from appwren import assistant_servers, jobs
from appwren.api.app import create_app
from appwren.cli import doctor
from appwren.config import AssistantConfig
from appwren.core.clock import frozen_at, utc_now
from appwren.core.errors import ConfigError
from appwren.db.models import AssistantExchange, Event
from tests.conftest import Instance
from tests.people import People, email_of, sign_in
from tests.test_assistant_servers import ASKED, Server, server  # noqa: F401 (a fixture)
from tests.test_config import parse

QUESTION = {"question": "Which applications watch freezers?"}
Clients = Callable[[str], TestClient]


def _clients(instance: Instance, **settings: Any) -> Iterator[Clients]:
    config = replace(instance.config, assistant=AssistantConfig(
        url="https://models.example.org/v1", model="small-model", **settings))  # fmt: skip
    app = create_app(config)
    app.state.assistant_ask = lambda config, messages: "Freezer Watch [APP-0001]."
    opened: list[TestClient] = []

    def as_role(role: str) -> TestClient:
        client = TestClient(app, base_url="http://localhost")
        client.__enter__()
        opened.append(client)
        sign_in(client, email_of(role))
        return client

    yield as_role
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def limited(instance: Instance, people: People) -> Iterator[Clients]:
    yield from _clients(instance, daily_limit=2)


@pytest.fixture
def managers_only(instance: Instance, people: People) -> Iterator[Clients]:
    yield from _clients(instance, roles=("manager",))


def test_a_person_may_ask_only_so_often_in_a_day(limited: Clients) -> None:
    member = limited("member")
    for _ in range(2):
        assert member.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200
    refused = member.post("/api/v1/assistant/ask", json=QUESTION)
    assert refused.status_code == 429, refused.text
    assert "2 times today" in refused.json()["detail"]
    assert member.post("/api/v1/assistant/draft", json={"text": "x" * 60}).status_code == 429
    # The limit is each person's own.
    assert limited("steward").post("/api/v1/assistant/ask", json=QUESTION).status_code == 200


def test_the_count_starts_again_each_day(limited: Clients) -> None:
    member = limited("member")
    with frozen_at(utc_now() - timedelta(days=1)):
        for _ in range(2):
            assert member.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200
    assert member.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200


def test_the_roles_that_may_use_it(managers_only: Clients) -> None:
    member = managers_only("member")
    assert member.get("/api/v1/session").json()["data"]["assistant"] is False
    refused = member.post("/api/v1/assistant/ask", json=QUESTION)
    assert refused.status_code == 403, refused.text
    for role in ("manager", "admin"):  # administrators always may
        person = managers_only(role)
        assert person.get("/api/v1/session").json()["data"]["assistant"] is True
        assert person.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200


def test_everyone_may_use_it_unless_roles_are_named(limited: Clients, as_role: Any) -> None:
    assert limited("member").get("/api/v1/session").json()["data"]["assistant"] is True
    # With no assistant set up, nobody's session offers one.
    assert as_role("admin").get("/api/v1/session").json()["data"]["assistant"] is False


def test_old_exchanges_are_removed_and_the_history_kept(
    instance: Instance, limited: Clients
) -> None:
    member = limited("member")
    with frozen_at(utc_now() - timedelta(days=40)):
        assert member.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200
    assert member.post("/api/v1/assistant/ask", json=QUESTION).status_code == 200
    config = replace(instance.config, assistant=AssistantConfig(
        url="https://models.example.org/v1", model="m", keep_days=30))  # fmt: skip
    counts = jobs._tidy(instance.db, config)
    assert counts["old_assistant_exchanges_removed"] == 1
    with instance.db.read() as session:
        assert session.scalar(select(func.count(AssistantExchange.id))) == 1
        told = list(
            session.scalars(
                select(Event).where(Event.subject_type == "assistant_exchange").order_by(Event.id)
            )
        )
    assert [e.action for e in told] == ["created", "updated", "created", "updated", "deleted"]
    assert all(not {"prompt", "response", "error"} & set(e.changes) for e in told)
    kept_forever = replace(config, assistant=replace(config.assistant, keep_days=0))
    assert "old_assistant_exchanges_removed" not in jobs._tidy(instance.db, kept_forever)


def test_a_gateway_is_sent_its_headers(server: Server) -> None:  # noqa: F811
    config = AssistantConfig(url="https://gateway.example.org/v1", model="m",
                             headers=("X-Team: portfolio", "X-Route:  models-east"))  # fmt: skip
    server.answer = {"choices": [{"message": {"content": "ok"}}]}
    assistant_servers.ask(config, ASKED, env={})
    assert server.header("X-Team") == "portfolio" and server.header("X-Route") == "models-east"
    signed = AssistantConfig(provider="bedrock", region="us-east-1", model="m",
                             headers=("X-Team: portfolio",))  # fmt: skip
    server.answer = {"output": {"message": {"content": [{"text": "ok"}]}}}
    assistant_servers.ask(
        signed, ASKED, env={"AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "b"}
    )
    assert "x-team" in (server.header("Authorization") or "")  # signed with the request


@pytest.mark.parametrize(("text", "problem"), [
    ('headers = ["Authorization: Bearer abc"]', "may not be set here"),
    ('headers = ["X-Api-Token: abc"]', "may not be set here"),
    ('headers = ["no colon here"]', 'should be written "Name: value"'),
    ('roles = ["boss"]', "is not a role"),
    ("daily_limit = -1", "daily_limit must be"),
    ("keep_days = 5000", "keep_days must be"),
    ('headers = "X-Team: one"', "must be a list"),
])  # fmt: skip
def test_settings_for_paid_models_that_cannot_work(text: str, problem: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        parse(f'[assistant]\nurl = "https://m.example.org/v1"\nmodel = "m"\n{text}\n', tmp_path)
    assert any(problem in line for line in caught.value.problems), caught.value.problems


def test_lists_may_come_from_the_environment(tmp_path: Path) -> None:
    text = '[assistant]\nurl = "https://m.example.org/v1"\nmodel = "m"\n'
    env = {"APPWREN_ASSISTANT_ROLES": "manager, leader",
           "APPWREN_ASSISTANT_HEADERS": '["X-Team: a, b"]'}  # fmt: skip
    helper = parse(text, tmp_path, env=env).assistant
    assert helper.roles == ("manager", "leader") and helper.headers == ("X-Team: a, b",)
    defaults = parse(text, tmp_path).assistant
    assert defaults.daily_limit == 100 and defaults.keep_days == 365 and defaults.roles == ()


# --- appwren doctor ------------------------------------------------------------------------------


def _doctor(instance: Instance, monkeypatch: pytest.MonkeyPatch, text: str, *, ask: bool = False,
            env: dict[str, str] | None = None) -> doctor.Check:  # fmt: skip
    for name in ("APPWREN_ASSISTANT_KEY", "AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID",
                 "AWS_SECRET_ACCESS_KEY"):  # fmt: skip
        monkeypatch.delenv(name, raising=False)
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    with instance.path.open("a") as file:
        file.write(f"\n[assistant]\n{text}\n")
    checks = doctor.run(str(instance.path), ask_assistant=ask)
    return next(check for check in checks if check.name == "Assistant")


def test_doctor_says_nothing_of_an_assistant_not_set_up(instance: Instance) -> None:
    assert all(check.name != "Assistant" for check in doctor.run(str(instance.path)))


@pytest.mark.parametrize(("text", "env", "status", "said"), [
    ('provider = "bedrock"\nregion = "us-east-1"\nmodel = "m"', {}, "fail",
     "AWS_BEARER_TOKEN_BEDROCK"),
    ('provider = "bedrock"\nregion = "us-east-1"\nmodel = "m"',
     {"AWS_BEARER_TOKEN_BEDROCK": "t"}, "ok", "Amazon Bedrock API key"),
    ('provider = "anthropic"\nmodel = "m"', {}, "fail", "needs a key"),
    ('url = "http://127.0.0.1:11434/v1"\nmodel = "m"', {}, "ok", "no key, on this machine"),
    ('url = "https://m.example.org/v1"\nmodel = "m"', {}, "warn", "is not set"),
    ('url = "https://m.example.org/v1"\nmodel = "m"', {"APPWREN_ASSISTANT_KEY": "k"}, "ok",
     "the key in APPWREN_ASSISTANT_KEY"),
])  # fmt: skip
def test_doctor_says_what_the_provider_needs(
    instance: Instance, monkeypatch: pytest.MonkeyPatch, text: str, env: dict[str, str],
    status: str, said: str,
) -> None:  # fmt: skip
    check = _doctor(instance, monkeypatch, text, env=env)
    assert check.status == status and said in check.detail, check


def test_doctor_can_ask_the_server(
    instance: Instance,
    monkeypatch: pytest.MonkeyPatch,
    server: Server,  # noqa: F811
) -> None:
    server.answer = {"choices": [{"message": {"content": " Ready. "}}]}
    check = _doctor(instance, monkeypatch, 'url = "http://127.0.0.1:11434/v1"\nmodel = "m"',
                    ask=True)  # fmt: skip
    assert check.status == "ok" and "answered “Ready.”" in check.detail, check
    server.status = 401
    server.answer = {"error": {"message": "bad key"}}
    check = doctor._assistant(doctor.load_config(str(instance.path)), ask=True)
    assert check.status == "fail" and "refused the request (401). bad key" in check.detail, check
