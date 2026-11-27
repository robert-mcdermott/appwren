"""Connectors: small, read-only readers for named sources, each switched on by an
administrator (SIG-01, ADR-0003).

A fresh installation has none switched on and makes no connection. A connector an
administrator adds names its source (an address, an organization) and the environment
variable its credential is in; the credential is read when it runs and is never stored.

A run has two parts. First it reads, under a time limit and a size limit on each answer,
gathering what it found. Only if all of that succeeds does it write, in one transaction, each
value to its record with its source. A run that fails anywhere writes nothing, and says why.
Every run is recorded: what it read, what it changed, and what it could not match.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.connectors import sourced
from appwren.core.clock import utc_now
from appwren.core.errors import AppWrenError, Conflict, Invalid, NotFound, PermissionDenied
from appwren.db.engine import Database
from appwren.db.models import Connector, ConnectorRun
from appwren.events.actor import Actor

log = logging.getLogger("appwren.connectors")

TIMEOUT = 20.0  # seconds for each request
DEADLINE = timedelta(minutes=10)  # for a whole run
MOST_BYTES = 5_000_000  # in any one answer
KEEP_RUNS = 50  # of each connector
KEY = re.compile(r"[a-z][a-z0-9-]{1,39}")
ENV = re.compile(r"[A-Z][A-Z0-9_]{1,79}")
# Variables the server reads for itself. A connector sends its credential to the host an
# administrator names, so it may never be given one of these: that would send the server's
# own secrets wherever the address points.
SERVER_PREFIXES = ("APPWREN_SERVER_", "APPWREN_DATABASE_", "APPWREN_DATA_", "APPWREN_SSO_",
                   "APPWREN_MAIL_", "APPWREN_ADMIN_", "APPWREN_TEST_", "APPWREN_ASSISTANT_",
                   "PG")  # fmt: skip
SERVER_NAMES = {"APPWREN_CONFIG", "DATABASE_URL"}
RESERVED: set[str] = set()  # those the configuration names, added when the server starts


def reserve(*names: str) -> None:
    """Keep the variables the configuration names for its own secrets from any connector."""
    RESERVED.update(name for name in names if name)


def server_variable(name: str) -> bool:
    return name in SERVER_NAMES or name in RESERVED or name.startswith(SERVER_PREFIXES)


# The tests put a transport of their own here, so that no test reaches the network.
TRANSPORT: httpx.BaseTransport | None = None


class SourceError(AppWrenError):
    """The source could not be read as needed. The run writes nothing."""


@dataclass(frozen=True)
class Setting:
    name: str
    label: str
    hint: str = ""
    required: bool = True
    default: str = ""


@dataclass(frozen=True)
class Kind:
    """A kind of source, and how to read it."""

    key: str
    label: str
    describes: str
    access: str  # the least access its credential needs, in words
    settings: tuple[Setting, ...]
    credential: str | None  # the environment variable it suggests, or None if it needs none
    read: Callable[[Reading], None]
    check: Callable[[Reading], str]


KINDS: dict[str, Kind] = {}


def register(kind: Kind) -> Kind:
    KINDS[kind.key] = kind
    return kind


def _kinds() -> None:
    """Make sure every module that adds a kind has added it."""
    import appwren.connectors.kinds  # noqa: F401


@dataclass
class Reading:
    """One run's reading: its source's settings and credential, a way to ask the source, and
    what it found, kept until the run writes it."""

    connector: Connector
    kind: Kind
    settings: dict[str, Any]
    credential: str | None
    session: Session
    started: float = field(default_factory=time.monotonic)
    found: list[tuple[Any, sourced.Field, Any]] = field(default_factory=list)
    unmatched: list[dict[str, Any]] = field(default_factory=list)
    asked: int = 0
    extra: dict[str, Any] = field(default_factory=dict)
    # Steps that need the write's session, such as adding a release before its dates: each is
    # called with ``put(record, spec, value)`` once everything has been read.
    steps: list[Callable[[Session, Callable[[Any, sourced.Field, Any], None]], None]] = field(
        default_factory=list
    )

    def client(self, base_url: str = "", headers: dict[str, str] | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=base_url, headers={"User-Agent": "AppWren connector", **(headers or {})},
            timeout=TIMEOUT, follow_redirects=False, transport=TRANSPORT,
        )  # fmt: skip

    def get(
        self, client: httpx.Client, url: str, *, missing: tuple[int, ...] = (404,), **params: Any
    ) -> Any:
        """One answer from the source, as JSON, within the run's limits. An answer with a
        status in ``missing`` means there is nothing there, and gives None."""
        return self._ask(client, "GET", url, missing=missing, params=params or None)

    def post_form(self, client: httpx.Client, url: str, form: dict[str, str]) -> Any:
        """A form posted to the source, such as a request for a token. Nothing is changed
        there: a connector only reads."""
        return self._ask(client, "POST", url, missing=(), data=form)

    def _ask(
        self, client: httpx.Client, method: str, url: str, *, missing: tuple[int, ...],
        **sent: Any,
    ) -> Any:  # fmt: skip
        if time.monotonic() - self.started > DEADLINE.total_seconds():
            raise SourceError("the run took longer than its time limit")
        self.asked += 1
        try:
            with client.stream(method, url, **sent) as response:
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MOST_BYTES:
                        raise SourceError(f"an answer from {url} was larger than the limit")
                status = response.status_code
        except httpx.HTTPError as exc:
            raise SourceError(f"the source could not be reached: {type(exc).__name__}") from exc
        if status in missing:
            return None
        if status in (401, 403):
            raise SourceError(f"the source refused the credential ({status}) for {url}")
        if status >= 400:
            raise SourceError(f"the source answered {status} for {url}")
        try:
            return json.loads(body or b"null")
        except ValueError as exc:
            raise SourceError(f"the source's answer for {url} was not JSON") from exc

    def keep(self, record: Any, spec: sourced.Field, value: Any) -> None:
        """Something read, to be written if the run succeeds."""
        try:
            sourced.clean(spec, value)
        except ValueError as exc:
            self.miss(f"{spec.label} for {_called(record)}", str(exc))
            return
        self.found.append((record, spec, value))

    def miss(self, what: str, why: str) -> None:
        if len(self.unmatched) < 500:
            self.unmatched.append({"what": what[:200], "why": why[:200]})


def _called(record: Any) -> str:
    return str(getattr(record, "ref", None) or getattr(record, "name", None)
               or getattr(record, "cycle", None) or record.id)  # fmt: skip


# --- Setting them up ------------------------------------------------------------------------


def _require(principal: Principal) -> None:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator sets up connectors.")


def _clean(kind: Kind, values: dict[str, Any], *, current: Connector | None) -> dict[str, Any]:
    errors: dict[str, str] = {}
    out: dict[str, Any] = {}
    name = " ".join(str(values.get("name", current.name if current else "") or "").split())
    if not name:
        errors["name"] = "Give the connector a name."
    out["name"] = name[:120]
    settings = dict(current.settings) if current else {}
    given = values.get("settings") or {}
    for spec in kind.settings:
        if spec.name in given:
            settings[spec.name] = str(given[spec.name] or "").strip()[:300]
        settings.setdefault(spec.name, spec.default)
        if spec.required and not settings[spec.name]:
            errors[f"settings.{spec.name}"] = f"Give the {spec.label.lower()}."
        value = settings[spec.name]
        if value and spec.name.endswith("url") and not value.startswith("https://"):
            errors[f"settings.{spec.name}"] = "Start the address with https://"
    out["settings"] = settings
    if kind.credential is not None:
        env = str(values.get("credential_env", current.credential_env if current else "")
                  or kind.credential).strip()  # fmt: skip
        if not ENV.fullmatch(env):
            errors["credential_env"] = (
                "Name the environment variable that holds the credential, such as "
                f"{kind.credential}. The credential itself is never given here."
            )
        elif server_variable(env):
            errors["credential_env"] = (
                f"{env} holds one of the server's own settings or secrets, and is never sent "
                f"to a source. Give the connector a variable of its own, such as {kind.credential}."
            )
        out["credential_env"] = env
    every = values.get("every_hours", current.every_hours if current else 24)
    try:
        every = int(every)
    except (TypeError, ValueError):
        every = 0
    if not 1 <= every <= 24 * 7:
        errors["every_hours"] = "Run it every 1 to 168 hours."
    out["every_hours"] = every
    if errors:
        raise Invalid("The connector was not saved.", errors)
    return out


def add(session: Session, principal: Principal, values: dict[str, Any]) -> Connector:
    """A connector for a named source. It is off until switched on."""
    _require(principal)
    _kinds()
    kind = KINDS.get(str(values.get("kind") or ""))
    if kind is None:
        raise Invalid("The connector was not added.", {"kind": "Choose a kind of source."})
    key = str(values.get("key") or "").strip().lower()
    if not KEY.fullmatch(key):
        raise Invalid(
            "The connector was not added.",
            {"key": "A short key of lower-case letters, digits, and dashes."},
        )
    if session.scalars(select(Connector.id).where(Connector.key == key)).first():
        raise Conflict(f"There is already a connector {key}.")
    clean = _clean(kind, values, current=None)
    row = Connector(key=key, kind=kind.key, enabled=False, created_at=utc_now(), **clean)
    session.add(row)
    session.flush()
    return row


def change(
    session: Session, principal: Principal, row: Connector, values: dict[str, Any]
) -> Connector:
    _require(principal)
    _kinds()
    clean = _clean(KINDS[row.kind], values, current=row)
    for name, value in clean.items():
        setattr(row, name, value)
    if "enabled" in values:
        on = bool(values["enabled"])
        if on and not row.enabled:
            row.next_run_at = utc_now()  # first run as soon as the scheduler next looks
        row.enabled = on
    session.flush()
    return row


def load(session: Session, key: str) -> Connector:
    row = session.scalars(select(Connector).where(Connector.key == key)).first()
    if row is None:
        raise NotFound(f"There is no connector {key}.")
    return row


# --- Running them -----------------------------------------------------------------------------


def _reading(session: Session, row: Connector) -> Reading:
    _kinds()
    kind = KINDS.get(row.kind)
    if kind is None:
        raise SourceError(f"AppWren has no connector of the kind {row.kind}")
    credential = None
    if kind.credential is not None:
        if server_variable(row.credential_env or ""):
            raise SourceError(f"{row.credential_env} is one of the server's own variables")
        credential = os.environ.get(row.credential_env or "", "")
        if not credential:
            raise SourceError(f"the environment variable {row.credential_env} is not set")
    return Reading(row, kind, dict(row.settings or {}), credential, session)


def check(session: Session, principal: Principal, row: Connector) -> str:
    """Whether the source answers with this credential. Nothing is written."""
    _require(principal)
    try:
        reading = _reading(session, row)
        return reading.kind.check(reading)
    except SourceError as exc:
        raise Invalid("The source could not be reached.", {"source": str(exc)}) from exc


def run(db: Database, key: str) -> dict[str, Any]:
    """Read the source, then write what was read, in one transaction. A run that fails
    writes nothing. Either way the run is recorded."""
    started_at = utc_now()
    with db.read() as session:
        row = load(session, key)
        connector_id, name = row.id, row.name
    counts = {"asked": 0, "read": 0, "changed": 0, "unchanged": 0, "kept": 0, "unmatched": 0}
    unmatched: list[dict[str, Any]] = []
    error: str | None = None
    actor = Actor.system(f"Connector: {name}")
    try:
        # Reading takes as long as the source does, so it holds no lock on the database.
        with db.read() as session:
            reading = _reading(session, load(session, key))
            reading.kind.read(reading)  # raises before anything is written
            found = [(type(record), record.id, spec, value)
                     for record, spec, value in reading.found]  # fmt: skip
        counts["asked"] = reading.asked
        unmatched = reading.unmatched
        with db.write(actor, action="connector.run", context={"connector": key}) as session:

            def put(record: Any, spec: sourced.Field, value: Any) -> None:
                outcome = sourced.write(
                    session, source=key, source_name=name, record=record, spec=spec, value=value,
                    read_at=started_at,
                )  # fmt: skip
                counts["read"] += 1
                counts[outcome] += 1

            for model, record_id, spec, value in found:
                record = session.get(model, record_id)
                if record is not None:  # removed while the source was being read
                    put(record, spec, value)
            for step in reading.steps:
                step(session, put)
        if "discovered" in reading.extra:
            counts["discovered"] = int(reading.extra["discovered"])
        counts["unmatched"] = len(unmatched)
    except (SourceError, Invalid, NotFound) as exc:
        error = str(exc)[:600]
    except Exception as exc:  # a connector must never take the scheduler down
        log.exception("connector %s failed", key)
        error = f"{type(exc).__name__}: {exc}"[:600]
    finished = utc_now()
    status = "failed" if error else "ok"
    summary = error or _words(counts)
    run_row = ConnectorRun
    # The run's own record is not history: its fields on the connector are left out of it.
    with db.write(actor) as session:
        session.add(
            run_row(
                connector_id=connector_id, started_at=started_at, finished_at=finished,
                status=status, counts=counts if not error else {}, unmatched=unmatched[:500],
                error=error,
            )
        )  # fmt: skip
        row = session.get(Connector, connector_id)
        assert row is not None
        row.last_run_at, row.last_status, row.last_summary = finished, status, summary[:300]
        row.next_run_at = started_at + timedelta(hours=row.every_hours)
        old = session.scalars(
            select(run_row.id).where(run_row.connector_id == connector_id)
            .order_by(run_row.id.desc())
            .offset(KEEP_RUNS)
        ).all()  # fmt: skip
        for run_id in old:
            session.delete(session.get(run_row, run_id))
    return {"key": key, "status": status, "counts": counts, "error": error, "summary": summary,
            "unmatched": unmatched[:50]}  # fmt: skip


def _words(counts: dict[str, int]) -> str:
    said = (
        f"Read {counts['read']} values; {counts['changed']} changed, {counts['unchanged']} the "
        f"same, {counts['kept']} kept by a person's override; {counts['unmatched']} not matched"
    )
    if counts.get("discovered"):
        said += f"; {counts['discovered']} newly found that are not on record"
    return said


def run_due(db: Database) -> dict[str, int]:
    """Run every connector that is switched on and due. For the scheduler."""
    now = utc_now()
    with db.read() as session:
        due = [
            row.key
            for row in session.scalars(select(Connector).where(Connector.enabled.is_(True)))
            if row.next_run_at is None or row.next_run_at <= now
        ]
    done = {"connectors_run": 0, "connectors_failed": 0}
    for key in due:
        result = run(db, key)
        done["connectors_run" if result["status"] == "ok" else "connectors_failed"] += 1
    return done


# --- Reading them back ------------------------------------------------------------------------


def view(session: Session, row: Connector, *, runs: int = 10) -> dict[str, Any]:
    _kinds()
    kind = KINDS.get(row.kind)
    recent = session.scalars(
        select(ConnectorRun).where(ConnectorRun.connector_id == row.id)
        .order_by(ConnectorRun.id.desc()).limit(runs)
    ).all()  # fmt: skip
    return {
        "key": row.key,
        "kind": row.kind,
        "kind_label": kind.label if kind else row.kind,
        "name": row.name,
        "enabled": row.enabled,
        "settings": row.settings,
        "credential_env": row.credential_env,
        "credential_set": bool(row.credential_env and os.environ.get(row.credential_env)),
        "every_hours": row.every_hours,
        "next_run_at": row.next_run_at if row.enabled else None,
        "last_run_at": row.last_run_at,
        "last_status": row.last_status,
        "last_summary": row.last_summary,
        "runs": [
            {"started_at": item.started_at, "finished_at": item.finished_at,
             "status": item.status, "counts": item.counts, "unmatched": item.unmatched[:100],
             "error": item.error}
            for item in recent
        ],
    }  # fmt: skip


def kinds_view() -> list[dict[str, Any]]:
    _kinds()
    return [
        {"key": kind.key, "label": kind.label, "describes": kind.describes,
         "access": kind.access, "credential": kind.credential,
         "settings": [{"name": s.name, "label": s.label, "hint": s.hint,
                       "required": s.required, "default": s.default} for s in kind.settings]}
        for kind in KINDS.values()
    ]  # fmt: skip


def listing(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(Connector).order_by(Connector.name))
    return [view(session, row) for row in rows]


def last_runs(session: Session) -> dict[str, datetime | None]:
    return {row.key: row.last_run_at for row in session.scalars(select(Connector))}
