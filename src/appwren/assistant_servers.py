"""The three protocols the assistant can speak to its model server, over plain HTTP.

``[assistant] provider`` names the protocol, not a vendor, so any server that speaks one of
them serves:

- ``openai``: the chat completions interface, offered by the official service, by gateways,
  and by servers run on one's own machines (Ollama, vLLM, llama.cpp, LM Studio).
- ``anthropic``: the messages interface, offered by the official service, by Amazon Bedrock's
  ``bedrock-mantle`` endpoint, by gateways, and by Ollama.
- ``bedrock``: Amazon Bedrock's Converse API, with an Amazon Bedrock API key sent as a bearer
  token, or with access keys from the environment, each request signed (Signature Version 4).

The assistant asks one question and reads one whole answer: nothing is streamed, and the model
is given no tools. Every protocol takes the same messages (``system`` and ``user`` turns) and
gives back the answer's words. A redirect is never followed, since it would carry the key to
wherever it points, and keys come only from the environment.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlsplit

from appwren.config import AssistantConfig, split_header
from appwren.core import net
from appwren.core.errors import AppWrenError
from appwren.core.sigv4 import sign

MAX_BYTES = 2_000_000
DEFAULT_MAX_TOKENS = 16_000  # for the protocols that need a limit; thinking counts against it
ANTHROPIC_VERSION = "2023-06-01"
BEDROCK_TOKEN = "AWS_BEARER_TOKEN_BEDROCK"  # noqa: S105 (a variable's name)

Env = Mapping[str, str]
Messages = list[dict[str, str]]


class AssistantError(AppWrenError):
    """The assistant could not be asked, or did not answer usefully."""


@dataclass
class Call:
    """One request to the model server, and how to read its answer."""

    url: str
    body: dict[str, Any]
    read: Callable[[Any], str]
    headers: dict[str, str] = field(default_factory=dict)
    sign: Callable[[str, dict[str, str], bytes], dict[str, str]] | None = None


def ask(config: AssistantConfig, messages: Messages, env: Env | None = None) -> str:
    """One question to the configured server. Returns the answer's words."""
    env = os.environ if env is None else env
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [{"role": m["role"], "content": m["content"]} for m in messages
             if m["role"] != "system"]  # fmt: skip
    build = {"openai": _openai, "anthropic": _anthropic, "bedrock": _bedrock}.get(config.provider)
    if build is None:
        raise AssistantError(f"There is no provider called {config.provider!r}.")
    return _send(config, build(config, system, turns, env))


def _key(config: AssistantConfig, env: Env) -> str:
    return env.get(config.key_env, "").strip() if config.key_env else ""


def _cut_off() -> AssistantError:
    return AssistantError(
        "The answer was cut off at the longest allowed. Raise [assistant] max_tokens."
    )


# --- chat completions ---------------------------------------------------------------------------


def _openai(config: AssistantConfig, system: str, turns: Messages, env: Env) -> Call:
    body: dict[str, Any] = {
        "model": config.model,
        "messages": ([{"role": "system", "content": system}] if system else []) + turns,
    }
    if config.max_tokens:
        body["max_tokens"] = config.max_tokens
    if config.temperature is not None:
        body["temperature"] = config.temperature
    key = _key(config, env)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return Call(f"{config.endpoint}/chat/completions", body, _openai_words, headers)


def _openai_words(found: Any) -> str:
    choice = found["choices"][0]
    if choice.get("finish_reason") == "length":
        raise _cut_off()
    message = choice["message"]
    if message.get("refusal"):
        raise AssistantError("The model declined to answer.")
    return str(message.get("content") or "")


# --- messages -----------------------------------------------------------------------------------


def _anthropic(config: AssistantConfig, system: str, turns: Messages, env: Env) -> Call:
    body: dict[str, Any] = {
        "model": config.model,
        "max_tokens": config.max_tokens or DEFAULT_MAX_TOKENS,
        "messages": turns,
    }
    if system:
        body["system"] = system
    if config.temperature is not None:
        body["temperature"] = config.temperature
    headers = {"anthropic-version": ANTHROPIC_VERSION}
    key = _key(config, env)
    if key:
        headers["x-api-key"] = key
    return Call(f"{config.endpoint}/v1/messages", body, _anthropic_words, headers)


def _anthropic_words(found: Any) -> str:
    stop = found.get("stop_reason")
    if stop == "refusal":
        raise AssistantError("The model declined to answer.")
    if stop == "max_tokens":
        raise _cut_off()
    # Thinking, and anything else that is not words for the person, is passed over.
    return "".join(b.get("text", "") for b in found["content"] if b.get("type") == "text")


# --- Amazon Bedrock's Converse API --------------------------------------------------------------


def _bedrock(config: AssistantConfig, system: str, turns: Messages, env: Env) -> Call:
    body: dict[str, Any] = {
        "messages": [{"role": t["role"], "content": [{"text": t["content"]}]} for t in turns],
        "inferenceConfig": {"maxTokens": config.max_tokens or DEFAULT_MAX_TOKENS},
    }
    if system:
        body["system"] = [{"text": system}]
    if config.temperature is not None:
        body["inferenceConfig"]["temperature"] = config.temperature
    url = f"{config.endpoint}/model/{quote(config.model, safe='')}/converse"
    token = _key(config, env) or env.get(BEDROCK_TOKEN, "").strip()
    if token:
        return Call(url, body, _bedrock_words, {"Authorization": f"Bearer {token}"})
    access, secret = env.get("AWS_ACCESS_KEY_ID", ""), env.get("AWS_SECRET_ACCESS_KEY", "")
    if not (access and secret):
        raise AssistantError(
            f"Bedrock needs {BEDROCK_TOKEN} (an Amazon Bedrock API key), or "
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, in the server's environment."
        )

    def signed(to: str, headers: dict[str, str], data: bytes) -> dict[str, str]:
        given = {**headers, "host": urlsplit(to).netloc}
        return sign("POST", to, given, data, access_key=access, secret_key=secret,
                    session_token=env.get("AWS_SESSION_TOKEN") or None,
                    region=config.region, service="bedrock")  # fmt: skip

    return Call(url, body, _bedrock_words, sign=signed)


def _bedrock_words(found: Any) -> str:
    stop = found.get("stopReason")
    if stop in ("guardrail_intervened", "content_filtered"):
        raise AssistantError("The model declined to answer.")
    if stop == "max_tokens":
        raise _cut_off()
    content = found["output"]["message"]["content"]
    return "".join(part.get("text", "") for part in content if "text" in part)


# --- the request --------------------------------------------------------------------------------


def _send(config: AssistantConfig, call: Call) -> str:
    data = json.dumps(call.body).encode()
    # A gateway's own headers go with every request, and are signed with it on Bedrock.
    gateway = dict(split_header(header) for header in config.headers)
    headers = {"content-type": "application/json", "accept": "application/json",
               "user-agent": "AppWren", **gateway, **call.headers}  # fmt: skip
    if call.sign:
        headers = call.sign(call.url, headers, data)
    request = urllib.request.Request(call.url, data=data, headers=headers, method="POST")  # noqa: S310
    seconds = config.timeout_seconds

    def fetch() -> Any:
        with net.opener().open(request, timeout=seconds) as answer:
            return json.loads(net.read_within(answer, MAX_BYTES, seconds))

    try:
        found = net.within(seconds + 5, fetch)
    except urllib.error.HTTPError as error:
        said = _said(error)
        raise AssistantError(
            f"The assistant's server answered {error.code}" + (f": {said}" if said else ".")
        ) from error
    except (OSError, ValueError) as error:
        raise AssistantError("The assistant could not be reached.") from error
    try:
        return call.read(found)
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        said = "The assistant's server sent an answer AppWren could not read."
        raise AssistantError(said) from error


def _said(error: urllib.error.HTTPError) -> str:
    """What the server said was wrong, briefly, so an administrator can put it right."""
    try:
        found = json.loads(error.read(20_000) or b"{}")
    except (OSError, ValueError):
        return ""
    if not isinstance(found, dict):
        return ""
    problem = found.get("error", found)
    if isinstance(problem, dict):
        problem = problem.get("message") or problem.get("Message") or ""
    return " ".join(str(problem or "").split())[:200]


__all__ = ["AssistantError", "ask"]
