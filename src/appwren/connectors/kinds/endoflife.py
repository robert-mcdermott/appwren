"""End-of-life data: support dates for technology releases from the public endoflife.date
dataset, matched by each technology's end-of-life key (SIG-04).

The same rules as the import from a file: releases are added and dates updated; nothing is
removed, and a date the dataset does not give is left as it is. Each date it sets is kept
with its source. A date a person has set by hand is theirs, and the dataset's waits beside it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.connectors import Kind, Reading, Setting, register, sourced
from appwren.db.models import Technology, TechnologyRelease
from appwren.landscape.lifecycle import MAX_CYCLES, _day

RELEASED = sourced.field("technology_release", "released_on", "Released", "date", column=True)
ENDS = sourced.field("technology_release", "support_ends", "Support ends", "date", column=True)
EXTENDED = sourced.field(
    "technology_release", "extended_ends", "Extended support ends", "date", column=True
)
LATEST = sourced.field("technology_release", "latest", "Latest version", "text", column=True)
DATES = (("releaseDate", RELEASED), ("eol", ENDS), ("extendedSupport", EXTENDED))


def _technologies(session: Session) -> list[Technology]:
    return [
        row
        for row in session.scalars(
            select(Technology).where(Technology.status == "active", Technology.eol_key.is_not(None))
        )
        if (row.eol_key or "").strip()
    ]


def read(reading: Reading) -> None:
    base = reading.settings.get("base_url") or "https://endoflife.date"
    with reading.client(base) as client:
        for technology in _technologies(reading.session):
            key = technology.eol_key.strip().lower()  # type: ignore[union-attr]
            cycles = reading.get(client, f"/api/{key}.json")
            if cycles is None:
                reading.miss(f"{technology.name} ({key})", "the dataset has no product by that key")
                continue
            if not isinstance(cycles, list) or len(cycles) > MAX_CYCLES:
                reading.miss(f"{technology.name} ({key})", "the dataset's answer was not a list")
                continue
            have = {
                row.cycle: row
                for row in reading.session.scalars(
                    select(TechnologyRelease).where(
                        TechnologyRelease.technology_id == technology.id
                    )
                )
            }
            for item in cycles:
                cycle = str(item.get("cycle", "")).strip() if isinstance(item, Mapping) else ""
                if not cycle or len(cycle) > 40:
                    continue
                values = _values(item)
                row = have.get(cycle)
                if row is not None:
                    for spec, value in values:
                        reading.keep(row, spec, value)
                else:
                    reading.steps.append(_add(technology.id, cycle, values))


def _values(item: Mapping[str, Any]) -> list[tuple[sourced.Field, Any]]:
    found: list[tuple[sourced.Field, Any]] = []
    for name, spec in DATES:
        day = _day(item.get(name))
        if day is not None:
            found.append((spec, day))
    latest = item.get("latest")
    if isinstance(latest, str | int | float) and str(latest).strip():
        found.append((LATEST, str(latest).strip()[:40]))
    return found


def _add(
    technology_id: int, cycle: str, values: list[tuple[sourced.Field, Any]]
) -> Callable[[Session, Callable[[Any, sourced.Field, Any], None]], None]:
    def step(session: Session, put: Callable[[Any, sourced.Field, Any], None]) -> None:
        row = TechnologyRelease(technology_id=technology_id, cycle=cycle)
        session.add(row)
        session.flush()
        for spec, value in values:
            put(row, spec, value)

    return step


def check(reading: Reading) -> str:
    base = reading.settings.get("base_url") or "https://endoflife.date"
    with reading.client(base) as client:
        found = reading.get(client, "/api/all.json")
    count = len(found) if isinstance(found, list) else 0
    keyed = len(_technologies(reading.session))
    return f"The dataset answers, with {count} products. {keyed} technologies have a key."


register(
    Kind(
        key="endoflife",
        label="End-of-life data",
        describes="Support dates for technology releases from the public endoflife.date "
        "dataset, for each technology with an end-of-life key",
        access="None: the dataset is public. Only each technology's key is sent.",
        settings=(
            Setting("base_url", "Address", "Leave as it is unless you keep a copy of the dataset",
                    required=False, default="https://endoflife.date"),
        ),
        credential=None,
        read=read,
        check=check,
    )
)  # fmt: skip
