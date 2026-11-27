"""Shares of the portfolio: the costliest tenth, the least used fifth, and others, read from the
applications in service (SCR-14).

A share says which applications are at one end of the portfolio, not whether any one of them
is too costly or too little used: that is for the defined bands of the scores (ADR-0012), and
a share never feeds a score. Each share is worked out from the applications the person may see
that have the figure it ranks by; cost is left out for anyone who may not see it.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.db.models import Application
from appwren.inventory import access, records
from appwren.inventory.registry import APPLICATION

IN_SERVICE = ("evaluating", "phase_in", "active", "containment", "phase_out")


def _share(
    key: str, label: str, definition: str, part: float, apps: list[Application],
    value: Callable[[Application], float | None], *, highest: bool, unit: str,
) -> dict[str, Any]:  # fmt: skip
    ranked = [(value(app), app) for app in apps]
    known = [(v, app) for v, app in ranked if v is not None]
    known.sort(key=lambda pair: (-pair[0] if highest else pair[0], pair[1].name))
    size = math.ceil(len(known) * part) if known else 0
    chosen = known[:size]
    return {
        "key": key, "label": label, "definition": definition, "unit": unit,
        "of": len(known), "not_known": len(ranked) - len(known),
        "threshold": chosen[-1][0] if chosen else None,
        "items": [{**records.chip(APPLICATION, app), "value": round(v, 2)} for v, app in chosen],
    }  # fmt: skip


def shares(session: Session, principal: Principal) -> dict[str, Any]:
    from appwren.landscape import costs

    apps = [
        app for app in session.scalars(
            select(Application).where(Application.status == "active",
                                      Application.lifecycle.in_(IN_SERVICE))
        )
        if access.sees_application(session, principal, app)
    ]  # fmt: skip
    costed = [app for app in apps if costs.sees_cost(session, principal, app)]
    on = today()

    def cost(app: Application) -> float | None:
        return float(app.annual_cost) if app.annual_cost is not None else None

    def per_user(app: Application) -> float | None:
        if app.annual_cost is None or not app.users:
            return None
        return app.annual_cost / app.users

    def users(app: Application) -> float | None:
        return float(app.users) if app.users is not None else None

    def age(app: Application) -> float | None:
        return (on - app.go_live).days / 365.25 if app.go_live else None

    return {
        "shares": [
            _share("costliest", "The costliest tenth", "The tenth of the applications in "
                   "service with an annual cost that cost the most a year.", 0.1, costed, cost,
                   highest=True, unit="a year"),
            _share("dearest_per_user", "The dearest tenth per user", "The tenth that cost the "
                   "most a year for each person who uses them.", 0.1, costed, per_user,
                   highest=True, unit="a year for each person"),
            _share("least_used", "The least used fifth", "The fifth of the applications in "
                   "service with a count of users that the fewest people use.", 0.2, apps, users,
                   highest=False, unit="people"),
            _share("oldest", "The oldest fifth", "The fifth that have been in use the longest.",
                   0.2, apps, age, highest=True, unit="years in use"),
        ],
        "cost_withheld": len(apps) - len(costed),
    }  # fmt: skip
