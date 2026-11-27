#!/usr/bin/env python3
"""Check that every release upgrades to this checkout with every row and file kept.

For each release (every vX.Y.Z tag, oldest first), on SQLite and on PostgreSQL, it makes a
git worktree of the tag and builds that release's demo organization with that release's own
code, then gives it two logos the same way, since a demo has no files of its own. It records
what is there: every table's rows, every file in the data home, every event of the history,
each decision's snapshot digest, each report's digest, and every stored score. Then it
upgrades the installation with this checkout's `appwren db upgrade` and checks, with this
checkout's code, that:

- every table that was there still holds every row it held, found by its key;
- every file is still there, with the same content;
- the history verifies (`appwren verify`), and every event from before is as it was;
- every decision still carries the digest of the snapshot it was made against, and every
  report's stored content still gives its digest;
- no stored score moved, and each snapshot's working still gives its digest;
- `appwren doctor` passes (what it warns about is listed, and does not fail).

It prints one line for each release and database, then the detail of anything that failed,
and exits with 1 if anything did.

    uv run --extra postgres python scripts/upgrade-check.py
    uv run --extra postgres python scripts/upgrade-check.py --releases v0.7.0,v0.8.0
    uv run python scripts/upgrade-check.py --database sqlite

PostgreSQL runs in a disposable container of its own (podman or docker, started with
scripts/dev-postgres.sh on port 55437, apart from the one the tests use), with a fresh
database for each release. The first run needs the network, for the image and for each
release's dependencies.

Development use only: everything it makes is in a temporary directory. The worktrees, the
directory, and the container are removed when it finishes, whether it passed or not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import warnings
from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SAWarning

ROOT = Path(__file__).resolve().parent.parent
TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
SEED = 1
DATABASES = {"sqlite": "SQLite", "postgres": "PostgreSQL"}
CONTAINER = {"APPWREN_PG_CONTAINER": "appwren-pg-upgrade", "APPWREN_PG_PORT": "55437"}
CHECKS = ("upgrade", "rows", "files", "history", "digests", "scores", "doctor")
# The SQLite database and its companion files are the database, not files in the data home.
DATABASE_FILES = {"appwren.db", "appwren.db-wal", "appwren.db-shm", "appwren.db-journal"}
# Tables whose rows an upgrade replaces by design. Their row counts are still checked.
REPLACED = {
    # Its one row names the schema's migration. The upgrade replaces it with the newer one.
    "alembic_version",
}
# What a score snapshot keeps, besides its working (kept as a hash of it).
SCORE_FIELDS = (
    "application_id", "portfolio_snapshot_id", "taken_at", "reason", "model_id",
    "profile_key", "bv", "th", "cb", "re", "confidence", "recommendation", "flags", "digest",
)  # fmt: skip
# Run inside a release's worktree, with that release's code. Every release from 0.1.0 has the
# same calls. The demo has no files of its own, so it is given logos: the files a data home
# keeps are the brand's images (and attachments).
IN_RELEASE = r'''
"""Build the demo on PostgreSQL ("build"), the way `appwren demo` builds it on SQLite, and
give it a logo for light and for dark backgrounds, by this release's own code."""

import struct
import sys
import zlib
from pathlib import Path

from appwren.access.principal import Principal
from appwren.config import example_config_text, load_config
from appwren.db import migrate
from appwren.db.engine import Database
from appwren.demo import build
from appwren.events import chain
from appwren.home import DataHome
from appwren.program import branding

LOGO = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle r="3" cx="4" cy="4"/>'
LOGO += b"</svg>"


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def dot():
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(b"\x00\x2f\x6b\x4f")
    whole = chunk(b"IHDR", header) + chunk(b"IDAT", pixel) + chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + whole


step, root, seed = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
if step == "build":
    root.mkdir(parents=True, exist_ok=True)
    (root / "appwren.toml").write_text(example_config_text(), encoding="utf-8")
config = load_config(root / "appwren.toml")
if step == "build" and not config.database_url.startswith("postgresql"):
    raise SystemExit("APPWREN_DATABASE_URL does not name a PostgreSQL database")
home = DataHome(config.data.home)
home.create()
db = Database(config.database_url)
try:
    if step == "build":
        migrate.upgrade(db.engine)
        build.build(db, seed=seed)
    admin = Principal.for_command("Upgrade check")
    with db.write(admin.actor) as session:
        branding.store_image(session, admin, home.brand, "logo-light", LOGO)
        branding.store_image(session, admin, home.brand, "logo-dark", dot())
    with db.engine.connect() as conn:
        report = chain.verify(conn)
finally:
    db.dispose()
if not report.ok:
    raise SystemExit(f"The demo's history does not verify: {report.reason}")
'''


class Failed(Exception):
    """A step that has to work for the rest to mean anything did not."""


@dataclass
class State:
    """What an installation holds, read with plain SQL so that any release's schema will do."""

    revision: str | None
    rows: dict[str, int]
    keys: dict[str, set[tuple[Any, ...]]]
    files: dict[str, str]
    events: dict[int, str]
    decisions: dict[str, tuple[str, str | None]]
    reports: dict[str, dict[str, Any]]
    scores: dict[int, dict[str, Any]]


@dataclass
class Result:
    release: str
    database: str
    seconds: float = 0.0
    cells: dict[str, tuple[bool, str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def mark(self, check: str, ok: bool, short: str, details: Iterable[str] = ()) -> None:
        self.cells[check] = (ok, short)
        self.problems += [f"{check}: {detail}" for detail in details]

    @property
    def passed(self) -> bool:
        return set(self.cells) == set(CHECKS) and all(ok for ok, _ in self.cells.values())


# --- Running things --------------------------------------------------------------------------


def environment(database_url: str | None = None) -> dict[str, str]:
    """This process's environment without anything that would point a command elsewhere: no
    other AppWren settings, no other virtual environment, no other import path."""
    scrubbed = ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONHOME")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("APPWREN_") and key not in scrubbed}  # fmt: skip
    if database_url:
        env["APPWREN_DATABASE_URL"] = database_url
    return env


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def why(done: subprocess.CompletedProcess[str]) -> str:
    """The last thing a command said about what went wrong."""
    lines = (done.stderr.strip() or done.stdout.strip()).splitlines()
    return lines[-1] if lines else f"exit status {done.returncode}"


def must(done: subprocess.CompletedProcess[str], what: str) -> subprocess.CompletedProcess[str]:
    if done.returncode != 0:
        raise Failed(f"{what}: {why(done)}")
    return done


def current(args: list[str], config: Path, database_url: str | None, cwd: Path) -> Any:
    """Run this checkout's `appwren` against an installation."""
    extra = ["--extra", "postgres"] if database_url else []
    command = ["uv", "run", "--project", str(ROOT), "--frozen", *extra, "appwren"]
    return run([*command, "-c", str(config), *args], cwd=cwd, env=environment(database_url))


class Postgres:
    """A disposable PostgreSQL in a container of its own, with a fresh database per release."""

    def __init__(self) -> None:
        self.env = {**environment(), **CONTAINER}
        self.script = str(ROOT / "scripts" / "dev-postgres.sh")
        self.url = ""

    def __enter__(self) -> Postgres:
        try:
            started = must(run(["sh", self.script], cwd=ROOT, env=self.env), "PostgreSQL")
        except BaseException:
            self.__exit__()
            raise
        self.url = started.stdout.strip().splitlines()[-1]
        return self

    def __exit__(self, *_: object) -> None:
        stopped = run(["sh", self.script, "stop"], cwd=ROOT, env=self.env)
        if stopped.returncode != 0:
            print(f"Could not remove the container: {why(stopped)}", file=sys.stderr)

    def database(self, name: str) -> str:
        admin = create_engine(self.url, isolation_level="AUTOCOMMIT")
        try:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
                conn.execute(text(f'CREATE DATABASE "{name}"'))
        finally:
            admin.dispose()
        return make_url(self.url).set(database=name).render_as_string(hide_password=False)


# --- Reading an installation -----------------------------------------------------------------


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str | bytes) else value


def _canonical(value: Any) -> str:
    def plain(item: Any) -> Any:
        if isinstance(item, datetime | date):
            return item.isoformat()
        return str(item)

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=plain)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files_in(home: Path) -> dict[str, str]:
    """Every file in the data home, but the SQLite database and the logs, by its content."""
    found = {}
    for path in sorted(home.rglob("*")):
        relative = path.relative_to(home)
        if not path.is_file() or relative.parts[0] == "logs":
            continue
        if relative.as_posix() in DATABASE_FILES:
            continue
        found[relative.as_posix()] = _sha256(path.read_bytes())
    return found


def measure(database_url: str, home: Path) -> State:
    # This checkout's code works out what a snapshot's working and a report's content should
    # give, before the upgrade and after it, so a change in either is seen.
    from appwren.assessment import digest as snapshot_digest
    from appwren.insight.reports import digest_of

    engine = create_engine(database_url)
    try:
        metadata = MetaData()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SAWarning)  # indexes reflection cannot describe
            metadata.reflect(engine)
        tables = metadata.tables
        with engine.connect() as conn:
            rows, keys = {}, {}
            for name, table in tables.items():
                rows[name] = conn.execute(select(func.count()).select_from(table)).scalar_one()
                key = list(table.primary_key.columns)
                if key:
                    keys[name] = {tuple(row) for row in conn.execute(select(*key))}
            revision = conn.execute(select(tables["alembic_version"].c.version_num)).scalar()
            event = tables["event"]
            events = {row.id: row.hash for row in conn.execute(select(event.c.id, event.c.hash))}
            decision, snapshot = tables["decision"], tables["score_snapshot"]
            decisions = {
                row.ref: (row.snapshot_digest, row.digest)
                for row in conn.execute(
                    select(decision.c.ref, decision.c.snapshot_digest, snapshot.c.digest)
                    .select_from(decision)
                    .outerjoin(snapshot, snapshot.c.id == decision.c.snapshot_id)
                )
            }
            reports = {}
            if "report" in tables:  # since 0.6.0
                for row in conn.execute(select(tables["report"])):
                    content = _json(row.content)
                    worked = digest_of(row.title, row.period_from, row.period_to, content)
                    reports[row.ref] = {
                        "digest": row.digest,
                        "content": _sha256(_canonical(content).encode()),
                        "holds": worked == row.digest,
                    }
            application = tables["application"]
            scores = {}
            for row in conn.execute(
                select(snapshot, application.c.ref.label("application_ref")).join(
                    application, application.c.id == snapshot.c.application_id
                )
            ):
                found = row._mapping
                working = _json(found["working"])
                scores[found["id"]] = {
                    "application": found["application_ref"],
                    **{name: _json(found[name]) if name == "flags" else found[name]
                       for name in SCORE_FIELDS},
                    "working": _sha256(_canonical(working).encode()),
                    "holds": snapshot_digest(working) == found["digest"],
                }  # fmt: skip
    finally:
        engine.dispose()
    return State(revision, rows, keys, files_in(home), events, decisions, reports, scores)


# --- Comparing before with after -------------------------------------------------------------


def _some(items: Iterable[Any], limit: int = 5) -> str:
    items = sorted(items, key=str)
    shown = ", ".join(str(item) for item in items[:limit])
    return shown + (f", and {len(items) - limit} more" if len(items) > limit else "")


def check_rows(result: Result, before: State, after: State) -> None:
    problems = []
    for name, count in sorted(before.rows.items()):
        if name not in after.rows:
            problems.append(f"the table {name} is gone, with its {count} rows")
            continue
        if after.rows[name] < count:
            problems.append(f"{name} held {count} rows and now holds {after.rows[name]}")
        if name in REPLACED or name not in before.keys:
            continue
        lost = before.keys[name] - after.keys.get(name, set())
        if lost:
            problems.append(f"{name} lost rows it held, with the keys {_some(lost)}")
    new = len(set(after.rows) - set(before.rows))
    short = f"{sum(before.rows.values()):,}→{sum(after.rows.values()):,}"
    result.mark("rows", not problems, short + (f", {new} new tables" if new else ""), problems)


def check_files(result: Result, before: State, after: State) -> None:
    gone = [name for name in before.files if name not in after.files]
    changed = [name for name in before.files
               if name in after.files and after.files[name] != before.files[name]]  # fmt: skip
    problems = [f"gone: {_some(gone)}"] if gone else []
    problems += [f"changed: {_some(changed)}"] if changed else []
    result.mark("files", not problems, f"{len(before.files)}", problems)


def check_history(
    result: Result, before: State, after: State, verified: subprocess.CompletedProcess[str]
) -> None:
    problems = [] if verified.returncode == 0 else [f"appwren verify: {why(verified)}"]
    gone = [seq for seq in before.events if seq not in after.events]
    altered = [seq for seq, hash_ in before.events.items()
               if seq in after.events and after.events[seq] != hash_]  # fmt: skip
    problems += [f"events gone: {_some(gone)}"] if gone else []
    problems += [f"events altered: {_some(altered)}"] if altered else []
    short = f"{len(before.events):,}→{len(after.events):,}"
    result.mark("history", not problems, short, problems)


def check_digests(result: Result, before: State, after: State) -> None:
    problems = []
    for ref, (digest, _) in sorted(before.decisions.items()):
        if ref not in after.decisions:
            problems.append(f"{ref} is gone")
            continue
        now, points_at = after.decisions[ref]
        if now != digest:
            problems.append(f"{ref}'s snapshot digest was {digest[:12]} and is {now[:12]}")
        elif points_at != digest:
            problems.append(f"{ref}'s snapshot no longer has its digest ({str(points_at)[:12]})")
    for ref, was in sorted(before.reports.items()):
        now = after.reports.get(ref)
        if now is None:
            problems.append(f"{ref} is gone")
        elif now["digest"] != was["digest"] or now["content"] != was["content"]:
            problems.append(f"{ref}'s stored content or digest changed")
        elif not now["holds"]:
            problems.append(
                f"{ref}'s content does not give its digest"
                + (" (nor did it before the upgrade)" if not was["holds"] else "")
            )
    short = f"{len(before.decisions)}" + (f"+{len(before.reports)}" if before.reports else "")
    result.mark("digests", not problems, short, problems)


def check_scores(result: Result, before: State, after: State) -> None:
    moved: dict[str, list[str]] = {}
    for key, was in before.scores.items():
        now = after.scores.get(key)
        app = was["application"]
        if now is None:
            moved.setdefault(app, []).append(f"snapshot {key} is gone")
            continue
        for name, value in was.items():
            if name == "holds":
                continue
            if now.get(name) == value:
                continue
            change = "changed" if name == "working" else f"{value} → {now.get(name)}"
            moved.setdefault(app, []).append(f"snapshot {key}'s {name} {change}")
        if not now["holds"]:
            note = "" if was["holds"] else " (nor did it before the upgrade)"
            moved.setdefault(app, []).append(f"snapshot {key}'s working does not give its digest"
                                             + note)  # fmt: skip
    problems = [f"{app}: {'; '.join(changes[:3])}" for app, changes in sorted(moved.items())[:5]]
    if len(moved) > 5:
        problems.append(f"and {len(moved) - 5} more applications")
    result.mark("scores", not moved, f"{len(before.scores):,}", problems)


def check_doctor(result: Result, doctor: subprocess.CompletedProcess[str]) -> None:
    lines = [line.strip() for line in doctor.stdout.splitlines()]
    failing = [line[1:].strip() for line in lines if line.startswith("✗")]
    warned = [line[1:].strip() for line in lines if line.startswith("!")]
    result.warnings += warned
    if doctor.returncode != 0:
        result.mark("doctor", False, "", failing or [why(doctor)])
    else:
        result.mark("doctor", True, f"{len(warned)} warned" if warned else "")


# --- One release on one database -------------------------------------------------------------


def build_demo(code: Path, database: str, demo: Path, database_url: str | None) -> None:
    """Build the release's demo organization, and give it its logos, with the release's own
    code."""
    release = ["uv", "run", "--frozen", "--no-dev"]
    helper = code.parent / "in-release.py"
    helper.write_text(IN_RELEASE.lstrip(), encoding="utf-8")
    if database == "sqlite":
        made = run([*release, "appwren", "demo", str(demo), "--seed", str(SEED)], cwd=code,
                   env=environment())  # fmt: skip
        must(made, "building the demo")
        command = [*release, "python", "-I", str(helper), "logos", str(demo), str(SEED)]
    else:
        command = [*release, "--extra", "postgres", "python", "-I", str(helper), "build",
                   str(demo), str(SEED)]  # fmt: skip
    must(run(command, cwd=code, env=environment(database_url)), "building the demo")


def check_one(release: str, code: Path, database: str, pg: Postgres | None) -> Result:
    result = Result(release, database)
    started = time.monotonic()
    place = code.parent / database
    demo, home = place / "demo", place / "demo" / "var"
    config = demo / "appwren.toml"
    try:
        url = pg.database(f"upgrade_{release.replace('.', '_')}") if pg else None
        try:
            build_demo(code, database, demo, url)
        except Failed as exc:
            result.mark("upgrade", False, "not built", [f"the release's demo: {exc}"])
            return result
        database_url = url or f"sqlite:///{home / 'appwren.db'}"
        before = measure(database_url, home)
        began = time.monotonic()
        upgraded = current(["db", "upgrade"], config, url, place)
        took = time.monotonic() - began
        if upgraded.returncode != 0:
            result.mark("upgrade", False, "failed", [why(upgraded)])
            return result
        after = measure(database_url, home)
        result.mark("upgrade", True, f"{before.revision}→{after.revision} {took:.0f}s")
        check_rows(result, before, after)
        check_files(result, before, after)
        check_history(result, before, after, current(["verify"], config, url, place))
        check_digests(result, before, after)
        check_scores(result, before, after)
        check_doctor(result, current(["doctor"], config, url, place))
    except Exception as exc:  # one release's surprise should not hide the others' results
        said = str(exc).strip().splitlines()
        result.problems.append(f"{type(exc).__name__}: {said[0] if said else 'no detail'}")
    finally:
        result.seconds = time.monotonic() - started
    return result


def check_release(
    release: str, databases: list[str], workdir: Path, pg: Postgres | None
) -> list[Result]:
    code = workdir / release / "code"
    try:
        must(run(["git", "worktree", "add", "--detach", str(code), release], cwd=ROOT,
                 env=environment()), "git worktree add")  # fmt: skip
    except Failed as exc:
        return [_unbuilt(release, database, exc) for database in databases]
    try:
        extra = ["--extra", "postgres"] if "postgres" in databases else []
        try:
            must(run(["uv", "sync", "--frozen", "--no-dev", *extra], cwd=code,
                     env=environment()), "uv sync")  # fmt: skip
        except Failed as exc:
            return [_unbuilt(release, database, exc) for database in databases]
        results = []
        for database in databases:
            print(f"{release} on {DATABASES[database]} ...", end=" ", file=sys.stderr, flush=True)
            results.append(
                check_one(release, code, database, pg if database == "postgres" else None)
            )
            done = results[-1]
            print(f"{'passed' if done.passed else 'FAILED'} in {done.seconds:.0f}s",
                  file=sys.stderr, flush=True)  # fmt: skip
        return results
    finally:
        removed = run(["git", "worktree", "remove", "--force", str(code)], cwd=ROOT,
                      env=environment())  # fmt: skip
        if removed.returncode != 0:
            print(f"Could not remove the worktree at {code}: {why(removed)}. "
                  "Run: git worktree prune", file=sys.stderr)  # fmt: skip


def _unbuilt(release: str, database: str, exc: Failed) -> Result:
    result = Result(release, database)
    result.mark("upgrade", False, "not built", [f"the release: {exc}"])
    return result


# --- The whole run ---------------------------------------------------------------------------


def releases(asked: str | None) -> list[str]:
    tags = run(["git", "tag", "--list", "v*"], cwd=ROOT, env=environment()).stdout.split()
    versions = {tag: tuple(int(part) for part in found.groups())
                for tag in tags if (found := TAG.fullmatch(tag))}  # fmt: skip
    known = sorted(versions, key=versions.__getitem__)  # by version number, not by name
    if not asked:
        return known
    chosen = [tag.strip() for tag in asked.split(",") if tag.strip()]
    unknown = [tag for tag in chosen if tag not in known]
    if unknown:
        raise SystemExit(f"No such release: {', '.join(unknown)}. There are: {', '.join(known)}")
    return [tag for tag in known if tag in chosen]


def report(results: list[Result], seconds: float) -> None:
    heads = ["Release", "Database", *(check.capitalize() for check in CHECKS), "Time"]
    table = [heads]
    for result in results:
        cells = []
        for check in CHECKS:
            if check not in result.cells:
                cells.append("-")
                continue
            ok, short = result.cells[check]
            cells.append(f"{'✓' if ok else '✗'} {short}".strip())
        table.append([result.release, DATABASES[result.database], *cells,
                      f"{result.seconds:.0f}s"])  # fmt: skip
    widths = [max(len(row[i]) for row in table) for i in range(len(heads))]
    print()
    for row in table:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)))
    failed = [result for result in results if not result.passed]
    if failed:
        print("\nWhat failed:")
        for result in failed:
            where = f"{result.release} on {DATABASES[result.database]}"
            for problem in result.problems or ["it did not finish"]:
                print(f"  {where}, {problem}")
    warned = [result for result in results if result.warnings]
    if warned:
        print("\nWhat doctor warned about (not failures):")
        for result in warned:
            for warning in result.warnings:
                print(f"  {result.release} on {DATABASES[result.database]}: {warning}")
    print()
    if failed:
        print(f"{len(failed)} of {len(results)} upgrades failed, in {seconds:.0f}s.")
    else:
        upgrades = f"{len(results)} upgrade{'s' if len(results) != 1 else ''}"
        print(f"Every release upgrades with nothing lost: {upgrades}, in {seconds:.0f}s.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--releases", metavar="TAGS", help="the releases to check, such as v0.7.0,v0.8.0 "
        "(default: every vX.Y.Z tag)",
    )  # fmt: skip
    parser.add_argument(
        "--database", choices=["sqlite", "postgres", "both"], default="both",
        help="the database to check them on (default: both)",
    )  # fmt: skip
    args = parser.parse_args()
    tags = releases(args.releases)
    if not tags:
        raise SystemExit("There are no release tags to check.")
    databases = ["sqlite", "postgres"] if args.database == "both" else [args.database]
    if "postgres" in databases:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            raise SystemExit(
                "PostgreSQL needs its driver here. Run it with:\n"
                "  uv run --extra postgres python scripts/upgrade-check.py"
            ) from None
    started = time.monotonic()
    results: list[Result] = []
    with ExitStack() as stack:
        workdir = Path(stack.enter_context(
            tempfile.TemporaryDirectory(prefix="appwren-upgrade-", ignore_cleanup_errors=True)
        ))  # fmt: skip
        pg = stack.enter_context(Postgres()) if "postgres" in databases else None
        for tag in tags:
            results += check_release(tag, databases, workdir, pg)
    report(results, time.monotonic() - started)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
