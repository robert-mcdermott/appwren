"""Standings: how a record linked in another system of record stands there (INT-07).

An application links to its records elsewhere (an AI-use review, a risk register entry, a
security assessment) by external reference. Where the program gives that system a
``standing_url`` (an https address with ``{id}`` for the identifier, answering in JSON),
a scheduled job reads each linked record's standing and keeps it beside the link: approved,
open, closed, as that system says it. ``standing_field`` names where in the answer to look,
as a dotted path (``status`` by default), and ``key_env`` names an environment variable
holding a key, sent as a bearer token.

Nothing is read until the program names such an address. A change of standing is kept in
the record's history like any change; a failed read says why, and changes nothing else.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from sqlalchemy import select

from appwren.core import net
from appwren.core.clock import utc_now
from appwren.db.engine import Database
from appwren.db.models import ExternalRef
from appwren.events.actor import Actor
from appwren.program import vocab

TIMEOUT = 10
MAX_ANSWER = 200_000
BATCH = 500  # records read in one run; the rest wait for the next
READER = Actor.system("Standings")

# (url, headers) -> the parsed JSON answer
Fetch = Callable[[str, dict[str, str]], Any]


class StandingError(Exception):
    pass


def fetch_json(url: str, headers: dict[str, str]) -> Any:
    request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310

    def read() -> Any:
        # A redirect is not followed: it would carry the key to wherever it points.
        with net.opener().open(request, timeout=TIMEOUT) as answer:
            return json.loads(net.read_within(answer, MAX_ANSWER, TIMEOUT))

    try:
        return net.within(TIMEOUT + 5, read)
    except urllib.error.HTTPError as error:
        raise StandingError(f"The system answered {error.code}.") from error
    except (OSError, ValueError) as error:
        raise StandingError(
            "The system could not be reached, or did not answer in JSON."
        ) from error


def _pick(found: Any, path: str) -> str | None:
    for part in path.split("."):
        if not isinstance(found, dict) or part not in found:
            return None
        found = found[part]
    return None if found is None or isinstance(found, dict | list) else str(found)[:80]


def systems(db: Database) -> dict[str, dict[str, Any]]:
    """The systems the program gives a standing address."""
    from appwren import connectors

    with db.read() as session:
        listed = vocab.get(session, "external_systems")
    return {item["key"]: item for item in listed
            if str(item.get("standing_url") or "").startswith("https://")
            and "{id}" in str(item.get("standing_url"))
            and not connectors.server_variable(str(item.get("key_env") or ""))}  # fmt: skip


def run_once(db: Database, _config: Any = None, fetch: Fetch = fetch_json) -> dict[str, int]:
    """Read the standing of every linked record whose system offers one, oldest read first."""
    readable = systems(db)
    if not readable:
        return {"read": 0, "changed": 0, "failed": 0}
    with db.read() as session:
        rows = session.execute(
            select(ExternalRef.id, ExternalRef.system, ExternalRef.value)
            .where(ExternalRef.system.in_(list(readable)))
            .order_by(ExternalRef.standing_read_at.is_not(None), ExternalRef.standing_read_at)
            .limit(BATCH)
        ).all()
    counts = {"read": 0, "changed": 0, "failed": 0}
    for ref_id, system, value in rows:
        spec = readable[system]
        if not value.strip(". ") or not value.isprintable():
            # "." and ".." would climb the address's path, carrying the key elsewhere.
            with db.write(READER) as session:
                row = session.get(ExternalRef, ref_id)
                if row is not None:
                    row.standing_read_at = utc_now()
                    row.standing_error = "The identifier cannot be used in an address."
            counts["failed"] += 1
            continue
        url = str(spec["standing_url"]).replace("{id}", quote(value, safe=""))
        headers = {"Accept": "application/json", "User-Agent": "AppWren"}
        key = os.environ.get(str(spec.get("key_env") or ""), "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        standing, problem = None, None
        try:
            standing = _pick(fetch(url, headers), str(spec.get("standing_field") or "status"))
            if standing is None:
                problem = "The answer did not say a standing where the program looks for it."
        except StandingError as error:  # read with no session open
            problem = str(error)
        with db.write(READER) as session:
            row = session.get(ExternalRef, ref_id)
            if row is None:
                continue
            row.standing_read_at = utc_now()
            row.standing_error = problem[:200] if problem else None
            if problem is None:
                counts["read"] += 1
                if row.standing != standing:
                    row.standing = standing
                    counts["changed"] += 1
            else:
                counts["failed"] += 1
    return counts
