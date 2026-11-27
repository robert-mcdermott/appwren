"""Signals: the facts sources supply, handed to the engine with the name of their source
(SCR-11).

Only what a source supplied is a signal. An application with none scores as before: a signal
factor with nothing behind it does not apply, rather than counting as unknown. A value a person
overrode is still a signal, shown as theirs.

Signals for an application come from its own facts (incidents and tickets that pushes fill) and
from its active components' (their dependency alerts and their last change). Its engineering
maturity is a signal where a source has read any of its repositories. A field of its own that a
source fills, such as its users, is no signal: it is the field, and the working names where its
value came from.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.core.clock import today
from appwren.db.models import Application, Component, FactValue
from appwren.engine.facts import EXTRA_FACTS

APPLICATION_SIGNALS = {"incidents_90d", "tickets_90d"}
COLUMNS = {"users", "maintainers"}  # the application's own fields that sources fill


def _who(row: FactValue) -> str:
    if row.overridden:
        return f"{row.override_by_name or 'a change by hand'}, over {row.source_name}"
    return row.source_name


def _holds(row: FactValue) -> Any:
    return row.override_value if row.overridden else row.value


def gather(session: Session, apps: list[Application]) -> dict[int, dict[str, Any]]:
    ids = [app.id for app in apps]
    if not ids:
        return {}
    signals: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    sources: dict[int, dict[str, str]] = defaultdict(dict)
    for row in session.scalars(
        select(FactValue).where(
            FactValue.record_type == "application", FactValue.record_id.in_(ids)
        )
    ):
        if row.field in APPLICATION_SIGNALS and _holds(row) is not None:
            signals[row.record_id][row.field] = {"value": _holds(row), "from": _who(row)}
        elif row.field in COLUMNS:
            sources[row.record_id][row.field] = _who(row)
    parts = session.execute(
        select(Component.id, Component.application_id).where(
            Component.application_id.in_(ids), Component.status == "active"
        )
    ).all()
    owner = dict(parts)
    alerts: dict[int, list[tuple[int, str]]] = defaultdict(list)
    changed: dict[int, list[tuple[date, str]]] = defaultdict(list)
    if owner:
        for row in session.scalars(
            select(FactValue).where(
                FactValue.record_type == "component",
                FactValue.record_id.in_(owner),
                FactValue.field.in_(("dependency_alerts", "last_change")),
            )
        ):
            value, app_id = _holds(row), owner[row.record_id]
            if row.field == "dependency_alerts" and isinstance(value, dict):
                count = int(value.get("critical") or 0) + int(value.get("high") or 0)
                alerts[app_id].append((count, _who(row)))
            elif row.field == "last_change" and value:
                changed[app_id].append((date.fromisoformat(str(value)[:10]), _who(row)))
    on = today()
    for app_id, found in alerts.items():
        names = sorted({who for _, who in found})
        signals[app_id]["open_alerts"] = {"value": sum(count for count, _ in found),
                                          "from": ", ".join(names)}  # fmt: skip
    for app_id, found in changed.items():
        latest, who = max(found)
        signals[app_id]["days_since_change"] = {"value": max(0, (on - latest).days), "from": who}
    coded = [app for app in apps if app.id in alerts or app.id in changed]
    if coded:
        from appwren.assessment import current_model
        from appwren.inventory import maturity

        measured = maturity.measure(session, coded, current_model(session).definition)
        for app in coded:
            item = measured[app.id]
            if item["level"] is not None:
                signals[app.id]["maturity"] = {"value": item["level"], "said": item["label"],
                                               "from": "its checks"}  # fmt: skip
    return {app_id: {"signals": signals.get(app_id, {}), "sources": sources.get(app_id, {})}
            for app_id in ids}  # fmt: skip


EXTRA_FACTS.append(gather)
