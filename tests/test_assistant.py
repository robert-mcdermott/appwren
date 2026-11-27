"""The optional assistant (slice 3 of wave 8): off and invisible until configured; drafts an
application from a document; answers with links; keeps every exchange."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from appwren.api.app import create_app
from appwren.config import AssistantConfig
from appwren.db.engine import Database
from tests.conftest import Instance
from tests.people import People, email_of, sign_in
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]
DOCUMENT = ("Freezer Watch alerts the labs when a freezer warms. It is a hosted service from "
            "a vendor, used by about 300 people, with single sign-on.")  # fmt: skip


class Model:
    """Stands in for the model server: remembers what it was asked, answers as told."""

    def __init__(self) -> None:
        self.asked: list[list[dict[str, str]]] = []
        self.answer = "{}"

    def __call__(self, config: AssistantConfig, messages: list[dict[str, str]]) -> str:
        self.asked.append(messages)
        return self.answer


@pytest.fixture
def helper(
    instance: Instance, people: People
) -> Iterator[tuple[Callable[[str], TestClient], Model]]:
    config = replace(instance.config, assistant=AssistantConfig(
        url="https://models.example.org/v1", model="small-model"))  # fmt: skip
    app = create_app(config)
    model = Model()
    app.state.assistant_ask = model
    clients: list[TestClient] = []

    def as_role(role: str) -> TestClient:
        client = TestClient(app, base_url="http://localhost")
        client.__enter__()
        clients.append(client)
        sign_in(client, email_of(role))
        return client

    yield as_role, model
    for client in clients:
        client.__exit__(None, None, None)


def test_off_and_invisible_until_configured(as_role: Clients) -> None:
    member = as_role("member")
    assert member.get("/api/v1/meta").json()["data"]["assistant"] is False
    assert member.post("/api/v1/assistant/ask", json={"question": "Which apps?"}).status_code == 404


def test_it_drafts_what_the_form_would_take(
    helper: tuple[Callable[[str], TestClient], Model],
) -> None:
    as_role, model = helper
    member = as_role("member")
    assert member.get("/api/v1/meta").json()["data"]["assistant"] is True
    model.answer = "Here it is: " + json.dumps({
        "name": "Freezer Watch", "sourcing": "saas", "users": 300, "sign_in": "sso",
        "tier": "nine", "data_classes": ["internal", "made_up"], "annual_cost": 5,
    })  # fmt: skip
    drafted = member.post("/api/v1/assistant/draft", json={"text": DOCUMENT})
    assert drafted.status_code == 200, drafted.text
    found = drafted.json()["data"]
    assert found["values"] == {"name": "Freezer Watch", "sourcing": "saas", "users": 300,
                               "sign_in": "sso", "data_classes": ["internal"]}  # fmt: skip
    assert "tier" in found["dropped"] and "annual_cost" in found["dropped"]
    assert "not instructions" in model.asked[0][0]["content"]
    model.answer = "I cannot help with that."
    assert (
        "failed" in member.post("/api/v1/assistant/draft", json={"text": DOCUMENT}).json()["data"]
    )
    assert member.post("/api/v1/assistant/draft", json={"text": "short"}).status_code == 422


def test_it_answers_from_what_the_person_may_see(
    helper: tuple[Callable[[str], TestClient], Model], db: Database, people: People
) -> None:
    as_role, model = helper
    shown = add_app(db, people, name="Freezer Watch", data_classes=["internal"])
    sensitive = add_app(db, people, name="Patient Portal", data_classes=["health"])
    secret = add_app(db, people, name="Hidden Ledger", restricted=True, unit="CANCER")
    member = as_role("member")
    model.answer = f"Freezer Watch [{shown}] does that. So might [{sensitive}] and [APP-9999]."
    said = member.post("/api/v1/assistant/ask", json={"question": "What watches freezers?"})
    assert said.status_code == 200, said.text
    answer = said.json()["data"]
    assert [item["ref"] for item in answer["records"]] == [shown]  # only what it was told of
    told = model.asked[-1][1]["content"]
    assert "Freezer Watch" in told and "Patient Portal" not in told and "Hidden Ledger" not in told
    assert secret
    # Every exchange is kept, for those who see everything.
    kept = as_role("auditor").get("/api/v1/assistant/exchanges").json()["data"]
    assert kept[0]["purpose"] == "question" and kept[0]["asked_by"] == "Member Person"
    assert "What watches freezers?" in kept[0]["prompt"]
    assert member.get("/api/v1/assistant/exchanges").status_code == 403


def test_a_sensitive_field_is_not_told_to_it(
    helper: tuple[Callable[[str], TestClient], Model], db: Database, people: People
) -> None:
    """Review of wave 8, finding B: what the program marks sensitive stays out of the prompt."""
    as_role, model = helper
    admin = as_role("admin")
    program = admin.get("/api/v1/program").json()["data"]
    marked = [*program["sensitive_fields"], "tier"]
    admin.put(
        "/api/v1/program/fields", json={"fields": program["fields"], "sensitive_fields": marked}
    )
    add_app(db, people, name="Freezer Watch", unit="CANCER", tier="1", data_classes=["internal"])
    model.answer = "Nothing to say."
    as_role("member").post("/api/v1/assistant/ask", json={"question": "Which are critical?"})
    told = model.asked[-1][1]["content"]
    assert "Freezer Watch" in told and "Mission critical" not in told
