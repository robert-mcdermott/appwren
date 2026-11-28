"""Scores kept between changes, so the pages that score the whole portfolio need not work every
application out again each time they are opened.

A score is worked out from what the database holds, the day, and the scoring model. So a kept
score is good for as long as none of the three moves:

- **What the database holds.** Every write that touches a table a score could read bumps one
  counter, in the same transaction as the change (``appwren.db.changes``).
- **The day.** Assessments go out of date, and releases and grants reach their ends, by the
  date alone.
- **The scoring model.** A model published or edited is a new one.

Scores are kept only from sessions that read: one that writes may hold changes that are
never committed. They are kept in each server process, for each database, and only for the
newest counter: an older generation is dropped as soon as a newer one is seen.

``CHECK``, which the test suite turns on, works every kept score out again when it is reused
and fails on any difference: a write that slips past the counter, or a caller that changes a
result it was given, is found there rather than shown to someone.
"""

from __future__ import annotations

import threading
import weakref
from collections.abc import Callable, Hashable
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from appwren.db.changes import generation

CHECK = False  # work each kept score out again, and fail on any difference (tests)
# How often scores were reused, and worked out, in this process: for measuring.
counts = {"reused": 0, "worked_out": 0}

Results = dict[int, dict[str, Any]]


class KeptScoresDiffer(AssertionError):
    """A kept score is not what working it out again gives (only raised under ``CHECK``)."""


class _Store:
    def __init__(self) -> None:
        self.key: Hashable | None = None
        self.results: Results = {}
        self.lock = threading.Lock()


_stores: weakref.WeakKeyDictionary[Engine, _Store] = weakref.WeakKeyDictionary()
_stores_lock = threading.Lock()


def _store(engine: Engine) -> _Store:
    with _stores_lock:
        found = _stores.get(engine)
        if found is None:
            found = _stores[engine] = _Store()
        return found


def _reads_only(session: Session) -> bool:
    bind = session.get_bind()
    writes = bool(getattr(bind, "get_execution_options", dict)().get("appwren_write"))
    return not writes and not (session.new or session.dirty or session.deleted)


def scores(
    session: Session, ids: list[int], key: Hashable, work_out: Callable[[list[int]], Results]
) -> Results:
    """The scores of these applications, from those kept where they are still good, the rest
    worked out by ``work_out`` and kept for next time. ``key`` names what else they depend
    on (the day and the model)."""
    if not _reads_only(session):
        return work_out(ids)
    engine = session.get_bind()
    store = _store(engine)  # type: ignore[arg-type]
    full = (generation(session), key)
    with store.lock:
        if store.key != full:
            kept: Results = {}
        else:
            kept = {app_id: store.results[app_id] for app_id in ids if app_id in store.results}
    missing = [app_id for app_id in ids if app_id not in kept]
    counts["reused"] += len(kept)
    counts["worked_out"] += len(missing)
    if missing:
        found = work_out(missing)
        # Kept only if nothing was written while they were worked out: on a database that
        # reads each statement afresh, they could mix the old and the new.
        if generation(session) == full[0]:
            with store.lock:
                if store.key != full:
                    store.key, store.results = full, {}
                store.results.update(found)
        kept.update(found)
    if CHECK and len(missing) < len(ids):
        fresh = work_out(ids)
        for app_id in ids:
            if kept[app_id] != fresh[app_id]:
                raise KeptScoresDiffer(f"The kept score of application {app_id} is stale")
    return {app_id: kept[app_id] for app_id in ids}


def forget() -> None:
    """Drop every kept score, in this process."""
    with _stores_lock:
        _stores.clear()
