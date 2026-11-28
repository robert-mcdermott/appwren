"""Scheduled work: the jobs AppWren runs by itself, and the scheduler that runs them.

The scheduler lives in the server process. Before a process runs a job it claims the job's
row in the database, so several server processes, or the server and ``appwren jobs run``
from a scheduled task, never run the same job at once. What is due is worked out from the
clock everything else uses, and from what is in the database, so a restart loses nothing.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from appwren import mail, reminders
from appwren.config import Config
from appwren.core.clock import utc_now
from appwren.core.errors import NotFound
from appwren.db.engine import Database
from appwren.db.models import Job, JobRun, SignInRequest
from appwren.events.actor import Actor

log = logging.getLogger("appwren.jobs")

LEASE = timedelta(minutes=15)  # a job claimed by a process that died is taken up after this
KEEP_RUNS = timedelta(days=90)
EVERY_SECONDS = 20  # how often the server looks for work that is due
SCHEDULER = Actor.system("Scheduler")


@dataclass(frozen=True)
class JobSpec:
    key: str
    label: str
    describes: str
    every: timedelta
    run: Callable[[Database, Config], dict[str, int]]


def _mail(db: Database, config: Config) -> dict[str, int]:
    return mail.run_once(db, config)


def _reminders(db: Database, _config: Config) -> dict[str, int]:
    # A campaign's item is done when its thing is done, whoever did it and however; the few a
    # change elsewhere did not close are closed here, under the scheduler's name.
    from appwren.oversight import campaigns

    with db.write(SCHEDULER, action="job.reminders") as session:
        closed = campaigns.refresh_all(session)
    # Reminders are notices, which are not history, so no actor writes them.
    with db.bookkeeping() as session:
        counts = reminders.send(session)
    counts["campaign_items_done"] = closed
    return counts


def _triggers(db: Database, _config: Config) -> dict[str, int]:
    from appwren.oversight import tasks

    # What is due is worked out by reading, then raised in batches, each committed, so a first
    # run that finds a thousand tasks holds nobody's changes up while it writes them all. The
    # last turn works it out again, raises anything due since, and settles what is not.
    with db.read() as session:
        wanted = list(tasks.due(session).items())
    raised = 0
    for start in range(0, len(wanted), tasks.BATCH):
        with db.write(SCHEDULER, action="job.triggers") as session:
            raised += tasks.raise_due(session, dict(wanted[start : start + tasks.BATCH]))
    with db.write(SCHEDULER, action="job.triggers") as session:
        counts = tasks.run(session)
    counts["tasks_raised"] += raised
    return counts


def _connectors(db: Database, _config: Config) -> dict[str, int]:
    from appwren import connectors

    return connectors.run_due(db)


def _snapshots(db: Database, _config: Config) -> dict[str, int]:
    from appwren import decisions

    with db.write(SCHEDULER, action="job.snapshots") as session:
        return {"monthly_snapshots_taken": decisions.take_monthly(session)}


def _webhooks(db: Database, config: Config) -> dict[str, int]:
    from appwren.integration import webhooks

    return webhooks.run_once(db, config)


def _standings(db: Database, config: Config) -> dict[str, int]:
    from appwren.integration import standings

    return standings.run_once(db, config)


def _tidy(db: Database, config: Config) -> dict[str, int]:
    now = utc_now()
    with db.bookkeeping() as session:
        runs = session.execute(delete(JobRun).where(JobRun.finished_at < now - KEEP_RUNS))
        begun = session.execute(
            delete(SignInRequest).where(SignInRequest.created_at < now - timedelta(hours=1))
        )
        counts = {
            "old_runs_removed": runs.rowcount or 0,  # type: ignore[attr-defined]
            "unfinished_sign_ins_removed": begun.rowcount or 0,  # type: ignore[attr-defined]
        }
    # Whether or not the assistant is on now: what it was told before stays only so long.
    if config.assistant.keep_days:
        from appwren import assistant

        # In batches, so a first tidy of a long backlog holds nobody's work up for long.
        forgotten = 0
        while True:
            with db.write(SCHEDULER, action="job.tidy") as session:
                gone = assistant.forget_old(session, config.assistant.keep_days)
            forgotten += gone
            if gone < assistant.FORGET_BATCH:
                break
        counts["old_assistant_exchanges_removed"] = forgotten
    return counts


JOBS: dict[str, JobSpec] = {
    spec.key: spec
    for spec in (
        JobSpec("triggers", "Triggers",
                "Raises a task when a contract's notice date is near, a release in use nears "
                "its end of support, a grant nears its end, or an owner leaves; closes those "
                "that are settled",
                timedelta(hours=1), _triggers),
        JobSpec("reminders", "Reminders",
                "Reminds people of what is nearly due, and tells stewards and leaders what "
                "stays late",
                timedelta(hours=1), _reminders),
        JobSpec("mail", "Email",
                "Queues notices and daily summaries and sends what is waiting, where email is "
                "set up",
                timedelta(minutes=1), _mail),
        JobSpec("webhooks", "Webhooks",
                "Tells each webhook an administrator has registered of what it asked for, "
                "signed, and tries again later where a delivery fails",
                timedelta(minutes=1), _webhooks),
        JobSpec("standings", "Standings elsewhere",
                "Reads how each linked record stands in another system of record, where the "
                "program gives that system an address to ask",
                timedelta(hours=6), _standings),
        JobSpec("connectors", "Connectors",
                "Runs each connector an administrator has switched on, when it is due",
                timedelta(minutes=15), _connectors),
        JobSpec("snapshots", "Monthly snapshot",
                "Keeps the portfolio's scores as they stand, once a month",
                timedelta(hours=6), _snapshots),
        JobSpec("tidy", "Housekeeping",
                "Removes run records older than ninety days, sign-ins that were never finished, "
                "and the assistant's exchanges older than the configuration keeps them",
                timedelta(days=1), _tidy),
    )
}  # fmt: skip


def ensure(db: Database) -> None:
    """Give every job a row. A new job is due at once."""
    with db.bookkeeping() as session:
        known = set(session.scalars(select(Job.key)))
        for key in JOBS:
            if key not in known:
                session.add(Job(key=key, enabled=True, next_run_at=utc_now()))


def _claim(db: Database, key: str, *, force: bool) -> bool:
    now = utc_now()
    with db.bookkeeping() as session:
        row = session.scalars(
            select(Job).where(Job.key == key).with_for_update(skip_locked=True)
        ).first()
        if row is None or (row.claimed_until is not None and row.claimed_until > now):
            return False
        if not force and (not row.enabled or row.next_run_at > now):
            return False
        row.claimed_until = now + LEASE
        row.last_started_at = now
        return True


def _words(counts: dict[str, int]) -> str:
    done = [f"{value} {name.replace('_', ' ')}" for name, value in counts.items() if value]
    return ", ".join(done) or "Nothing to do"


def run_job(
    db: Database, config: Config, key: str, *, force: bool = False
) -> dict[str, Any] | None:
    """Run one job if it is due and nobody else has it. ``force`` runs it now whether or
    not it is due. Returns what happened, or None if it was not this process's to run."""
    spec = JOBS.get(key)
    if spec is None:
        raise NotFound(f"There is no job {key}.")
    if force:
        ensure(db)  # asked for by name, perhaps before the scheduler has ever run
    if not _claim(db, key, force=force):
        return None
    started = utc_now()
    counts: dict[str, int] = {}
    error: str | None = None
    try:
        counts = spec.run(db, config)
    except Exception as exc:  # one bad run must not stop the scheduler
        log.exception("the %s job failed", key)
        error = f"{type(exc).__name__}: {exc}"[:600]
    finished = utc_now()
    status = "failed" if error else "ok"
    with db.bookkeeping() as session:
        row = session.get(Job, key)
        assert row is not None
        row.claimed_until = None
        row.last_finished_at = finished
        row.last_status = status
        row.last_summary = (error or _words(counts))[:300]
        row.next_run_at = started + spec.every
        if error or any(counts.values()):
            session.add(JobRun(job_key=key, started_at=started, finished_at=finished,
                               status=status, counts=counts, error=error))  # fmt: skip
    return {"key": key, "status": status, "counts": counts, "error": error,
            "summary": error or _words(counts)}  # fmt: skip


def run_due(db: Database, config: Config) -> list[dict[str, Any]]:
    """Run every job that is due. Safe to call from several processes at once."""
    ensure(db)
    results = []
    for key in JOBS:
        result = run_job(db, config, key)
        if result is not None:
            results.append(result)
    return results


def status(session: Session, *, runs: int = 12) -> list[dict[str, Any]]:
    rows = {row.key: row for row in session.scalars(select(Job))}
    recent = session.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(200)).all()
    out = []
    for key, spec in JOBS.items():
        row = rows.get(key)
        out.append(
            {
                "key": key,
                "label": spec.label,
                "describes": spec.describes,
                "every_seconds": int(spec.every.total_seconds()),
                "enabled": row.enabled if row else True,
                "next_run_at": row.next_run_at if row else None,
                "running": bool(row and row.claimed_until and row.claimed_until > utc_now()),
                "last_finished_at": row.last_finished_at if row else None,
                "last_status": row.last_status if row else None,
                "last_summary": row.last_summary if row else None,
                "runs": [
                    {"started_at": run.started_at, "finished_at": run.finished_at,
                     "status": run.status, "summary": run.error or _words(run.counts)}
                    for run in recent if run.job_key == key
                ][:runs],
            }
        )  # fmt: skip
    return out


def set_enabled(db: Database, key: str, enabled: bool) -> None:
    if key not in JOBS:
        raise NotFound(f"There is no job {key}.")
    ensure(db)
    with db.bookkeeping() as session:
        row = session.get(Job, key)
        assert row is not None
        row.enabled = enabled


def start_worker(db: Database, config: Config) -> threading.Event:
    """Run the scheduler beside the server for as long as it is up. Returns an event that
    stops it when set."""
    stop = threading.Event()

    def work() -> None:
        while not stop.wait(EVERY_SECONDS):
            try:
                run_due(db, config)
            except Exception:  # the scheduler must outlive a bad turn
                log.exception("the scheduler failed this time and will try again")

    threading.Thread(target=work, name="appwren-jobs", daemon=True).start()
    return stop
