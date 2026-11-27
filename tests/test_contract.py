"""The API's contract (INT-01, INT-02): what a release offers, the next keeps.

``docs/openapi.json`` records the API as it is, and a test keeps it current. This checks it
against the last release's: every route is still there with the same methods, and no request
asks for something it did not ask for before. A route may be added, and an answer may carry
more; nothing another system relies on goes away within 0.x without a changelog entry and
a new fixture here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RELEASED = sorted((ROOT / "tests" / "fixtures").glob("openapi-*.json"))[-1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _required(spec: dict[str, Any], operation: dict[str, Any]) -> set[str]:
    """The request fields and query parameters an operation insists on."""
    needed = {f"query:{p['name']}" for p in operation.get("parameters", []) if p.get("required")
              and p.get("in") == "query"}  # fmt: skip
    body = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    schema = body.get("schema", {})
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return needed | {f"body:{name}" for name in schema.get("required", [])}


def test_nothing_released_is_taken_away() -> None:
    before, now = _load(RELEASED), _load(ROOT / "docs" / "openapi.json")
    gone, stricter = [], []
    for path, methods in before["paths"].items():
        for method, operation in methods.items():
            current = now["paths"].get(path, {}).get(method)
            if current is None:
                gone.append(f"{method.upper()} {path}")
                continue
            added = _required(now, current) - _required(before, operation)
            if added:
                stricter.append(f"{method.upper()} {path} now needs {', '.join(sorted(added))}")
    assert not gone, f"Routes of {RELEASED.name} are gone: {gone}"
    assert not stricter, f"Requests ask for more than in {RELEASED.name}: {stricter}"
