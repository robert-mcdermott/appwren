"""What falls out of support, and when (LND-08, LND-09).

A timeline of the technology releases in use against their end of support, with what runs on
each; a radar of the technologies in use by ring; and support dates brought in from a file.
AppWren never fetches them: an architect brings a file, sees what it would change, and
applies it (ADR-0003).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.core.errors import Invalid, PermissionDenied
from appwren.db.models import (
    Application,
    Component,
    ComponentTechnology,
    Technology,
    TechnologyRelease,
)
from appwren.events import audit
from appwren.inventory import access, parts, records
from appwren.inventory.registry import APPLICATION, COMPONENT, TECHNOLOGY
from appwren.program import vocab

MAX_PRODUCTS = 2000
MAX_CYCLES = 200


def _use(
    session: Session, principal: Principal
) -> tuple[dict[int, set[int]], dict[int, set[int]], dict[int, set[int]]]:
    """For each release, and for each technology with no release named, the components and
    applications the person may see that are on it."""
    seen = access.visible(session, principal, COMPONENT)
    conditions = [Component.status == "active"]
    if seen is not None:
        conditions.append(seen)
    by_release: dict[int, set[int]] = defaultdict(set)
    apps_of: dict[int, set[int]] = defaultdict(set)
    by_technology: dict[int, set[int]] = defaultdict(set)
    for release_id, technology_id, component_id, application_id in session.execute(
        select(
            ComponentTechnology.release_id,
            ComponentTechnology.technology_id,
            Component.id,
            Component.application_id,
        )
        .join(Component, Component.id == ComponentTechnology.component_id)
        .where(*conditions)
    ):
        by_technology[technology_id].add(component_id)
        if release_id is not None:
            by_release[release_id].add(component_id)
            apps_of[release_id].add(application_id)
    return by_release, apps_of, by_technology


def timeline(session: Session, principal: Principal, *, every: bool = False) -> dict[str, Any]:
    """Technology releases to their end of support, soonest first, each with how many
    components and applications are on it; and applications to their planned retirement.
    Releases nothing runs on are left out unless ``every`` is asked for."""
    on = today()
    by_release, apps_of, _ = _use(session, principal)
    technologies = {row.id: row for row in session.scalars(select(Technology))}
    releases = []
    for release in session.scalars(select(TechnologyRelease)):
        technology = technologies.get(release.technology_id)
        used = by_release.get(release.id, set())
        if technology is None or technology.status != "active" or (not used and not every):
            continue
        releases.append(
            {
                "technology": records.chip(TECHNOLOGY, technology),
                "radar": technology.radar,
                "release_id": release.id,
                "cycle": release.cycle,
                "released_on": release.released_on,
                "support_ends": release.support_ends,
                "extended_ends": release.extended_ends,
                "support": parts.support_state(release, on),
                "components": len(used),
                "applications": len(apps_of.get(release.id, ())),
            }
        )
    far = date(9999, 12, 31)
    releases.sort(
        key=lambda item: (item["support_ends"] or far, item["technology"]["name"], item["cycle"])
    )
    seen = access.visible(session, principal, APPLICATION)
    conditions = [Application.status == "active", Application.retire_planned.is_not(None)]
    if seen is not None:
        conditions.append(seen)
    retiring = [
        {**records.chip(APPLICATION, app), "retire_planned": app.retire_planned,
         "lifecycle": app.lifecycle, "go_live": app.go_live}
        for app in session.scalars(
            select(Application).where(*conditions).order_by(Application.retire_planned)
        )
    ]  # fmt: skip
    counts: dict[str, int] = defaultdict(int)
    for item in releases:
        counts[item["support"]] += 1
    return {"today": on, "releases": releases, "by_support": dict(counts), "retiring": retiring}


def radar(session: Session, principal: Principal) -> dict[str, Any]:
    """The technologies in use, by the organization's view of each for new work, with how
    many components use it; and those in use that nobody has placed."""
    _, _, by_technology = _use(session, principal)
    rings = [item for item in vocab.get(session, "radar") if not item.get("retired")]
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unused = 0
    for technology in session.scalars(
        select(Technology).where(Technology.status == "active").order_by(Technology.name)
    ):
        used = len(by_technology.get(technology.id, ()))
        if not used and not technology.radar:
            unused += 1
            continue
        found[technology.radar or ""].append(
            {**records.chip(TECHNOLOGY, technology), "kind": technology.kind, "components": used}
        )
    return {
        "rings": [
            {"key": ring["key"], "label": ring["label"], "description": ring.get("description"),
             "technologies": found.get(ring["key"], [])}
            for ring in rings
        ],
        "unplaced": found.get("", []),
        "unused": unused,
    }  # fmt: skip


# --- Support dates from a file --------------------------------------------------------------


def _day(value: Any) -> date | None:
    """A date, where the file gives one. It may give true or false in its place, for "it has
    ended" or "it has no end": neither is a date, and neither is taken."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def import_end_of_life(
    session: Session, principal: Principal, data: Any, *, dry_run: bool
) -> dict[str, Any]:
    """Bring releases and their support dates in from a file: an object whose keys are
    products and whose values are lists of release cycles, each with ``cycle`` and any of
    ``releaseDate``, ``eol`` (the end of support), ``extendedSupport``, and ``latest``.

    A product is matched to the technology whose end-of-life key it is. Releases are added
    and dates updated; nothing is removed, and a date the file does not give is left as it
    is. Returns what would change, or what did."""
    if not access.keeps_shared(principal):
        raise PermissionDenied("Only an architect or a manager can change a technology.")
    if not isinstance(data, Mapping) or len(data) > MAX_PRODUCTS:
        raise Invalid(
            "The file was not read.",
            {"file": "It should be one object: each product's key, with its list of releases."},
        )
    wanted = {str(key).strip().lower(): value for key, value in data.items()}
    technologies = {
        row.eol_key.strip().lower(): row
        for row in session.scalars(select(Technology).where(Technology.eol_key.is_not(None)))
        if row.eol_key and row.eol_key.strip()
    }
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "matched": [],
        "added": [],
        "changed": [],
        "problems": [],
        "unmatched": sorted(key for key in wanted if key not in technologies)[:50],
        "without_key": sum(
            1
            for row in session.scalars(select(Technology).where(Technology.status == "active"))
            if not (row.eol_key or "").strip()
        ),
    }
    fields = (
        ("releaseDate", "released_on"),
        ("eol", "support_ends"),
        ("extendedSupport", "extended_ends"),
    )
    with audit.operation(session, "technology.end_of_life_import"):
        for key, technology in sorted(technologies.items()):
            cycles = wanted.get(key)
            if cycles is None:
                continue
            if not isinstance(cycles, list) or len(cycles) > MAX_CYCLES:
                report["problems"].append(f"{key}: its releases should be a list.")
                continue
            report["matched"].append(records.chip(TECHNOLOGY, technology))
            have = {
                row.cycle: row
                for row in session.scalars(
                    select(TechnologyRelease).where(
                        TechnologyRelease.technology_id == technology.id
                    )
                )
            }
            for item in cycles:
                cycle = str(item.get("cycle", "")).strip() if isinstance(item, Mapping) else ""
                if not cycle or len(cycle) > 40:
                    report["problems"].append(f"{key}: a release has no cycle.")
                    continue
                dates = {column: _day(item.get(name)) for name, column in fields}
                latest = item.get("latest")
                latest = str(latest).strip()[:40] if isinstance(latest, str | int | float) else None
                row = have.get(cycle)
                if row is None:
                    report["added"].append(
                        {"technology": technology.name, "cycle": cycle,
                         "support_ends": dates["support_ends"]}
                    )  # fmt: skip
                    if not dry_run:
                        row = TechnologyRelease(
                            technology_id=technology.id, cycle=cycle, latest=latest, **dates
                        )
                        session.add(row)
                        have[cycle] = row
                    continue
                for column, value in dates.items():
                    before = getattr(row, column)
                    if value is not None and value != before:
                        report["changed"].append(
                            {"technology": technology.name, "cycle": cycle, "field": column,
                             "from": before, "to": value}
                        )  # fmt: skip
                        if not dry_run:
                            setattr(row, column, value)
                if latest and latest != row.latest and not dry_run:
                    row.latest = latest
        session.flush()
    return report
