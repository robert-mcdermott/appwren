"""The tool server: an assistant reads AppWren and proposes, and a person accepts."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from appwren import toolserver
from appwren.db.engine import Database
from tests.people import People
from tests.test_decisions import add_app

Clients = Callable[[str | None], TestClient]


def _caller(as_role: Clients, role: str) -> toolserver.Call:
    """The server's way to AppWren, through the app under test, with the person's token."""
    made = as_role(role).post("/api/v1/tokens", json={"name": "Assistant"})
    token = made.json()["data"]["token"]
    client = as_role(None)

    def call(method: str, path: str, query: dict[str, Any] | None, body: Any) -> tuple[int, Any]:
        client.cookies.clear()
        answer = client.request(
            method, path, params={k: v for k, v in (query or {}).items() if v},
            json=body, headers={"Authorization": f"Bearer {token}"},
        )  # fmt: skip
        try:
            return answer.status_code, answer.json()
        except ValueError:
            return answer.status_code, None

    return call


def _ask(call: toolserver.Call, name: str, **arguments: Any) -> tuple[Any, bool]:
    message = {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}  # fmt: skip
    answer = toolserver.handle(call, message, "https://apps.example.org")
    assert answer is not None and answer["id"] == 7
    result = answer["result"]
    text = result["content"][0]["text"]
    return (text if result["isError"] else json.loads(text)), result["isError"]


def test_the_protocol(as_role: Clients) -> None:
    call = _caller(as_role, "member")
    hello = toolserver.handle(call, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2025-03-26"}})  # fmt: skip
    assert hello is not None and hello["result"]["protocolVersion"] == "2025-03-26"
    assert hello["result"]["serverInfo"]["name"] == "appwren"
    assert (
        toolserver.handle(call, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    )
    listed = toolserver.handle(call, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    names = [tool["name"] for tool in listed["result"]["tools"]]  # type: ignore[index]
    assert names == ["search", "get_record", "list_applications", "check_application",
                     "my_work", "suggest_change"]  # fmt: skip
    # Nothing an assistant could use to change, decide, or accept.
    assert not any(word in " ".join(names) for word in ("update", "decide", "accept", "delete"))
    unknown = toolserver.handle(call, {"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
    assert unknown is not None and unknown["error"]["code"] == -32601
    source = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\n\nnot json\n')
    sink = io.StringIO()
    toolserver.serve(call, "", source, sink)
    lines = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert [line.get("result", line.get("error", {}).get("code")) for line in lines] == [{}, -32700]


def test_an_assistant_reads_as_its_person_and_proposes(
    as_role: Clients, db: Database, people: People
) -> None:
    ref = add_app(db, people, name="Sample Store", users=40)
    secret = add_app(db, people, name="Hidden Store", restricted=True, unit="CANCER")
    call = _caller(as_role, "member")
    found, failed = _ask(call, "search", query="Store")
    assert (
        not failed
        and "Sample Store" in json.dumps(found)
        and "Hidden Store" not in json.dumps(found)
    )
    record, failed = _ask(call, "get_record", ref=ref)
    assert not failed and record["users"] == 40
    hidden, failed = _ask(call, "get_record", ref=secret)
    assert failed and "no such record" in hidden.lower()
    checked, failed = _ask(call, "check_application", ref=ref, data_class="internal")
    assert not failed and checked["allowed"] is True
    proposal, failed = _ask(call, "suggest_change", ref=ref, field="users", value=95,
                            note="The sign-in log says so")  # fmt: skip
    assert (
        not failed and proposal["status"] == "pending" and "Nothing has changed" in proposal["note"]
    )
    assert proposal["open"] == f"https://apps.example.org/applications/{ref}"
    assert as_role("member").get(f"/api/v1/applications/{ref}").json()["data"]["users"] == 40
    _wrong, failed = _ask(call, "get_record", ref="NOPE-1")
    assert failed
