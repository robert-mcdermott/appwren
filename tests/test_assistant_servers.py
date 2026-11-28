"""The three protocols the assistant speaks to its model server, and their settings."""

from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from appwren import assistant_servers
from appwren.assistant_servers import AssistantError, ask
from appwren.config import AssistantConfig
from appwren.core.errors import ConfigError
from appwren.core.sigv4 import sign
from tests.test_config import parse

ASKED = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Which?"}]


class Server:
    """Stands in for the model server: keeps the request, answers as told."""

    def __init__(self) -> None:
        self.requests: list[Any] = []
        self.answer: Any = {}
        self.status = 200

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].data)

    def header(self, name: str) -> str | None:
        found = {k.lower(): v for k, v in self.requests[-1].header_items()}
        return found.get(name.lower())

    def open(self, request: Any, timeout: float) -> Any:
        self.requests.append(request)
        data = json.dumps(self.answer).encode()
        if self.status >= 400:
            raise urllib.error.HTTPError(request.full_url, self.status, "no", None,  # type: ignore[arg-type]
                                         io.BytesIO(data))  # fmt: skip
        return io.BytesIO(data)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[Server]:
    fake = Server()
    monkeypatch.setattr(assistant_servers.net, "opener", lambda: fake)
    yield fake


def test_chat_completions(server: Server) -> None:
    config = AssistantConfig(url="http://127.0.0.1:11434/v1/", model="small")
    server.answer = {"choices": [{"message": {"content": "That one."}, "finish_reason": "stop"}]}
    assert ask(config, ASKED, env={"APPWREN_ASSISTANT_KEY": "k1"}) == "That one."
    assert server.requests[-1].full_url == "http://127.0.0.1:11434/v1/chat/completions"
    assert server.header("Authorization") == "Bearer k1"
    assert server.body == {"model": "small", "messages": ASKED}  # no temperature, no limit
    ask(config, ASKED, env={})
    assert server.header("Authorization") is None  # no key, none sent: fine for one's own


def test_a_temperature_and_a_limit_are_sent_only_when_given(server: Server) -> None:
    server.answer = {"choices": [{"message": {"content": "x"}}]}
    config = AssistantConfig(url="https://m.example.org/v1", model="m", max_tokens=900,
                             temperature=0.2)  # fmt: skip
    ask(config, ASKED, env={})
    assert server.body["max_tokens"] == 900 and server.body["temperature"] == 0.2


def test_messages(server: Server) -> None:
    config = AssistantConfig(provider="anthropic", model="claude-opus-5-5")
    server.answer = {"stop_reason": "end_turn", "content": [
        {"type": "thinking", "thinking": ""}, {"type": "text", "text": "That "},
        {"type": "text", "text": "one."}]}  # fmt: skip
    assert config.enabled
    assert ask(config, ASKED, env={"APPWREN_ASSISTANT_KEY": "k2"}) == "That one."
    assert server.requests[-1].full_url == "https://api.anthropic.com/v1/messages"
    assert server.header("x-api-key") == "k2" and server.header("Authorization") is None
    assert server.header("anthropic-version") == "2023-06-01"
    assert server.body == {"model": "claude-opus-5-5", "max_tokens": 16_000, "system": "Be brief.",
                           "messages": [{"role": "user", "content": "Which?"}]}  # fmt: skip


def test_messages_at_another_address(server: Server) -> None:
    config = AssistantConfig(provider="anthropic", model="anthropic.claude-opus-5-5",
                             url="https://bedrock-mantle.us-east-1.api.aws/anthropic")  # fmt: skip
    server.answer = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Yes."}]}
    assert ask(config, ASKED, env={"APPWREN_ASSISTANT_KEY": "bedrock-key"}) == "Yes."
    assert server.requests[-1].full_url == (
        "https://bedrock-mantle.us-east-1.api.aws/anthropic/v1/messages"
    )


@pytest.mark.parametrize(("stop", "said"), [("refusal", "declined"), ("max_tokens", "cut off")])
def test_an_answer_that_is_refused_or_cut_off_says_so(server: Server, stop: str, said: str) -> None:
    config = AssistantConfig(provider="anthropic", model="m")
    server.answer = {"stop_reason": stop, "content": [{"type": "text", "text": '{"na'}]}
    with pytest.raises(AssistantError, match=said):
        ask(config, ASKED, env={})


def test_converse_with_a_bedrock_api_key(server: Server) -> None:
    config = AssistantConfig(provider="bedrock", region="us-west-2",
                             model="us.anthropic.claude-opus-5-5")  # fmt: skip
    server.answer = {"stopReason": "end_turn", "output": {"message": {"role": "assistant",
                     "content": [{"reasoningContent": {}}, {"text": "That one."}]}}}  # fmt: skip
    assert ask(config, ASKED, env={"AWS_BEARER_TOKEN_BEDROCK": "abk"}) == "That one."
    runtime = "https://bedrock-runtime.us-west-2.amazonaws.com"
    assert server.requests[-1].full_url == f"{runtime}/model/us.anthropic.claude-opus-5-5/converse"
    assert server.header("Authorization") == "Bearer abk"
    assert server.body == {
        "messages": [{"role": "user", "content": [{"text": "Which?"}]}],
        "system": [{"text": "Be brief."}], "inferenceConfig": {"maxTokens": 16_000},
    }  # fmt: skip


def test_converse_signed_with_access_keys(server: Server) -> None:
    config = AssistantConfig(provider="bedrock", region="eu-west-1",
                             model="arn:aws:bedrock:eu-west-1:1:inference-profile/x")  # fmt: skip
    server.answer = {"output": {"message": {"content": [{"text": "Signed."}]}}}
    env = {"AWS_ACCESS_KEY_ID": "AKIDEXAMPLE", "AWS_SECRET_ACCESS_KEY": "secret",
           "AWS_SESSION_TOKEN": "session"}  # fmt: skip
    assert ask(config, ASKED, env=env) == "Signed."
    assert "/model/arn%3Aaws%3Abedrock%3Aeu-west-1%3A1%3Ainference-profile%2Fx/converse" in (
        server.requests[-1].full_url
    )
    authorization = server.header("Authorization") or ""
    day = datetime.now(UTC).strftime("%Y%m%d")
    assert authorization.startswith(
        f"AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/{day}/eu-west-1/bedrock/aws4_request"
    )
    assert "host" in authorization and "x-amz-date" in authorization
    assert server.header("x-amz-security-token") == "session"
    assert server.header("Host") == "bedrock-runtime.eu-west-1.amazonaws.com"


def test_converse_without_credentials_says_what_to_set(server: Server) -> None:
    config = AssistantConfig(provider="bedrock", region="us-east-1", model="m")
    with pytest.raises(AssistantError, match="AWS_BEARER_TOKEN_BEDROCK"):
        ask(config, ASKED, env={})
    assert not server.requests


def test_a_refusal_from_the_server_says_what_it_said(server: Server) -> None:
    config = AssistantConfig(provider="anthropic", model="m")
    server.status = 400
    server.answer = {"type": "error", "error": {"type": "invalid_request_error",
                     "message": "temperature is not supported   for this model"}}  # fmt: skip
    with pytest.raises(AssistantError, match="answered 400: temperature is not supported for"):
        ask(config, ASKED, env={})


def test_an_unreadable_answer_is_explained(server: Server) -> None:
    server.answer = {"nothing": "here"}
    with pytest.raises(AssistantError, match="could not read"):
        ask(AssistantConfig(url="https://m.example.org/v1", model="m"), ASKED, env={})


@pytest.mark.parametrize(("method", "url", "signature"), [
    ("GET", "https://example.amazonaws.com/",
     "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"),
    ("POST", "https://example.amazonaws.com/",
     "5da7c1a2acd57cee7505fc6676e4e544621c30862966e37dddb68e92efbe5d6b"),
    ("GET", "https://example.amazonaws.com/?Param2=value2&Param1=value1",
     "b97d918cfa904a5beff61c982a1b6f458b799221646efd99d3219ec94cdf2500"),
])  # fmt: skip
def test_signature_version_4_matches_the_published_vectors(
    method: str, url: str, signature: str
) -> None:
    """get-vanilla, post-vanilla, and get-vanilla-query-order-key-case from AWS's test suite."""
    headers = sign(method, url, {"Host": "example.amazonaws.com"}, b"", access_key="AKIDEXAMPLE",
                   secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", region="us-east-1",
                   service="service", now=datetime(2015, 8, 30, 12, 36, tzinfo=UTC))  # fmt: skip
    assert headers["Authorization"].endswith(f"Signature={signature}")


# --- settings -----------------------------------------------------------------------------------


def test_the_settings_for_each_provider(tmp_path: Path) -> None:
    text = ('[assistant]\nprovider = "bedrock"\nregion = "us-east-1"\nmodel = "m"\n'
            "temperature = 1\nmax_tokens = 4000\ntimeout_seconds = 300\n")  # fmt: skip
    config = parse(text, tmp_path)
    helper = config.assistant
    assert helper.enabled and helper.temperature == 1.0 and helper.max_tokens == 4000
    assert helper.endpoint == "https://bedrock-runtime.us-east-1.amazonaws.com"
    assert parse('[assistant]\nprovider = "anthropic"\nmodel = "m"\n', tmp_path).assistant.enabled
    assert not parse("", tmp_path).assistant.enabled
    assert parse("", tmp_path).assistant.temperature is None


@pytest.mark.parametrize(("text", "problem"), [
    ('provider = "other"', "provider must be one of"),
    ('url = "https://m.example.org/v1"', "needs both url and model"),
    ('provider = "anthropic"', "needs a model"),
    ('provider = "bedrock"\nmodel = "m"', "region is needed"),
    ('url = "https://m.example.org"\nmodel = "m"\ntemperature = 3', "temperature must be"),
    ('url = "https://m.example.org"\nmodel = "m"\ntemperature = "low"', "must be a number"),
    ('url = "https://m.example.org"\nmodel = "m"\nmax_tokens = -1', "max_tokens must be"),
    ('url = "https://m.example.org"\nmodel = "m"\ntimeout_seconds = 1', "timeout_seconds must"),
    ('provider = "anthropic"\nmodel = "m"\nurl = "http://models.example.org"', "must start with"),
])  # fmt: skip
def test_settings_that_cannot_work_are_refused(text: str, problem: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        parse(f"[assistant]\n{text}\n", tmp_path)
    assert any(problem in line for line in caught.value.problems), caught.value.problems


def test_a_temperature_may_come_from_the_environment(tmp_path: Path) -> None:
    text = '[assistant]\nurl = "https://m.example.org/v1"\nmodel = "m"\ntemperature = 0.5\n'
    assert parse(text, tmp_path, env={"APPWREN_ASSISTANT_TEMPERATURE": "0.1"}
                 ).assistant.temperature == 0.1  # fmt: skip
    assert parse(text, tmp_path, env={"APPWREN_ASSISTANT_TEMPERATURE": ""}
                 ).assistant.temperature is None  # an empty variable unsets it  # fmt: skip
