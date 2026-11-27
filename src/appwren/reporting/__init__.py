"""Where the portfolio stands, and what each person owes (CUR-01, CUR-02, RPT-02, RPT-03).

Every figure here is the length of a list. The dashboard does not have queries of its own:
each figure is the count of the portfolio narrowed by a filter, and carries that filter, so
the page can only ever open exactly what it counted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from appwren import decisions
from appwren.access import roles
from appwren.access.principal import Principal
from appwren.core.clock import today
from appwren.db.models import OrgUnit
from appwren.inventory import applications
from appwren.program import catalog, vocab

QUALITY = {
    "no_accountable": "Nobody accountable",
    "no_capability": "No capability",
    "no_assessment": "Never assessed",
    "assessment_expired": "Assessment expired",
    "low_confidence": "Low confidence",
    "not_confirmed": "Not confirmed in time",
    "missing_required": "Missing what its stage requires",
}
CONFIDENCE_BANDS = [
    (0, 49, "Under 50%"),
    (50, 69, "50 to 69%"),
    (70, 89, "70 to 89%"),
    (90, 100, "90% or more"),
]
NOT_IN_SERVICE = ("retired", "archived")
# Stored fields a figure narrows by, matched again on the rows already loaded.
STORED = ("lifecycle", "sourcing", "domain", "tier")
# What narrows a list beyond the stored fields, worked out from the scores.
COMPUTED = (
    "recommendation",
    "decision",
    "flag",
    "confidence_min",
    "confidence_max",
    "eol",
    "quality",
    "unit_only",
    "mismatch",
    "review_due",
    "decided",
    "in_service",
)


def rows(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The portfolio the person may see, narrowed by the stored fields in ``filters``, each
    row with what it lacks and how current its technology is."""
    stored = {key: value for key, value in filters.items() if key not in COMPUTED}
    found = decisions.portfolio(session, principal, stored, keep=True)
    stages = vocab.keys(session, "lifecycle", active_only=False)
    rules = catalog.stage_requirements(session)
    own = {item["key"] for item in catalog.fields(session)}
    threshold = found[0]["_result"]["thresholds"]["confidence"] if found else 70
    for row in found:
        result, app = row.pop("_result"), row.pop("_app")
        has = result["has"]
        missing = applications.missing_from(
            app,
            lambda name, has=has, app=app: (
                has[name] if name in has else applications.field_present(app, name, own)
            ),
            stages,
            rules,
        )
        currency = next(
            (
                f
                for f in result["dimensions"]["technical_health"]["factors"]
                if f["key"] == "currency"
            ),
            None,
        )
        level = currency["level"] if currency and currency["state"] == "known" else None
        row["eol"] = "past" if level == 1 else "ending" if level == 2 else None
        row["missing_now"] = missing["now"]
        row["quality"] = [
            key
            for key, true in (
                ("no_accountable", not has["accountable"]),
                ("no_capability", not has["capabilities"]),
                ("no_assessment", result["assessment"] is None),
                ("assessment_expired", bool(result["assessment"]) and not has["assessment"]),
                ("low_confidence", result["confidence"] < threshold),
                ("not_confirmed", result.get("stale") is not None),
                ("missing_required", bool(missing["now"])),
            )
            if true
        ]
    return found


def select(found: list[dict[str, Any]], filters: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The rows that match the computed filters. The same function narrows the dashboard's
    lists and counts its figures."""
    on = today().isoformat()
    out = []
    for row in found:
        value = filters.get
        if any(
            value(name) not in (None, "") and str(row.get(name)) != str(value(name))
            for name in STORED
        ):
            continue
        if value("in_service") in (True, "true") and row["lifecycle"] in NOT_IN_SERVICE:
            continue
        if value("recommendation") and row["recommendation"] != value("recommendation"):
            continue
        if value("decision"):
            wanted = None if value("decision") == "none" else value("decision")
            if row["decision"] != wanted:
                continue
        if value("flag") and value("flag") not in row["flags"]:
            continue
        if value("confidence_min") not in (None, "") and row["confidence"] < int(
            value("confidence_min")
        ):
            continue
        if value("confidence_max") not in (None, "") and row["confidence"] > int(
            value("confidence_max")
        ):
            continue
        if value("eol") and row["eol"] != value("eol"):
            continue
        if value("quality") and value("quality") not in row["quality"]:
            continue
        if value("unit_only") not in (None, "") and row["org_unit_id"] != int(value("unit_only")):
            continue
        if value("mismatch") not in (None, "") and row["mismatch"] != _true(value("mismatch")):
            continue
        if value("decided") not in (None, "") and (row["decision"] is not None) != _true(
            value("decided")
        ):
            continue
        if value("review_due") not in (None, ""):
            due = bool(row["review_on"] and str(row["review_on"]) < on)
            if due != _true(value("review_due")):
                continue
        out.append(row)
    return out


def _true(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def portfolio_list(
    session: Session, principal: Principal, filters: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return select(rows(session, principal, filters), filters)


# --- The dashboard ---------------------------------------------------------------------------


def _figure(label: str, found: list[dict[str, Any]], filters: dict[str, Any], **more: Any) -> dict:
    return {"label": label, "count": len(select(found, filters)), "filters": filters, **more}


def dashboard(session: Session, principal: Principal, base: Mapping[str, Any]) -> dict[str, Any]:
    """Where the portfolio stands, for the applications in service that the person may see.
    ``base`` narrows it by unit or domain; every figure's filters include it."""
    base = {key: value for key, value in base.items() if value not in (None, "")}
    base["in_service"] = "true"
    found = select(rows(session, principal, base), base)
    labels = {
        name: vocab.labels(session, name) for name in ("dispositions", "lifecycle", "sourcing")
    }

    def by(
        field: str, vocabulary: str, keys: list[str], extra: dict[str, Any] | None = None
    ) -> list:
        return [
            _figure(labels[vocabulary].get(key, key), found, {**base, field: key}, key=key)
            for key in keys
        ] + ([extra] if extra else [])

    dispositions = vocab.keys(session, "dispositions")
    counts = Counter(row["recommendation"] for row in found)
    flag_texts: dict[str, str] = {}
    flag_severity: dict[str, str] = {}
    from appwren import assessment

    for flag in assessment.current_model(session).definition.get("flags", []):
        flag_texts[flag["key"]] = flag["text"]
        flag_severity[flag["key"]] = flag["severity"]
    flag_texts["mismatch"] = "The decision on record differs from today's recommendation"
    flag_severity["mismatch"] = "info"
    flags = Counter(key for row in found for key in row["flags"])
    from appwren.landscape import costs

    return {
        "total": _figure("Applications in service", found, dict(base)),
        # What it all costs, for those who see every application's cost; None for the rest.
        "costs": costs.breakdown(session, principal, [row["id"] for row in found]),
        "headline": [
            _figure("Decided", found, {**base, "decided": "true"}),
            _figure("Mismatches", found, {**base, "mismatch": "true"}),
            _figure("Reviews due", found, {**base, "review_due": "true"}),
            _figure("Low confidence", found, {**base, "quality": "low_confidence"}),
            _figure("Past end of support", found, {**base, "eol": "past"}),
            _figure("Support ending within a year", found, {**base, "eol": "ending"}),
        ],
        "recommendations": [
            _figure(
                labels["dispositions"].get(key, key),
                found,
                {**base, "recommendation": key},
                key=key,
            )
            for key in dispositions
            if counts.get(key)
        ],
        "decisions": by(
            "decision",
            "dispositions",
            [key for key in dispositions if any(r["decision"] == key for r in found)],
            _figure("No decision yet", found, {**base, "decision": "none"}, key="none"),
        ),
        "lifecycle": by(
            "lifecycle",
            "lifecycle",
            [
                k
                for k in vocab.keys(session, "lifecycle", active_only=False)
                if any(r["lifecycle"] == k for r in found)
            ],
        ),
        "sourcing": by(
            "sourcing",
            "sourcing",
            [
                k
                for k in vocab.keys(session, "sourcing", active_only=False)
                if any(r["sourcing"] == k for r in found)
            ],
        ),
        "flags": [
            _figure(
                flag_texts.get(key, key),
                found,
                {**base, "flag": key},
                key=key,
                severity=flag_severity.get(key, "info"),
            )
            for key, _ in sorted(
                flags.items(),
                key=lambda item: (
                    {"danger": 0, "warning": 1, "info": 2}.get(
                        flag_severity.get(item[0], "info"), 3
                    ),
                    -item[1],
                ),
            )
        ],
        "confidence": [
            _figure(text, found, {**base, "confidence_min": low, "confidence_max": high})
            for low, high, text in CONFIDENCE_BANDS
        ],
    }


# --- Data quality ----------------------------------------------------------------------------


def data_quality(session: Session, principal: Principal, base: Mapping[str, Any]) -> dict:
    """How much of the portfolio can be trusted, by the unit that answers for each
    application. Each count opens its list."""
    base = {key: value for key, value in base.items() if value not in (None, "")}
    base["in_service"] = "true"
    found = select(rows(session, principal, base), base)
    names = {unit.id: unit.name for unit in session.query(OrgUnit)}
    by_unit: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for row in found:
        by_unit[row["org_unit_id"]].append(row)
    units = []
    for unit_id, _rows in sorted(by_unit.items(), key=lambda pair: names.get(pair[0] or 0, "")):
        scope = {**base, "unit_only": unit_id}
        units.append(
            {
                "unit": {"id": unit_id, "name": names.get(unit_id or 0, "No unit")},
                "total": _figure("Applications", found, scope),
                "issues": [
                    _figure(text, found, {**scope, "quality": key}, key=key)
                    for key, text in QUALITY.items()
                ],
            }
        )
    return {
        "total": _figure("Applications in service", found, dict(base)),
        "issues": [
            _figure(text, found, {**base, "quality": key}, key=key) for key, text in QUALITY.items()
        ],
        "units": units,
    }


# --- Home: what a person owes ----------------------------------------------------------------

SEVERITY = {"danger": 0, "warning": 1, "info": 2}


def owed(session: Session, principal: Principal) -> dict[str, Any]:
    """One list of what the person owes, most urgent first, and for those who decide or keep
    a unit, what is waiting in their scope."""
    found = rows(session, principal, {})
    found = [row for row in found if row["lifecycle"] not in NOT_IN_SERVICE]
    me = principal.account_id
    named = set()
    if me is not None:
        from sqlalchemy import select as sql_select

        from appwren.db.models import RecordOwner

        named = set(
            session.scalars(
                sql_select(RecordOwner.record_id).where(
                    RecordOwner.record_type == "application", RecordOwner.account_id == me
                )
            )
        )
    items: list[dict[str, Any]] = []

    def add(row: dict[str, Any], severity: str, kind: str, text: str, href: str) -> None:
        items.append(
            {
                "severity": severity,
                "kind": kind,
                "text": text,
                "href": href,
                "application": {"ref": row["ref"], "name": row["name"], "type": "application"},
            }
        )

    for row in found:
        if row["id"] not in named:
            continue
        ref = row["ref"]
        if "no_assessment" in row["quality"]:
            add(row, "warning", "assess", "Not assessed yet", f"/applications/{ref}/assess")
        elif "assessment_expired" in row["quality"]:
            add(
                row,
                "warning",
                "assess",
                "Its assessment has expired",
                f"/applications/{ref}/assess",
            )
        if "not_confirmed" in row["quality"]:
            add(
                row,
                "warning",
                "confirm",
                "Confirm that its record is right",
                f"/applications/{ref}",
            )
        for key in row["flags"]:
            if key in (
                "assessment_expired",
                "mismatch",
                "decision_review_due",
                "cost_review",
                "stale",
            ):
                continue
            severity = (
                "danger" if key in ("restricted_unsupported", "no_accountable") else "warning"
            )
            add(
                row,
                severity,
                "flag",
                row["flag_texts"].get(key, key),
                f"/applications/{ref}?tab=scores",
            )
        if row["missing_now"]:
            add(row, "info", "complete", _lacks(len(row["missing_now"])), f"/applications/{ref}")
    keeps = principal.units_for(roles.STEWARD, roles.MANAGER, roles.ARCHITECT)
    for row in found:
        if (
            "no_accountable" in row["quality"]
            and row["id"] not in named
            and (keeps is None or row["org_unit_id"] in keeps)
            and (principal.stewards or principal.manages_somewhere)
        ):
            add(
                row,
                "danger",
                "orphan",
                "Nobody is accountable for it",
                f"/applications/{row['ref']}",
            )
    decides = principal.units_for(roles.LEADER, roles.MANAGER)
    waiting = []
    if principal.leads or principal.manages_somewhere:
        for row in found:
            if decides is not None and row["org_unit_id"] not in decides:
                continue
            on = today().isoformat()
            if row["review_on"] and str(row["review_on"]) < on:
                waiting.append({**_chip(row), "why": "Decision due for review"})
            elif row["mismatch"]:
                waiting.append({**_chip(row), "why": "Decision differs from the recommendation"})
            elif not row["decision"] and row["recommendation"] not in (None, "assess", "incubate"):
                waiting.append({**_chip(row), "why": "No decision yet"})
    from appwren.oversight import campaigns

    asked_for = campaigns.owed(session, principal)
    # What a campaign asks is said once: as the campaign's, with its date.
    by_campaign = {(a["application"]["ref"], a["kind"]) for a in asked_for}
    items = [
        item
        for item in items
        if not (
            (item["kind"] == "confirm" and (item["application"]["ref"], "confirm") in by_campaign)
            or (item["kind"] == "assess" and (item["application"]["ref"], "assess") in by_campaign)
        )
    ]
    for asked in asked_for:
        verb = "Assess it" if asked["kind"] == "assess" else "Confirm that its record is right"
        items.append(
            {
                "severity": "danger" if asked["late"] else "warning",
                "kind": "campaign",
                "text": f"{verb}, for {asked['campaign']['name']}, "
                f"by {asked['due_on'].isoformat()}",
                "href": asked["href"],
                "application": asked["application"],
            }
        )
    from appwren.oversight import tasks

    for task in tasks.owed(session, principal):
        items.append(
            {
                "severity": "danger" if task["late"] else "warning",
                "kind": "task",
                "text": f"{task['title']}, by {task['due_on'].isoformat()}",
                "href": f"/tasks/{task['id']}",
                "application": task["about"] or {"ref": "", "name": "", "type": "task"},
            }
        )
    from appwren.oversight import contests

    for contest in contests.waiting(session, principal):
        items.append(
            {
                "severity": "warning",
                "kind": "contest",
                "text": f"{contest['raised_by']} contests {contest['factor_label'].lower()}",
                "href": f"/applications/{contest['application']['ref']}?tab=scores",
                "application": contest["application"],
            }
        )
    items.sort(key=lambda item: (SEVERITY.get(item["severity"], 3), item["application"]["name"]))
    return {
        "items": items,
        "waiting": waiting[:50],
        "waiting_total": len(waiting),
        "named": len(named),
    }


def _lacks(count: int) -> str:
    return f"Its record lacks {count} thing{'s' if count != 1 else ''} its stage requires"


def _chip(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ref": row["ref"],
        "name": row["name"],
        "type": "application",
        "recommendation": row["recommendation"],
        "decision": row["decision"],
    }
