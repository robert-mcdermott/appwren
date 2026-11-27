"""An optional tool server, so that an AI assistant can read AppWren and draft for a person.

It speaks the Model Context Protocol over standard input and output: an assistant's host
program starts ``appwren tools serve`` and asks it for tools. Each tool is one call to
AppWren's own API, made with the person's own token, so the assistant sees exactly what they
see (INT-05).

What it can do is deliberately short. It reads: search, a record, the applications, the
checkpoint, what is waiting on the person. And it drafts: it can propose a change to one
field of an application. It cannot change a record, decide anything, or accept its own
proposal. A proposal waits on the application until someone who keeps it accepts it.

Nothing here is needed to run AppWren, and nothing runs unless someone starts it.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import IO, Any

from appwren import __version__
from appwren.core import net

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

# (method, path, query, body) -> (status, parsed JSON or None)
Call = Callable[[str, str, dict[str, Any] | None, Any], tuple[int, Any]]


def http_caller(base: str, token: str) -> Call:
    """Calls a AppWren server over HTTP with a token."""

    def call(method: str, path: str, query: dict[str, Any] | None, body: Any) -> tuple[int, Any]:
        address = base.rstrip("/") + path
        if query:
            address += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v})
        request = urllib.request.Request(  # noqa: S310
            address,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            # A redirect is not followed: it would carry the token to wherever it points.
            with net.opener().open(request, timeout=20) as answer:
                return int(answer.status), json.load(answer)
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.load(error)
            except ValueError:
                return error.code, None

    return call


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


_REF = {"type": "string", "description": "An AppWren reference, such as APP-0042 or TEC-0007"}
TOOLS: list[dict[str, Any]] = [
    {
        "name": "search",
        "description": "Find records in AppWren by words or by reference: applications, "
        "components, technologies, vendors, capabilities, and the rest. Returns only what "
        "this person may see.",
        "inputSchema": _schema({"query": {"type": "string"}}, ["query"]),
    },
    {
        "name": "get_record",
        "description": "One record by its reference, with everything this person may see "
        "of it: for an application, its owner, stage, scores, decision, and more.",
        "inputSchema": _schema({"ref": _REF}, ["ref"]),
    },
    {
        "name": "list_applications",
        "description": "Applications, fifty at a time, narrowed by words if given.",
        "inputSchema": _schema({"query": {"type": "string"}}),
    },
    {
        "name": "check_application",
        "description": "Whether an application is approved for new use, and for a class of "
        "data if given, with every reason.",
        "inputSchema": _schema({"ref": _REF, "data_class": {"type": "string"}}, ["ref"]),
    },
    {
        "name": "my_work",
        "description": "What is waiting on this person: records to confirm, assessments, "
        "tasks, reviews, and more.",
        "inputSchema": _schema({}),
    },
    {
        "name": "suggest_change",
        "description": "Propose a value for one field of an application, with a note saying "
        "why. Nothing changes: someone who keeps the application accepts or dismisses it. "
        "Use get_record first to see the fields and their current values.",
        "inputSchema": _schema(
            {"ref": _REF, "field": {"type": "string"}, "value": {}, "note": {"type": "string"}},
            ["ref", "field", "value"],
        ),
    },
]


class ToolError(Exception):
    """Something to tell the assistant, in words it can pass on."""


def _data(answer: tuple[int, Any], missing: str = "There is no such record.") -> Any:
    status, body = answer
    if status == 404:
        raise ToolError(missing)
    if status in (401, 403):
        detail = (body or {}).get("detail") if isinstance(body, dict) else None
        raise ToolError(detail or "The token this server was started with may not do that.")
    if status == 422 and isinstance(body, dict):
        problems = "; ".join(
            f"{'.'.join(map(str, error.get('location', [])))}: {error.get('message')}"
            for error in body.get("errors", [])
        )
        raise ToolError(f"{body.get('detail') or 'That was not accepted.'} {problems}".strip())
    if status >= 400 or not isinstance(body, dict):
        raise ToolError(f"AppWren answered {status}.")
    return body.get("data")


def _path_of(ref: str) -> str:
    from appwren.inventory.registry import TYPES

    cleaned = ref.strip().upper()
    paths = {record_type.prefix: record_type.path for record_type in TYPES.values()}
    kind = paths.get(cleaned.split("-")[0])
    if kind is None:
        raise ToolError("That is not the reference of a record AppWren keeps.")
    return f"/api/v1/{kind}/{urllib.parse.quote(cleaned)}"


def run_tool(call: Call, name: str, arguments: dict[str, Any], base: str = "") -> Any:
    """Do one tool's work and return what the assistant is given."""
    if name == "search":
        return _data(call("GET", "/api/v1/search", {"q": str(arguments.get("query", ""))}, None))
    if name == "get_record":
        return _data(call("GET", _path_of(str(arguments.get("ref", ""))), None, None))
    if name == "list_applications":
        query = {"q": arguments.get("query"), "limit": 50}
        return _data(call("GET", "/api/v1/applications", query, None))
    if name == "check_application":
        ref = urllib.parse.quote(str(arguments.get("ref", "")).strip().upper())
        query = {"data_class": arguments.get("data_class")}
        return _data(call("GET", f"/api/v1/checkpoint/{ref}", query, None))
    if name == "my_work":
        return _data(call("GET", "/api/v1/home", None, None))
    if name == "suggest_change":
        ref = urllib.parse.quote(str(arguments.get("ref", "")).strip().upper())
        body = {"field": arguments.get("field"), "value": arguments.get("value"),
                "note": arguments.get("note")}  # fmt: skip
        made = _data(call("POST", f"/api/v1/applications/{ref}/suggestions", None, body))
        return {
            **made,
            "open": f"{base.rstrip('/')}/applications/{ref}" if base else "",
            "note": "This is a proposal. Nothing has changed. Someone who keeps the "
            "application accepts or dismisses it in AppWren.",
        }
    raise ToolError(f"There is no tool called {name}.")


def handle(call: Call, message: dict[str, Any], base: str = "") -> dict[str, Any] | None:
    """Answer one message of the protocol. A notification gets no answer."""
    method, identifier = message.get("method"), message.get("id")
    if identifier is None:
        return None

    def result(value: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": identifier, "result": value}

    if method == "initialize":
        asked = (message.get("params") or {}).get("protocolVersion")
        return result(
            {
                "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "appwren", "version": __version__},
                "instructions": "AppWren is this organization's record of the applications it "
                "runs: who answers for each, how each scores, and what was decided. You may "
                "read it and propose changes for the person. You cannot change, decide, or "
                "accept anything: people do that in AppWren.",
            }
        )
    if method == "ping":
        return result({})
    if method == "tools/list":
        return result({"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            value = run_tool(call, str(params.get("name")), params.get("arguments") or {}, base)
            text, failed = json.dumps(value, indent=1, ensure_ascii=False, default=str), False
        except ToolError as error:
            text, failed = str(error), True
        except (OSError, KeyError, TypeError, ValueError) as error:
            text, failed = f"AppWren could not be asked: {type(error).__name__}.", True
        return result({"content": [{"type": "text", "text": text}], "isError": failed})
    return {
        "jsonrpc": "2.0",
        "id": identifier,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def serve(
    call: Call, base: str = "", source: IO[str] = sys.stdin, sink: IO[str] = sys.stdout
) -> None:
    """Read one JSON message a line and write one answer a line, until the input ends."""
    for line in source:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            answer: dict[str, Any] | None = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        else:
            answer = handle(call, message, base) if isinstance(message, dict) else None
        if answer is not None:
            sink.write(json.dumps(answer, ensure_ascii=False) + "\n")
            sink.flush()
