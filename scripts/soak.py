#!/usr/bin/env python3
"""Keep a real server busy for a while, as many people at once would, and watch it hold up.

Builds the large installation scripts/perf.py measures (the demo organization, its
applications copied until there are 5,000 and its components until there are 50,000) in a
temporary directory, and starts the real server on it with `appwren serve`, its scheduler
on as in production. Then many simulated people use it at once, each signed in as a
different person of the demo, across roles. They arrive over the first minute, and each
reads a page for about ten seconds before the next (--think): the home page, the list of
applications with its filters, sorting, and pages, an application's page and the tabs
behind it, the dashboard, search, and the reports. Now and then one makes a change that
goes into the history: an application's summary edited, its record confirmed, a change
proposed. About one request in twenty is a change. Each page sends the requests the web app
sends for it, at once, as the browser does.

It times every request and samples the memory of the server's processes (the server and
every process under it) every five seconds. At the end it stops the server as Ctrl-C would,
checks with `appwren verify` that the history still holds, and prints a report: requests
and failures, the 50th, 95th, and 99th percentiles of each kind of request, throughput, the
same minute by minute, how memory went, and how the scheduled work fared.

    uv run python scripts/soak.py                           20 people for 10 minutes
    uv run python scripts/soak.py --minutes 2               a short run
    uv run python scripts/soak.py --people 40 --workers 4 --minutes 30
    uv run python scripts/soak.py --no-scheduler            the same, the scheduler off
    APPWREN_DATABASE_URL=postgresql+psycopg://... uv run --extra postgres python scripts/soak.py

The PostgreSQL database must be empty, as for scripts/perf.py.

The demo offers eight of its people for signing in. So that each simulated person is someone
different, the soak offers more of them in its throwaway copy: stewards, people named on
applications, leaders, architects, and people with no role. With more simulated people than
the demo has, some share an account, each with a session of their own.

It exits with 1 if any of these is so:

- A request failed: an answer of 500 or more, no answer at all (the connection refused or
  broken, or a minute without an answer), or a refusal (400 to 499) of a request that should
  have been accepted. Only three refusals are expected, and they are counted, not failed:
  401 when the web app asks who is signed in before anyone is, 409 when a summary is saved
  over a version someone else changed first, and 422 when a change is proposed to an
  application that holds as many waiting proposals as it may.
- The 95th percentile of a kind of request is over the budget (--budget, 5,000 ms). A kind
  made fewer than 20 times is shown but not judged.
- Memory kept growing through the second half of the run. The samples of the second half
  are split into quarters, and memory is taken to be leaking when the median of each
  quarter is above the median of the one before, and the last quarter's is above the
  first's by more than --leak-mb (32 MB) and more than 5 percent. The first half is left
  out because a server's memory grows while it warms up, as caches fill and connections
  open. A process may also keep the memory it needed at its busiest, so memory steps up when
  more requests than ever before are under way at once, and can stay up; growth in every
  quarter is what tells a leak from such a step, and medians let a single spike pass. A
  run with fewer than eight samples in its second half is too short to judge.
- The server logged an error, a scheduled job failed, the server stopped by itself or did
  not stop within 30 seconds of being asked, or the history does not verify.

The server and the temporary directory are always removed, on Ctrl-C too.

Development use only: it makes a throwaway installation in a temporary directory.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import itertools
import math
import os
import random
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, text

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent
HELD_PORTS = {8000, 8010, 8020, 8030}  # left for the servers people start by hand
CACHE_SECONDS = 20  # how long the web app reuses an answer it may keep (core/api.js)
RAMP_SECONDS = 60  # the people arrive over this long, or a tenth of the run if that is less
SAMPLE_SECONDS = 5
TIMEOUT_SECONDS = 60
READY_SECONDS = 120
STOP_SECONDS = 30
CLEAN_EXITS = {0, 128 + signal.SIGINT, -signal.SIGINT}  # uvicorn exits as Ctrl-C ended it
JUDGED = 20  # a kind of request made fewer times than this is shown, not judged
LEAK_SHARE = 0.05
EXCEPTION = re.compile(r"[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt): ")  # a raised line
REVIEWED = "Reviewed."
WORDS = (
    "lab", "imaging", "clinical", "research", "data", "portal", "grant", "analysis",
    "finance", "sample", "records", "tracker", "student", "copy 7",
)  # fmt: skip

# What many pages ask for and the web app keeps a while (core/lookups.js): name -> kind, path
LOOKUPS = {
    "vocabularies": ("Vocabularies", "/api/v1/vocabularies"),
    "units": ("Units", "/api/v1/units"),
    "catalog": ("Catalog", "/api/v1/catalog"),
    "questionnaire": ("Questionnaire", "/api/v1/questionnaire"),
    "scoring-model": ("Scoring model", "/api/v1/scoring-model"),
    "accounts": ("Accounts", "/api/v1/accounts"),
}
# Where people go, and how often, by weight
PAGES = {
    "home": 10, "applications": 22, "application": 24, "dashboard": 8, "search": 12,
    "report": 16, "tasks": 6, "again": 1,
}  # fmt: skip
# An application's tabs after the first look, by weight (pages/record.js)
TABS = {
    "scores": 14, "assessment": 8, "decisions": 7, "components": 10, "capabilities": 6,
    "connections": 8, "cost": 6, "retirement": 4, "history": 10,
}  # fmt: skip
SORTS = ("name", "-name", "lifecycle", "-lifecycle", "tier", "-tier", "sourcing", "-updated_at")
FILTERS = ("lifecycle", "sourcing", "tier", "domain", "unit", "maturity")
# The report pages anyone may open: kind, path, parameters, what else the page asks for
REPORTS: tuple[tuple[str, str, dict[str, Any] | None, tuple[str, ...]], ...] = (
    ("Capability map", "/api/v1/capability-heat", None, ()),
    ("Overlap", "/api/v1/overlap", None, ("vocabularies", "units")),
    ("Lifecycle", "/api/v1/lifecycle", None, ("vocabularies",)),
    ("Technology radar", "/api/v1/radar", None, ("vocabularies",)),
    ("Roadmap", "/api/v1/roadmap", None, ("vocabularies", "units")),
    ("Portfolio chart", "/api/v1/portfolio", None, ("scoring-model", "vocabularies", "units")),
    ("Decisions", "/api/v1/portfolio", {"decided": "true"}, ("vocabularies",)),
    ("Shares of the portfolio", "/api/v1/shares", None, ()),
    ("Data quality", "/api/v1/data-quality", None, ("units",)),
    ("Data handling", "/api/v1/data-handling", None, ("vocabularies",)),
    ("Engineering maturity", "/api/v1/maturity", None, ()),
    ("Retirements", "/api/v1/retirements", None, ()),
)


def _perf() -> Any:
    """scripts/perf.py, which builds the large installation."""
    spec = importlib.util.spec_from_file_location("appwren_perf", HERE / "perf.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data(answer: httpx.Response | None) -> Any:
    """What an answer carries, or None if there was no good answer."""
    return None if answer is None else answer.json().get("data")


def percentile(ordered: list[float], share: float) -> float:
    """The nearest-rank percentile of values already in order."""
    if not ordered:
        return 0.0
    return ordered[max(0, min(len(ordered) - 1, math.ceil(share / 100 * len(ordered)) - 1))]


# --- What happened ---------------------------------------------------------------------------


@dataclass
class Done:
    kind: str
    ms: float
    at: float  # seconds into the load
    failed: bool


@dataclass
class Sample:
    at: float  # seconds into the load
    rss_kb: int
    processes: int
    cpu: float  # percent of one core, summed over the processes


@dataclass
class Tally:
    """Every request the simulated people made, and what came of it."""

    began: float = 0.0
    ended: float = 0.0
    done: list[Done] = field(default_factory=list)
    failures: list[tuple[float, str, str]] = field(default_factory=list)  # when, what, said
    expected: Counter[str] = field(default_factory=Counter)
    changes: int = 0

    def now(self) -> float:
        return time.perf_counter() - self.began

    def note(self, kind: str, ms: float, *, failure: tuple[str, str] | None = None) -> None:
        """Note a request. A failure is what failed, in words that group alike failures
        together, and an example of what was said."""
        self.done.append(Done(kind, ms, self.now(), failure is not None))
        if failure is not None:
            self.failures.append((self.now(), *failure))


# --- One simulated person -------------------------------------------------------------------


class Person:
    """One simulated person: a browser of their own, signed in as someone of the demo."""

    def __init__(
        self, account: dict[str, Any], base: str, tally: Tally, rng: random.Random,
        think: float, share: float,
    ) -> None:  # fmt: skip
        self.account = account
        self.base = base
        self.tally = tally
        self.rng = rng
        self.think = think
        self.share = share  # of all requests, the part that should be changes
        self.client: httpx.AsyncClient | None = None
        self.csrf = ""
        self.permissions: dict[str, bool] = {}
        self.roles: list[str] = []
        self.known: dict[str, Any] = {}  # the last answer to each lookup
        self.kept: dict[str, float] = {}  # when each was last asked for
        self.seen: dict[str, None] = {}  # every application met, in order
        self.shown: list[str] = []  # those on the list last shown
        self.editable: set[str] = set()
        self.confirmable: set[str] = set()
        self.words: dict[str, None] = dict.fromkeys(WORDS)

    # How it asks

    async def call(
        self, kind: str, method: str, path: str, *, params: dict[str, Any] | None = None,
        body: Any = None, expected: dict[int, str] | None = None,
    ) -> httpx.Response | None:  # fmt: skip
        """Make one request and note it. Returns the answer if it was a success. A refusal
        in ``expected`` (a status, and words its detail must hold) is right, not a failure."""
        assert self.client is not None
        headers = {}
        if method != "GET":  # as a browser sends a change from AppWren's own page
            headers = {"Origin": self.base, "Sec-Fetch-Site": "same-origin"}
            if self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        began = time.perf_counter()
        try:
            answer = await self.client.request(
                method, path, params=params, json=body, headers=headers
            )
        except httpx.HTTPError as exc:
            ms = (time.perf_counter() - began) * 1000
            what = f"{kind}: no answer ({type(exc).__name__})"
            said = f"{method} {path} as {self.account['key']}: no answer after {ms:,.0f} ms"
            self.tally.note(kind, ms, failure=(what, said))
            return None
        ms = (time.perf_counter() - began) * 1000
        if answer.is_success:
            self.tally.note(kind, ms)
            return answer
        words = (expected or {}).get(answer.status_code)
        if words is not None and words in answer.text:
            self.tally.note(kind, ms)
            self.tally.expected[f"{answer.status_code} from {kind}"] += 1
            return None
        where = answer.request.url.raw_path.decode()
        said = f"{method} {where} as {self.account['key']}: {answer.text[:300]}"
        self.tally.note(kind, ms, failure=(f"{kind}: {answer.status_code}", said))
        return None

    def get(
        self, kind: str, path: str, params: dict[str, Any] | None = None
    ) -> Awaitable[httpx.Response | None]:
        return self.call(kind, "GET", path, params=params)

    async def lookup(self, name: str) -> Any:
        """Something many pages need, asked for again only once the web app's copy is old."""
        if time.monotonic() - self.kept.get(name, -math.inf) < CACHE_SECONDS:
            return self.known.get(name)
        kind, path = LOOKUPS[name]
        found = data(await self.get(kind, path))
        if found is not None:
            self.known[name], self.kept[name] = found, time.monotonic()
        return found

    async def page(self, *calls: Awaitable[Any]) -> list[Any]:
        """Open a page: its requests at once, and the count of unread notices beside the
        bell, which the web app asks for on every page."""
        bell = self.get("Unread notices", "/api/v1/notices/count")
        *found, _ = await asyncio.gather(*calls, bell)
        return found

    async def wait(self) -> None:
        await asyncio.sleep(self.pause())

    def pause(self, left: float = math.inf) -> float:
        """How long a person reads before the next step: about --think seconds on average,
        often less, now and then up to four times as long."""
        return max(0.0, min(self.rng.expovariate(1 / self.think), 4 * self.think, left))

    # What it remembers

    def learn(self, rows: Iterable[dict[str, Any]]) -> list[str]:
        """Remember the applications among these rows, and words from their names."""
        refs = []
        for row in rows:
            if row.get("type", "application") != "application" or not row.get("ref"):
                continue
            refs.append(row["ref"])
            self.seen[row["ref"]] = None
            for word in str(row.get("name", "")).lower().split():
                if len(word) > 3 and word.isalpha() and len(self.words) < 200:
                    self.words[word] = None
        return refs

    def found(self, result: dict[str, Any] | None) -> list[str]:
        groups = (result or {}).get("groups") or []
        return self.learn(item for group in groups for item in group.get("items", []))

    def pick(self) -> str | None:
        if self.shown and self.rng.random() < 0.7:
            return self.rng.choice(self.shown)
        return self.rng.choice(list(self.seen)) if self.seen else None

    def word(self) -> str:
        return self.rng.choice(list(self.words))

    # Signing in and out

    async def sign_in(self) -> bool:
        """As the web app does it: what the product is, nobody signed in yet, the sample
        person's button, then the app starting again signed in."""
        await self.get("Product and branding", "/api/v1/meta")
        await self.call("Who is signed in", "GET", "/api/v1/session", expected={401: ""})
        me = data(await self.call("Sign in as a sample person", "POST", "/api/v1/session/demo",
                                  body={"email": self.account["email"]}))  # fmt: skip
        if me is None:
            return False
        self.csrf, self.permissions, self.roles = me["csrf_token"], me["permissions"], me["roles"]
        await self.get("Product and branding", "/api/v1/meta")
        await self.get("Who is signed in", "/api/v1/session")
        return True

    async def run(self, until: float, ramp: float) -> None:
        # Six connections, as a browser has. Each is let go after four seconds unused, before
        # the server closes it at five: a browser asks again over a new connection when one
        # it reuses has just been closed, and this client does not.
        limits = httpx.Limits(max_connections=6, max_keepalive_connections=6, keepalive_expiry=4)
        headers = {"Accept": "application/json", "User-Agent": "AppWren soak test"}
        async with httpx.AsyncClient(
            base_url=self.base, timeout=TIMEOUT_SECONDS, limits=limits, headers=headers
        ) as self.client:
            await asyncio.sleep(self.rng.uniform(0, ramp))
            if not await self.sign_in():
                return
            await self.attempt(self.home)
            while (left := until - time.monotonic()) > 0:
                await asyncio.sleep(self.pause(left))
                if time.monotonic() < until:
                    await self.attempt(self.act)
            await self.call("Sign out", "DELETE", "/api/v1/session")

    async def attempt(self, step: Callable[[], Awaitable[Any]]) -> None:
        try:
            await step()
        except Exception as exc:  # a step that cannot be taken is a failure; the person goes on
            said = f"{self.account['key']}: {type(exc).__name__}: {exc}"
            self.tally.failures.append((self.tally.now(), "A simulated person's step", said))

    # Where it goes

    async def act(self) -> None:
        if self.tally.changes < self.share * len(self.tally.done) and await self.change():
            return
        name = self.rng.choices(list(PAGES), weights=list(PAGES.values()))[0]
        await getattr(self, name)()

    async def home(self) -> None:
        calls = [self.get("Home", "/api/v1/home"), self.lookup("vocabularies")]
        if self.permissions.get("admin"):
            calls += [self.lookup("units"), self.lookup("accounts")]
        await self.page(*calls)

    def list_params(self) -> tuple[dict[str, Any], str]:
        roll = self.rng.random()
        if roll < 0.35:
            params = self.filter()
            if params and self.rng.random() < 0.25:
                params.update(self.filter())
            if params:
                return params, "Applications, filtered"
        elif roll < 0.55:
            return {"q": self.word()}, "Applications, searched"
        elif roll < 0.70:
            return {"sort": self.rng.choice(SORTS)}, "Applications, sorted"
        elif roll < 0.78:
            return {"mine": "true"}, "Applications, mine"
        return {}, "Applications, first page"

    def filter(self) -> dict[str, Any]:
        name = self.rng.choice(FILTERS)
        if name == "unit":
            choices = [unit["id"] for unit in (self.known.get("units") or {}).get("units", [])]
        elif name == "maturity":
            levels = (self.known.get("catalog") or {}).get("maturity_levels") or []
            choices = [level[0] for level in levels] + (["unmeasured"] if levels else [])
        else:
            vocabulary = {"tier": "tiers", "domain": "domains"}.get(name, name)
            items = (self.known.get("vocabularies") or {}).get(vocabulary, [])
            choices = [item["key"] for item in items if not item.get("retired")]
        return {name: self.rng.choice(choices)} if choices else {}

    async def applications(self) -> None:
        """The list of applications, as it opens or filtered, searched, sorted, or one's own;
        then perhaps a page or two further on, and perhaps one of them opened."""
        params, kind = self.list_params()
        query = {"sort": "name", **params}
        lookups = ("vocabularies", "units", "catalog")
        answer, *_ = await self.page(
            self.get(kind, "/api/v1/applications", query), *map(self.lookup, lookups)
        )
        if answer is None:
            return
        body = answer.json()
        self.shown = self.learn(body["data"])
        for _ in range(self.rng.choice((0, 0, 0, 1, 1, 2, 3))):
            cursor = body.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            await self.wait()
            answer, *_ = await self.page(
                self.get("Applications, next page", "/api/v1/applications",
                         {**query, "cursor": cursor}),
                *map(self.lookup, lookups),
            )  # fmt: skip
            if answer is None:
                return
            body = answer.json()
            self.shown = self.learn(body["data"])
        if self.shown and self.rng.random() < 0.5:
            await self.wait()
            await self.application(self.rng.choice(self.shown))

    async def application(self, ref: str | None = None) -> None:
        """An application's page, on one tab and then perhaps another or two."""
        ref = ref or self.pick()
        if ref is None:
            await self.applications()
            return
        await self.open(ref, "overview" if self.rng.random() < 0.6 else self.tab())
        for _ in range(self.rng.choice((0, 0, 1, 1, 2))):
            await self.wait()
            await self.open(ref, self.tab())

    def tab(self) -> str:
        return self.rng.choices(list(TABS), weights=list(TABS.values()))[0]

    async def open(self, ref: str, tab: str = "overview") -> tuple[Any, Any]:
        """An application's page on one tab: the requests pages/record.js makes for it."""
        base = f"/api/v1/applications/{ref}"
        behind = {
            "scores": [("Application, contests", f"{base}/contests", None),
                       ("Application, score history", f"{base}/score-history", None)],
            "assessment": [("Application, assessments", f"{base}/assessments", None)],
            "decisions": [("Application, decisions", f"{base}/decisions", None)],
            "components": [("Application, deployments", "/api/v1/deployments",
                            {"application": ref, "sort": "environment", "limit": 200}),
                           ("Application, maturity", f"/api/v1/maturity/{ref}", None)],
            "connections": [("Application, interfaces", "/api/v1/interfaces",
                             {"application": ref, "sort": "name", "limit": 200}),
                            ("Application, impact", f"{base}/impact", None)],
            "cost": [("Application, costs", f"{base}/costs", None)],
            "retirement": [("Application, retirement", f"{base}/retirement", None)],
            "history": [("Application, history", f"{base}/history", None)],
        }.get(tab, [])  # fmt: skip
        lookups = ["vocabularies", "units", "catalog"] + (["questionnaire"] * (tab == "assessment"))
        record, _, scores, *_ = await self.page(
            self.get("Application", base),
            self.get("Application, sourced values", f"/api/v1/sourced/{ref}"),
            self.get("Application, scores", f"{base}/scores"),
            *[self.get(kind, path, params) for kind, path, params in behind],
            *map(self.lookup, lookups),
        )
        record, scores = data(record), data(scores)
        if record is None:
            return None, None
        if record.get("can", {}).get("edit"):
            self.editable.add(ref)
        if ((scores or {}).get("confirmation") or {}).get("can_confirm"):
            self.confirmable.add(ref)
        if tab == "overview" and record.get("suggestions_pending"):
            await self.get("Application, proposed changes", f"{base}/suggestions")
        return record, scores

    async def dashboard(self) -> None:
        units = [unit["id"] for unit in (self.known.get("units") or {}).get("units", [])]
        params = {"unit": self.rng.choice(units)} if units and self.rng.random() < 0.25 else None
        await self.page(
            self.get("Dashboard, one unit" if params else "Dashboard", "/api/v1/dashboard", params),
            self.lookup("vocabularies"),
            self.lookup("units"),
        )

    async def search(self) -> None:
        """Finding by words: the quick find as they are typed, then often the search page,
        sometimes narrowed to applications, and sometimes one of them opened."""
        word = self.word()
        if len(word) > 4 and self.rng.random() < 0.5:
            await self.get("Quick find", "/api/v1/search", {"q": word[:3], "limit": 4})
        refs = self.found(data(await self.get("Quick find", "/api/v1/search",
                                              {"q": word, "limit": 4})))  # fmt: skip
        if self.rng.random() < 0.6:
            answer, _ = await self.page(
                self.get("Search everything", "/api/v1/search", {"q": word, "limit": 6}),
                self.lookup("units"),
            )
            refs = self.found(data(answer)) or refs
            if self.rng.random() < 0.3:
                await self.wait()
                answer, _ = await self.page(
                    self.get("Search, applications only", "/api/v1/search",
                             {"q": word, "type": "application", "limit": 50}),
                    self.lookup("units"),
                )  # fmt: skip
                refs = self.found(data(answer)) or refs
        if refs and self.rng.random() < 0.5:
            await self.wait()
            await self.application(self.rng.choice(refs))

    async def report(self) -> None:
        """One of the reports: those anyone may open, the trends between two snapshots, and
        for those who read everything, the leadership reports and the whole history."""
        pick = self.rng.randrange(len(REPORTS) + 3)
        if pick == len(REPORTS):
            answer, _ = await self.page(
                self.get("Trends, the snapshots", "/api/v1/portfolio-snapshots"),
                self.lookup("vocabularies"),
            )
            snapshots = data(answer) or []
            if snapshots:
                before = snapshots[min(1, len(snapshots) - 1)]["ref"]
                after = snapshots[0]["ref"] if len(snapshots) > 1 else None
                between = {"before": before, **({"after": after} if after else {})}
                await self.get("Trends", "/api/v1/trends", between)
            return
        if pick > len(REPORTS) and self.permissions.get("read_all"):
            if pick == len(REPORTS) + 1:
                answer, *_ = await self.page(self.get("Leadership reports", "/api/v1/reports"))
                made = data(answer) or []
                if made:
                    await self.wait()
                    ref = self.rng.choice(made)["ref"]
                    await self.page(self.get("Leadership report", f"/api/v1/reports/{ref}"))
            else:
                await self.page(self.get("Whole history", "/api/v1/history", {"kind": "records"}))
            return
        kind, path, params, lookups = REPORTS[pick % len(REPORTS)]
        await self.page(self.get(kind, path, params), *map(self.lookup, lookups))

    async def tasks(self) -> None:
        if self.rng.random() < 0.6:
            await self.page(self.get("Tasks", "/api/v1/tasks"))
        else:
            await self.page(self.get("Notices", "/api/v1/notices"))

    async def again(self) -> None:
        """Sign out, and back in, as people do from one day to the next."""
        await self.call("Sign out", "DELETE", "/api/v1/session")
        self.csrf = ""
        self.kept.clear()
        if await self.sign_in():
            await self.home()

    async def change(self) -> bool:
        """A change that goes into the history, made as people make them: the application's
        page, a pause to fill in the dialog, the change, and the page again as it reloads.
        Returns False if this person has nothing they may change yet."""
        ways = [way for way, refs in (("edit", self.editable), ("confirm", self.confirmable))
                if refs]  # fmt: skip
        if "auditor" not in self.roles and self.seen:
            ways.append("propose")
        if not ways:
            return False
        way = self.rng.choice(ways)
        ref = self.pick() if way == "propose" else self.rng.choice(
            sorted(self.editable if way == "edit" else self.confirmable)
        )  # fmt: skip
        if ref is None:
            return False
        record, scores = await self.open(ref)
        if record is None:
            return True
        await self.wait()
        base = f"/api/v1/applications/{ref}"
        summary = (record.get("summary") or "").strip()
        if way == "edit":
            if not record.get("can", {}).get("edit"):
                self.editable.discard(ref)
                return True
            reviewed = summary.removesuffix(REVIEWED).strip()
            changed = reviewed if summary.endswith(REVIEWED) else f"{summary} {REVIEWED}".strip()
            self.tally.changes += 1
            await self.call("Edit an application's summary", "PATCH", base,
                            body={"version": record["version"], "summary": changed},
                            expected={409: "changed by someone else"})  # fmt: skip
        elif way == "confirm":
            if not ((scores or {}).get("confirmation") or {}).get("can_confirm"):
                self.confirmable.discard(ref)
                return True
            self.tally.changes += 1
            await self.call("Confirm an application's record", "POST", f"{base}/confirmations",
                            body={"note": None})  # fmt: skip
        else:
            self.tally.changes += 1
            await self.call("Propose a change to an application", "POST", f"{base}/suggestions",
                            body={"field": "summary", "value": f"{summary} It is used daily.",
                                  "note": "Proposed during a soak test."},
                            expected={422: "waiting"})  # fmt: skip
        self.kept.clear()  # the web app forgets what it kept after any change
        await self.open(ref)
        return True


# --- Setting up and the server --------------------------------------------------------------


def choose_people(db: Any, count: int, rng: random.Random) -> list[dict[str, Any]]:
    """The demo's people to sign in as: the sample people it offers, then others across
    roles, one for each simulated person while there are enough. Those it does not offer
    yet are added to what it offers, so that its sign-in lets them in."""
    from appwren.db.models import Account, RecordOwner, RoleGrant
    from appwren.demo import build as demo_build
    from appwren.events.actor import Actor
    from appwren.program import settings

    order = ("steward", "named", "leader", "architect", "member", "manager", "auditor", "admin")
    with db.read() as session:
        marker = demo_build.marker(session)
        assert marker is not None, "the installation is not a demo"
        offered = list(marker["accounts"])
        taken = {person["email"] for person in offered}
        roles: dict[int, set[str]] = defaultdict(set)
        for account_id, role in session.execute(select(RoleGrant.account_id, RoleGrant.role)):
            roles[account_id].add(role)
        named = set(session.scalars(
            select(RecordOwner.account_id).where(RecordOwner.record_type == "application")
        ))  # fmt: skip
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        active = select(Account).where(Account.status == "active").order_by(Account.id)
        for account in session.scalars(active):
            if account.email in taken:
                continue
            held = roles.get(account.id, set())
            group = next((role for role in order if role in held), None) or (
                sorted(held)[0] if held else "named" if account.id in named else "member"
            )
            groups[group].append({"key": f"{group}-{account.id}", "email": account.email,
                                  "name": account.display_name, "title": account.title or "",
                                  "about": ""})  # fmt: skip
    for people in groups.values():
        rng.shuffle(people)
    more: list[dict[str, Any]] = []
    names = [*order, *sorted(set(groups) - set(order))]
    while len(offered) + len(more) < count and any(groups.values()):
        for name in names:
            if groups.get(name) and len(offered) + len(more) < count:
                more.append(groups[name].pop())
    if more:
        with db.write(Actor.command("Soak test")) as session:
            settings.put(session, demo_build.SETTING, {**marker, "accounts": [*offered, *more]})
    return [*offered, *more][:count]


def free_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port not in HELD_PORTS:
            return port


def appwren_command(config: Path, *words: str) -> list[str]:
    """`uv run appwren` with this configuration, with the PostgreSQL driver where needed."""
    extra = ["--extra", "postgres"] if os.environ.get("APPWREN_DATABASE_URL") else []
    return ["uv", "run", "--quiet", *extra, "appwren", "-c", str(config), *words]


def start_server(
    config: Path, port: int, workers: int | None, log: Path, *, scheduler: bool
) -> subprocess.Popen:
    """Start the server in a process group of its own, so that Ctrl-C reaches only this
    script, which then stops the server itself."""
    words = ["serve", "--port", str(port), *(["--workers", str(workers)] if workers else [])]
    env = {**os.environ, "APPWREN_SERVER_SCHEDULER": "true" if scheduler else "false",
           "PYTHONUNBUFFERED": "1"}  # fmt: skip
    with log.open("w", encoding="utf-8") as output:
        return subprocess.Popen(
            appwren_command(config, *words), cwd=REPOSITORY, env=env, stdout=output,
            stderr=subprocess.STDOUT, start_new_session=True,
        )  # fmt: skip


def wait_until_ready(server: subprocess.Popen, base: str) -> bool:
    deadline = time.monotonic() + READY_SECONDS
    while time.monotonic() < deadline and server.poll() is None:
        try:
            if httpx.get(f"{base}/api/v1/health/ready", timeout=2).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def stop_server(server: subprocess.Popen) -> tuple[bool, float, int | None]:
    """Stop the server as Ctrl-C in its terminal would. Returns whether it stopped in time,
    how long it took, and its exit code; one that does not stop is killed."""
    if server.poll() is not None:
        return False, 0.0, server.returncode
    began = time.monotonic()
    try:
        os.killpg(server.pid, signal.SIGINT)
        code = server.wait(STOP_SECONDS)
        return True, time.monotonic() - began, code
    except subprocess.TimeoutExpired:
        return False, time.monotonic() - began, None
    finally:
        end_server(server)


def end_server(server: subprocess.Popen) -> None:
    """Kill whatever is left of the server's process group."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(server.pid, signal.SIGKILL)
    if server.poll() is None:
        server.wait()


def shut_down(log: Path) -> bool:
    """Whether the server said it had shut down, each of its processes."""
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    started = sum("Application startup complete" in line for line in lines)
    return started > 0 and sum("Application shutdown complete" in line for line in lines) >= started


def usage(pid: int) -> tuple[int, int, float]:
    """The resident memory (in kilobytes) and CPU of a process and every process under it,
    and how many processes that is."""
    table = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid=,rss=,%cpu="], capture_output=True, text=True, check=False
    ).stdout
    children: dict[int, list[int]] = defaultdict(list)
    seen: dict[int, tuple[int, float]] = {}
    for line in table.splitlines():
        parts = line.split()
        if len(parts) != 4 or not parts[0].isdigit():
            continue
        children[int(parts[1])].append(int(parts[0]))
        seen[int(parts[0])] = (int(parts[2]), float(parts[3].replace(",", ".")))
    rss, cpu, count, todo = 0, 0.0, 0, [pid]
    while todo:
        process = todo.pop()
        if process in seen:
            rss, cpu, count = rss + seen[process][0], cpu + seen[process][1], count + 1
            todo.extend(children[process])
    return rss, count, cpu


async def watch(pid: int, tally: Tally, until: float, samples: list[Sample]) -> None:
    while True:
        rss, count, cpu = await asyncio.to_thread(usage, pid)
        samples.append(Sample(tally.now(), rss, count, cpu))
        if time.monotonic() >= until:
            return
        await asyncio.sleep(min(SAMPLE_SECONDS, max(0.0, until - time.monotonic())))


async def load(
    accounts: list[dict[str, Any]], base: str, args: argparse.Namespace, pid: int
) -> tuple[Tally, list[Sample], list[Person]]:
    tally = Tally()
    rng = random.Random(args.seed)  # noqa: S311 (a repeatable simulation, not a secret)
    people = [
        Person(accounts[n % len(accounts)], base, tally, random.Random(rng.random()),  # noqa: S311
               args.think, args.changes)
        for n in range(args.people)
    ]  # fmt: skip
    seconds = args.minutes * 60
    until = time.monotonic() + seconds
    tally.began = time.perf_counter()
    samples: list[Sample] = []
    watcher = asyncio.create_task(watch(pid, tally, until, samples))
    await asyncio.gather(*(person.run(until, min(RAMP_SECONDS, seconds / 10)) for person in people))
    await watcher
    tally.ended = time.perf_counter()
    return tally, samples, people


def scheduled_work(url: str, since: Any) -> tuple[list[str], list[str]]:
    """How each scheduled job last went, and the runs that failed since the server started."""
    from appwren.db.engine import Database
    from appwren.db.models import Job, JobRun

    db = Database(url)
    try:
        with db.read() as session:
            jobs = session.scalars(select(Job).order_by(Job.key)).all()
            failed = session.scalars(
                select(JobRun).where(JobRun.status == "failed", JobRun.started_at >= since)
            ).all()
            lines = []
            for job in jobs:
                ran = job.last_finished_at is not None and job.last_finished_at >= since
                when = "ran during the soak" if ran else "not run during the soak"
                lines.append(f"  {job.key:12} {job.last_status or '-':7} {when:24} "
                             f"{job.last_summary or ''}")  # fmt: skip
            failures = [f"{run.job_key} at {run.started_at:%H:%M:%S}: {run.error}"
                        for run in failed]  # fmt: skip
    finally:
        db.dispose()
    return lines, failures


def server_log(path: Path) -> tuple[int, int, list[str], list[str]]:
    """What the server logged: how many errors, how many answers of 500 or more it gave, the
    end of the traceback of each different error, and its distinct warnings."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    heads = ("INFO", "WARNING", "ERROR", "CRITICAL")
    served = re.compile(r'HTTP/[0-9.]+" 5\d\d ')
    failed_answers = sum(1 for line in lines if served.search(line))
    causes: dict[str, list[str]] = {}
    count: Counter[str] = Counter()
    errors = [n for n, line in enumerate(lines) if line.startswith(("ERROR", "CRITICAL"))]
    for n in errors:
        block = [lines[n]]
        for line in lines[n + 1 :]:
            if line.startswith(heads):
                break
            block.append(line)
        said = [line.strip(" |+-") for line in block if line.strip(" |+-")]
        raised = [line for line in said if EXCEPTION.match(line)]
        cause = (raised or said or [lines[n]])[-1]
        count[cause] += 1
        causes.setdefault(cause, [lines[n], *block[1:][-14:]])
    excerpt = []
    for cause, block in causes.items():
        excerpt += [f"{count[cause]}x: {cause}", *(f"  {line}" for line in block)]
    warnings = sorted({line for line in lines if line.startswith("WARNING")})
    return len(errors), failed_answers, excerpt, warnings


# --- The report -----------------------------------------------------------------------------


def mb(kb: float) -> str:
    return f"{kb / 1024:,.0f} MB"


def leak(samples: list[Sample], seconds: float, leak_mb: int) -> tuple[bool | None, str]:
    """Whether memory kept growing through the second half of the run (see the rule above)."""
    late = [sample.rss_kb for sample in samples if sample.at >= seconds / 2]
    if len(late) < 8:
        return None, f"{len(late)} samples in the second half: too few to judge growth"
    size = len(late) / 4
    medians = [statistics.median(late[round(n * size) : round((n + 1) * size)]) for n in range(4)]
    growth = medians[-1] - medians[0]
    rising = all(later > earlier for earlier, later in itertools.pairwise(medians))
    grew = rising and growth > leak_mb * 1024 and growth > LEAK_SHARE * medians[0]
    return grew, (
        "the median of each quarter of the second half: "
        + ", ".join(mb(median) for median in medians)
        + f" ({growth / 1024:+,.1f} MB, {100 * growth / medians[0]:+.1f}%)"
    )


def report(
    tally: Tally, samples: list[Sample], people: list[Person], args: argparse.Namespace,
    setting: str,
) -> list[str]:  # fmt: skip
    """Print the measurements, and return what is wrong with them."""
    seconds = tally.ended - tally.began
    problems: list[str] = []
    cast = Counter(next((role for role in p.roles if role != "member"), "member") for p in people)
    accounts = len({p.account["email"] for p in people})
    print(f"\n{setting}")
    roles = ", ".join(f"{n} {role}{'s' * (n > 1)}" for role, n in cast.most_common())
    print(f"People: {len(people)}, as {accounts} different accounts: {roles}")

    kinds: dict[str, list[Done]] = defaultdict(list)
    for done in tally.done:
        kinds[done.kind].append(done)
    print(f"\n{'Request':38}{'count':>7}{'failed':>7}{'p50':>10}{'p95':>10}{'p99':>10}{'max':>10}")
    rows = [*sorted(kinds.items()), ("All requests", tally.done)]
    for kind, done in rows:
        times = sorted(d.ms for d in done)
        failed = sum(d.failed for d in done)
        p95 = percentile(times, 95)
        flag = ""
        if kind != "All requests":
            if len(done) < JUDGED:
                flag = "  (too few to judge)"
            elif p95 > args.budget:
                flag = "  over budget"
                problems.append(f"{kind} has a 95th percentile of {p95:,.0f} ms")
        if kind == "All requests":
            print("-" * 92)
        p50, p99, slowest = percentile(times, 50), percentile(times, 99), (times or [0])[-1]
        print(f"{kind:38}{len(done):7,}{failed:7,}{p50:8,.0f}ms{p95:8,.0f}ms{p99:8,.0f}ms"
              f"{slowest:8,.0f}ms{flag}")  # fmt: skip

    expected = ", ".join(f"{what}: {count:,}" for what, count in sorted(tally.expected.items()))
    print(f"\nThroughput: {len(tally.done) / seconds:,.1f} requests a second "
          f"({len(tally.done):,} in {seconds:,.0f} s), {tally.changes:,} of them changes "
          f"({100 * tally.changes / max(1, len(tally.done)):.1f}%)")  # fmt: skip
    print(f"Expected refusals, not failures: {expected or 'none'}")

    step = 60 if seconds <= 15 * 60 else 60 * math.ceil(seconds / 12 / 60)
    print(f"\n{'Minutes':12}{'requests':>9}{'failed':>8}{'p50':>10}{'p95':>10}{'memory':>10}"
          f"{'cpu':>7}")  # fmt: skip
    for start in range(0, math.ceil(seconds), step):
        done = sorted(d.ms for d in tally.done if start <= d.at < start + step)
        failed = sum(d.failed for d in tally.done if start <= d.at < start + step)
        here = [s for s in samples if start <= s.at < start + step] or samples[-1:]
        memory = max(s.rss_kb for s in here) if here else 0
        cpu = statistics.mean(s.cpu for s in here) if here else 0.0
        end = min(seconds, start + step)
        span = f"{start // 60}:{start % 60:02.0f}-{end // 60:.0f}:{end % 60:02.0f}"
        print(f"{span:12}{len(done):9,}{failed:8,}{percentile(done, 50):8,.0f}ms"
              f"{percentile(done, 95):8,.0f}ms{mb(memory):>10}{cpu:6.0f}%")  # fmt: skip

    if samples:
        first, peak, last = samples[0], max(samples, key=lambda s: s.rss_kb), samples[-1]
        print(f"\nMemory of the server's {last.processes} processes: {mb(first.rss_kb)} as the "
              f"load began, {mb(peak.rss_kb)} at its peak ({peak.at:,.0f} s in), "
              f"{mb(last.rss_kb)} at the end")  # fmt: skip
    grew, said = leak(samples, seconds, args.leak_mb)
    verdict = "" if grew is None else ": growing, as a leak would" if grew else ": level"
    print(f"Growth: {said}{verdict}")
    if grew:
        problems.append(f"memory kept growing ({said})")

    if tally.failures:
        problems.append(f"{len(tally.failures):,} requests or steps failed")
        grouped: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for at, what, said in tally.failures:
            grouped[what].append((at, said))
        print("\nFailures, by what failed, each with its first example:")
        for what, seen in sorted(grouped.items(), key=lambda item: -len(item[1]))[:30]:
            print(f"  {len(seen):5,}x  {what}, first {seen[0][0]:,.0f} s in\n"
                  f"          {seen[0][1]}")  # fmt: skip
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--people", type=int, default=20, help="simulated people at once")
    parser.add_argument("--minutes", type=float, default=10, help="how long the load lasts")
    parser.add_argument(
        "--think", type=float, default=10.0, help="seconds a person reads between steps, on average"
    )
    parser.add_argument(
        "--changes", type=float, default=0.05, help="the part of requests that are changes"
    )
    parser.add_argument(
        "--budget", type=int, default=5000, help="the slowest 95th percentile allowed, in ms"
    )
    parser.add_argument(
        "--leak-mb", type=int, default=32, help="growth in the second half taken for a leak"
    )
    parser.add_argument("--workers", type=int, help="server processes (default: one)")
    parser.add_argument(
        "--no-scheduler", action="store_true",
        help="run the server without its scheduler, to see how much of the load is its own",
    )  # fmt: skip
    parser.add_argument("--applications", type=int, default=5_000, help="applications to have")
    parser.add_argument("--components", type=int, default=50_000, help="components to have")
    parser.add_argument("--seed", type=int, default=1, help="a different number, other people")
    parser.add_argument("--log", metavar="FILE", help="keep a copy of the server's log here")
    args = parser.parse_args()

    def interrupt(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)  # stopped from outside: clean up as for Ctrl-C
    perf = _perf()
    from appwren.core.clock import utc_now
    from appwren.db.engine import Database

    with tempfile.TemporaryDirectory(prefix="appwren-soak-") as folder:
        server: subprocess.Popen | None = None
        try:
            started = time.perf_counter()
            config = perf.build(folder)
            if config is None:
                return 1
            db = Database(config.database_url)
            try:
                apps, parts = perf.multiply(db.engine, args.applications, args.components)
                accounts = choose_people(db, args.people, random.Random(args.seed))  # noqa: S311
                with db.engine.connect() as conn:
                    events = conn.execute(text("SELECT seq FROM chain_head")).scalar_one()
                dialect = db.dialect
            finally:
                db.dispose()
            workers = args.workers or config.server.workers
            setting = (
                f"{args.people} people for {args.minutes:g} minutes, about {args.think:g} s "
                f"between steps, on {apps:,} applications, {parts:,} components, and "
                f"{events:,} events on {dialect}; {workers} server "
                f"{'process' if workers == 1 else 'processes'}, "
                f"the scheduler {'off' if args.no_scheduler else 'on'}"
            )
            print(f"Built the installation in {time.perf_counter() - started:,.0f} s.")

            port, log = free_port(), Path(folder) / "server.log"
            base = f"http://127.0.0.1:{port}"
            config_path = Path(folder) / "appwren.toml"
            since = utc_now()
            began = time.perf_counter()
            server = start_server(config_path, port, args.workers, log,
                                  scheduler=not args.no_scheduler)  # fmt: skip
            if not wait_until_ready(server, base):
                print(f"The server did not start. Its last words:\n{log.read_text()[-3000:]}",
                      file=sys.stderr)  # fmt: skip
                return 1
            ends = time.strftime("%H:%M", time.localtime(time.time() + args.minutes * 60))
            print(f"Server ready on port {port} in {time.perf_counter() - began:.1f} s; "
                  f"the load runs until about {ends}")  # fmt: skip
            tally, samples, people = asyncio.run(load(accounts, base, args, server.pid))

            stopped, took, code = stop_server(server)
            problems = report(tally, samples, people, args, setting)
            print(f"\nServer: {'stopped' if stopped else 'did not stop'} in {took:.1f} s "
                  f"when asked, exit code {code}")  # fmt: skip
            if not stopped or code not in CLEAN_EXITS or not shut_down(log):
                problems.append("the server did not stop cleanly")

            jobs, failed_jobs = scheduled_work(config.database_url, since)
            print("Scheduled work:\n" + "\n".join(jobs))
            for line in failed_jobs:
                print(f"  failed: {line}")
            if failed_jobs:
                problems.append(f"{len(failed_jobs)} scheduled runs failed")

            if args.log:
                shutil.copyfile(log, args.log)
            errors, answers, excerpt, warnings = server_log(log)
            print(f"Server log: {errors:,} errors, {answers:,} answers of 500 or more, "
                  f"{len(warnings)} different warnings")  # fmt: skip
            for line in warnings:
                print(f"  {line}")
            if excerpt:
                print("  Each different error, and the end of its traceback:")
                print("\n".join(f"    {line}" for line in excerpt[:200]))
            if errors:
                problems.append(f"the server logged {errors:,} errors")

            verified = subprocess.run(
                appwren_command(config_path, "verify"), cwd=REPOSITORY, capture_output=True,
                text=True, check=False,
            )  # fmt: skip
            said = (verified.stdout + verified.stderr).strip().splitlines()
            print(f"History: {said[0] if said else 'no answer from appwren verify'}")
            if verified.returncode != 0:
                problems.append("the history does not verify")

            if problems:
                sys.stdout.flush()  # the report first, then the verdict
                print("\nFailed: " + "; ".join(problems) + ".", file=sys.stderr)
                return 1
            print(f"\nPassed: no failures, every 95th percentile within {args.budget:,} ms, "
                  "memory level, the history verified.")  # fmt: skip
            return 0
        except KeyboardInterrupt:
            print("\nInterrupted. Stopping the server and removing the temporary directory.",
                  file=sys.stderr)  # fmt: skip
            return 130
        finally:
            signal.signal(signal.SIGINT, signal.SIG_IGN)  # let the clean-up finish
            if server is not None:
                stop_server(server)  # asked to stop if it is still running, and then killed


if __name__ == "__main__":
    raise SystemExit(main())
