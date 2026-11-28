#!/usr/bin/env python3
"""Measure the common pages against a large installation.

Builds a demo organization, copies its applications (with their owners, units,
capabilities, components, technologies, assessments, and cost lines) until there are as many
as asked for, then copies components until there are as many of those as asked for, each
copy with its entry in the history. Then it times the requests behind the pages people open
most, signed in as the portfolio manager, and prints the median and the slowest of five
calls for each. The pages that score every application keep their scores between changes, so
each is also timed once just after a change. It exits with 1 if a median is over the budget,
a scoring page takes longer than the budget just after a change, or longer than ``--again``
when opened again.

    uv run python scripts/perf.py                          5,000 applications, 50,000 components
    uv run python scripts/perf.py --applications 1000 --components 10000
    APPWREN_DATABASE_URL=postgresql+psycopg://... uv run --extra postgres python scripts/perf.py

The PostgreSQL database must be empty: the demo is built on SQLite and moved into it with
a backup and a restore.

Development use only: it makes a throwaway installation in a temporary directory.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, func, insert, select, text

OFFSET = 1_000_000  # copy k of row n is row n + k * OFFSET
# table -> (columns that move with the copy, the column that says what kind of record)
WITH_APPLICATIONS: dict[str, tuple[dict[str, str | None], str | None]] = {
    "application": ({"id": None}, None),
    "record_owner": ({"id": None, "record_id": "record_type"}, "record_type"),
    "application_unit": ({"id": None, "application_id": None}, None),
    "application_capability": ({"id": None, "application_id": None}, None),
    "component": ({"id": None, "application_id": None}, None),
    "component_technology": ({"id": None, "component_id": None}, None),
    "assessment": ({"id": None, "application_id": None, "superseded_by": None}, None),
    "cost_line": ({"id": None, "application_id": None}, None),
}
WITH_COMPONENTS: dict[str, tuple[dict[str, str | None], str | None]] = {
    "component": ({"id": None}, None),
    "component_technology": ({"id": None, "component_id": None}, None),
}
KINDS = {"application", "component"}
# The pages that score every application the person may see. Scores are kept between
# changes, so each is timed just after a change, and again before the next.
SCORING = {"Home", "The portfolio list", "Dashboard", "Data quality", "Overlap"}
REQUESTS = [
    ("Home", "/api/v1/home"),
    ("Applications, first page", "/api/v1/applications?limit=50"),
    ("Applications, searched", "/api/v1/applications?q=lab&limit=50"),
    ("Applications, filtered and sorted", "/api/v1/applications?tier=2&sort=name&limit=50"),
    ("One application", "/api/v1/applications/APP-0024"),
    ("Its history", "/api/v1/applications/APP-0024/history"),
    ("Its score history", "/api/v1/applications/APP-0024/score-history"),
    ("Components, first page", "/api/v1/components?limit=50"),
    ("The portfolio list", "/api/v1/portfolio?in_service=true"),
    ("Dashboard", "/api/v1/dashboard"),
    ("Data quality", "/api/v1/data-quality"),
    ("Capability map", "/api/v1/capability-map"),
    ("Overlap", "/api/v1/overlap"),
    ("Lifecycle", "/api/v1/lifecycle"),
    ("Engineering maturity", "/api/v1/maturity"),
    ("Shares of the portfolio", "/api/v1/shares"),
    ("Roadmap", "/api/v1/roadmap"),
    ("Search everything", "/api/v1/search?q=imaging"),
    ("Tasks", "/api/v1/tasks"),
    ("Notices", "/api/v1/notices"),
]


def _copy(
    conn: Any, metadata: MetaData, tables: dict[str, tuple[dict[str, str | None], str | None]],
    source: dict[str, list[dict[str, Any]]], k: int, label: str, step: int = OFFSET,
) -> None:  # fmt: skip
    from appwren.core.clock import utc_now
    from appwren.events import chain

    shift = k * step
    for name, (moving, kind) in tables.items():
        rows = []
        for row in source[name]:
            if kind and row[kind] not in KINDS:
                continue
            new = dict(row)
            for column in moving:
                if new[column] is not None:
                    new[column] += shift
            if new.get("ref"):
                prefix, _, number = new["ref"].partition("-")
                new["ref"] = f"{prefix}-{int(number) + shift}"
            if name in ("application", "component"):
                new["name"] = f"{row['name']} ({label}{k})"
            if name == "application":
                new["successor_id"] = None  # it may come later in the batch
            rows.append(new)
        for start in range(0, len(rows), 500):
            conn.execute(insert(metadata.tables[name]), rows[start : start + 500])
        if name in ("application", "component"):
            chain.append(
                conn,
                utc_now(),
                [
                    {
                        "actor_kind": "command", "actor_id": None,
                        "actor_label": "Performance seed", "action": "created",
                        "subject_type": name, "subject_id": new["id"],
                        "subject_ref": new["ref"], "parent_type": None, "parent_id": None,
                        "changes": {key: [None, chain.jsonable(value)]
                                    for key, value in new.items() if value is not None},
                        "context": {},
                    }
                    for new in rows
                ],
            )  # fmt: skip


def multiply(engine: Any, applications: int, components: int) -> tuple[int, int]:
    """Copy the demo's applications, then its components, until there are as many of each as
    asked for."""
    names = sorted(set(WITH_APPLICATIONS) | set(WITH_COMPONENTS))
    metadata = MetaData()
    metadata.reflect(engine, only=names)

    def read(conn: Any) -> dict[str, list[dict[str, Any]]]:
        return {name: [dict(row._mapping) for row in conn.execute(select(metadata.tables[name]))]
                for name in names}  # fmt: skip

    def count(conn: Any, name: str) -> int:
        return conn.execute(select(func.count()).select_from(metadata.tables[name])).scalar_one()

    with engine.begin() as conn:
        source = read(conn)
        base = len(source["application"])
        for k in range(1, max(0, -(-(applications - base) // base)) + 1):
            _copy(conn, metadata, WITH_APPLICATIONS, source, k, "copy ")
        have = count(conn, "component")
        if have < components:
            source = read(conn)  # every component now, on every application
            per = len(source["component"])
            for k in range(1, -(-(components - have) // per) + 1):
                # Past every id the application copies took, so nothing collides.
                _copy(conn, metadata, WITH_COMPONENTS, source, k, "part ", step=100 * OFFSET)
        if engine.dialect.name == "postgresql":
            for name in names:
                conn.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('\"{name}\"', 'id'), "  # noqa: S608
                        f'(SELECT max(id) FROM "{name}"))'
                    )
                )
        return count(conn, "application"), count(conn, "component")


def build(root: str) -> Any:
    """Build the demo organization in ``root`` and, when APPWREN_DATABASE_URL is set, move it
    into that database. Returns its configuration, or None if the demo could not be built."""
    from appwren.cli import main as appwren
    from appwren.config import load_config

    if appwren(["--quiet", "demo", root]) != 0:
        return None
    config = load_config(Path(root) / "appwren.toml")
    if os.environ.get("APPWREN_DATABASE_URL"):
        # The demo is always built on SQLite. Move it, the way an installation is moved.
        from appwren import backup
        from appwren.db.engine import Database
        from appwren.home import DataHome

        home = DataHome(config.data.home)
        built = Database(load_config(Path(root) / "appwren.toml", env={}).database_url)
        target = Database(config.database_url)
        saved = Path(root) / "move.tar.gz"
        backup.create(built.engine, home, saved)
        backup.restore(target.engine, home, saved)
        built.dispose()
        target.dispose()
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--applications", type=int, default=5_000, help="applications to have")
    parser.add_argument("--components", type=int, default=50_000, help="components to have")
    parser.add_argument(
        "--budget", type=int, default=2500, help="the slowest median allowed, in ms"
    )
    parser.add_argument(
        "--again", type=int, default=500,
        help="the slowest a scoring page may be when opened again before a change, in ms",
    )  # fmt: skip
    args = parser.parse_args()
    os.environ["APPWREN_SERVER_SCHEDULER"] = "false"

    from fastapi.testclient import TestClient

    from appwren.api.app import create_app

    with tempfile.TemporaryDirectory(prefix="appwren-perf-") as root:
        started = time.perf_counter()
        config = build(root)
        if config is None:
            return 1
        app = create_app(config)
        with TestClient(app, base_url="http://127.0.0.1") as client:
            apps, parts = multiply(app.state.db.engine, args.applications, args.components)
            with app.state.db.engine.connect() as conn:
                events = conn.execute(text("SELECT seq FROM chain_head")).scalar_one()
            print(
                f"{apps:,} applications, {parts:,} components, and {events:,} events on "
                f"{app.state.db.dialect}, ready in {time.perf_counter() - started:.0f}s\n"
            )
            people = client.get("/api/v1/meta").json()["data"]["demo"]["accounts"]
            email = next(person["email"] for person in people if person["key"] == "portfolio")
            signed = client.post("/api/v1/session/demo", json={"email": email})
            if signed.status_code != 200:
                print(f"Could not sign in: {signed.status_code} {signed.text}", file=sys.stderr)
                return 1
            from appwren.db.models import Application
            from appwren.events.actor import Actor

            def change() -> None:
                """A change a score reads, as a person editing an application makes."""
                with app.state.db.write(Actor.command("Performance check")) as session:
                    row = session.scalars(select(Application).order_by(Application.id)).first()
                    row.users = (row.users or 0) + 1

            slow, failed = [], []
            print(f"{'Request':36}{'median':>9}{'slowest':>9}{'after a change':>16}")
            for label, path in REQUESTS:
                after = None
                if label in SCORING:
                    change()
                    began = time.perf_counter()
                    client.get(path)
                    after = (time.perf_counter() - began) * 1000
                times = []
                for _ in range(5):
                    began = time.perf_counter()
                    answer = client.get(path)
                    times.append((time.perf_counter() - began) * 1000)
                    if answer.status_code != 200:
                        break
                if answer.status_code != 200:
                    print(f"{label:36}  failed: {answer.status_code} from {path}")
                    failed.append(label)
                    continue
                median = statistics.median(times)
                over = median > (args.again if after is not None else args.budget)
                if after is not None and after > args.budget:
                    over = True
                flag = "  over budget" if over else ""
                then = f"{after:14.0f}ms" if after is not None else ""
                print(f"{label:36}{median:8.0f}ms{max(times):7.0f}ms{then}{flag}")
                if flag:
                    slow.append(label)
        if failed:
            print(f"\nFailed: {', '.join(failed)}", file=sys.stderr)
        if slow:
            print(f"\nOver budget: {', '.join(slow)}", file=sys.stderr)
        if failed or slow:
            return 1
        print(
            f"\nEvery median is within {args.budget} ms, and every scoring page within "
            f"{args.again} ms when opened again."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
