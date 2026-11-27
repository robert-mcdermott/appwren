"""From facts to scores, confidence, a recommendation, and flags, with the working.

Pure functions: facts and a scoring model in, a result out. Nothing here reads the database,
so the worked example in spec/engine.md is a test of exactly this module.

Every factor ends in one of three states: *known* (it has a level from 1 to 5), *unknown*
(it applies, but nothing is known: left out of the score and counted against confidence),
or *not applicable* (left out of both).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from appwren.core import conditions
from appwren.engine import model as models

KNOWN, UNKNOWN, NOT_APPLICABLE = "known", "unknown", "not_applicable"
YEAR_DAYS = 365
# What a person can do to supply an unknown factor, by the fact or kind it comes from.
WHERE = {
    "answer": "assessment",
    "technology_currency": "components",
    "capability_uniqueness": "capabilities",
    "data_exposure": "data_classes",
    "eol_exposure": "components",
    "continuity": "backup",
}
BUILT_IN_FLAGS = {
    "mismatch": ("info", "The decision on record differs from today's recommendation"),
    "stale": ("warning", "Nobody has confirmed its record in time"),
}


def round1(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def whole(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def band_level(value: float, bands: list[float], direction: str) -> int:
    """Four rising boundaries make five levels. Below the first is 1 when rising (5 when
    falling); at or above the last is 5 (1 when falling)."""
    position = sum(1 for boundary in bands if value >= boundary)
    return position + 1 if direction == "rising" else 5 - position


# --- Computed factors ---------------------------------------------------------------------------


def release_state(item: Mapping[str, Any], today: date) -> str:
    ends, extended = item.get("support_ends"), item.get("extended_ends")
    if ends is None:
        return "unknown"
    if ends < today:
        return "extended" if extended is not None and extended >= today else "ended"
    return "ending" if (ends - today).days <= YEAR_DAYS else "supported"


def technology_currency(facts: Mapping[str, Any], today: date) -> tuple[str, int | None, str]:
    technologies = facts.get("technologies") or []
    if not technologies:
        if facts.get("vendor_sourced") and not facts.get("has_components"):
            return NOT_APPLICABLE, None, "The vendor runs the technology it is built on"
        return UNKNOWN, None, "No technologies are recorded on its components"
    states = [(item, release_state(item, today)) for item in technologies]
    ended = [item for item, state in states if state == "ended"]
    if ended:
        return KNOWN, 1, f"Past end of support: {_names(ended)}"
    ending = [item for item, state in states if state in ("ending", "extended")]
    if ending:
        return KNOWN, 2, f"End of support within a year, or on extended support: {_names(ending)}"
    held = [item for item, _ in states if item.get("radar") == "hold"]
    undated = [item for item, state in states if state == "unknown"]
    note = f"; no support dates for {_names(undated)}" if undated else ""
    if held:
        return KNOWN, 3, f"All supported, but on hold for new work: {_names(held)}{note}"
    if all(item.get("radar") == "adopt" for item, _ in states):
        return KNOWN, 5, f"All {len(states)} supported, and every one is Adopt{note}"
    return KNOWN, 4, f"All {len(states)} supported{note}"


def _names(items: list[Mapping[str, Any]]) -> str:
    return ", ".join(
        f"{item['name']} {item['release']}" if item.get("release") else str(item["name"])
        for item in items
    )


def capability_uniqueness(facts: Mapping[str, Any]) -> tuple[str, int | None, str]:
    capabilities = facts.get("capabilities") or []
    if not capabilities:
        return UNKNOWN, None, "No capability is recorded"
    best, why = 0, ""
    for item in capabilities:
        if item.get("others", 0) == 0:
            level, said = 5, f"The only active application for {item['name']}"
        elif item.get("primary") == "self":
            level, said = 4, f"The primary provider of {item['name']}, which others also serve"
        elif item.get("primary") is None:
            level, said = 3, f"One of several for {item['name']}, with no primary named"
        else:
            level, said = 2, f"One of several for {item['name']}, where another is the primary"
        if level > best:
            best, why = level, said
    return KNOWN, best, why


def dependents(facts: Mapping[str, Any]) -> tuple[str, int | None, str]:
    count = int(facts.get("dependents") or 0)
    if count == 0:
        return NOT_APPLICABLE, None, "Nothing is recorded as depending on it"
    level = 3 if count == 1 else 4 if count <= 4 else 5
    return KNOWN, level, f"{count} active application{'s' if count != 1 else ''} depend on it"


# Data exposure: sensitivity against the sign-in level (spec/engine.md).
EXPOSURE = {
    0: {5: 5, 4: 5, 3: 5, 2: 5, 1: 5},
    1: {5: 5, 4: 5, 3: 5, 2: 4, 1: 4},
    2: {5: 4, 4: 4, 3: 3, 2: 2, 1: 2},
    3: {5: 4, 4: 3, 3: 2, 2: 1, 1: 1},
}
SENSITIVITY = {0: "public", 1: "internal", 2: "confidential", 3: "restricted"}


def data_exposure(facts: Mapping[str, Any], sign_in: int | None) -> tuple[str, int | None, str]:
    sensitivity = facts.get("sensitivity")
    if sensitivity is None:
        return UNKNOWN, None, "The data it handles is not recorded"
    if sensitivity == 0:
        return KNOWN, 5, "It handles only public data"
    if facts.get("sign_in") is None:
        return UNKNOWN, None, "How people sign in is not recorded"
    level_in = sign_in if sign_in is not None else 1  # no sign-in at all is the weakest
    level = EXPOSURE[int(sensitivity)][level_in]
    return (
        KNOWN,
        level,
        f"{SENSITIVITY[int(sensitivity)].capitalize()} data, sign-in level {level_in}",
    )


def eol_exposure(
    facts: Mapping[str, Any], currency: tuple[str, int | None, str]
) -> tuple[str, int | None, str]:
    state, level, _ = currency
    if state != KNOWN or level is None:
        return state, None, "Follows technology currency, which is not known"
    if level >= 4:
        return KNOWN, 5, "Its technology is supported"
    if level == 3:
        return KNOWN, 4, "Supported, but on technology held for new work"
    sensitivity = facts.get("sensitivity")
    if sensitivity is None:
        return UNKNOWN, None, "Its technology is near or past its end, and its data is not recorded"
    sensitive = sensitivity >= 2
    if level == 2:
        return (
            KNOWN,
            2 if sensitive else 3,
            "Support ends within a year"
            + (", and it handles confidential or restricted data" if sensitive else ""),
        )
    return (
        KNOWN,
        1 if sensitive else 2,
        "Past end of support" + (", with confidential or restricted data" if sensitive else ""),
    )


def continuity(facts: Mapping[str, Any], today: date) -> tuple[str, int | None, str]:
    backup = facts.get("backup")
    if backup is None:
        return UNKNOWN, None, "Backup is not recorded"
    tested_on = facts.get("last_restore_test")
    if backup == "tested" and (tested_on is None or (today - tested_on).days > YEAR_DAYS):
        backup = "unverified"
    tier = facts.get("tier") or 3
    critical = tier <= 2
    level = {
        "tested": 5,
        "vendor": 4,
        "unverified": 2 if critical else 4,
        "none": 1 if critical else 3,
    }.get(backup)
    if level is None:
        return NOT_APPLICABLE, None, "Its backup is of no kind the model knows"
    words = {
        "tested": "Restore tested within a year",
        "vendor": "Backed up by the vendor",
        "unverified": "Backed up, but no restore tested in a year",
        "none": "No backup",
    }
    return KNOWN, level, f"{words[backup]}; tier {tier}"


# --- One factor ---------------------------------------------------------------------------------


def factor_result(
    factor: Mapping[str, Any],
    facts: Mapping[str, Any],
    today: date,
    computed: dict[str, tuple[str, int | None, str]],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": factor["key"],
        "label": factor.get("label", factor["key"]),
        "kind": factor["kind"],
        "weight": factor["weight"],
        "level": None,
        "value": None,
    }
    if "applies" in factor and not conditions.evaluate(factor["applies"], facts):
        return {**out, "state": NOT_APPLICABLE, "why": "Does not apply to this application"}
    kind = factor["kind"]
    if kind == "answer":
        key = factor["question"]
        answers = facts.get("answer") or {}
        level = answers.get(key)
        if level is None:
            why = (
                "The assessment's answers have expired"
                if facts.get("assessment_expired")
                else "Not answered, or answered Don't know"
            )
            return {**out, "state": UNKNOWN, "why": why, "where": "assessment"}
        return {**out, "state": KNOWN, "level": int(level), "value": int(level),
                "why": "Answered in the assessment", "source": "assessment"}  # fmt: skip
    if kind == "signal":
        signal = (facts.get("signals") or {}).get(factor["signal"])
        if signal is None:
            return {**out, "state": NOT_APPLICABLE, "why": "No source supplies it"}
        value, source = signal["value"], signal["from"]
        if "map" in factor:
            level = factor["map"].get(str(value))
            if level is None:
                return {**out, "state": NOT_APPLICABLE, "value": value, "from": source,
                        "why": f"{value} has no level"}  # fmt: skip
            said = signal.get("said") or str(value)
        else:
            level = band_level(float(value), factor["bands"], factor["direction"])
            said = f"{value:,} {factor.get('unit', '')}".strip()
        return {**out, "state": KNOWN, "level": level, "value": value, "source": "signal",
                "from": source, "why": f"{said}, from {source}"}  # fmt: skip
    sourced = (facts.get("sources") or {}).get(factor.get("fact", ""))
    if sourced:
        out["from"] = sourced
    if kind == "choice":
        value = facts.get(factor["fact"])
        if value is None:
            return {**out, "state": UNKNOWN, "why": "Not recorded", "where": factor["fact"]}
        level = factor["map"].get(str(value))
        if level is None:
            return {**out, "state": NOT_APPLICABLE, "value": value,
                    "why": f"{value} has no level", "source": factor["fact"]}  # fmt: skip
        return {**out, "state": KNOWN, "level": level, "value": value,
                "why": "From what is recorded", "source": factor["fact"]}  # fmt: skip
    if kind == "band":
        value = facts.get(factor["fact"])
        if value is None:
            # A figure worked out from others is entered where the first one missing is.
            needs = [name for name in factor.get("needs", []) if facts.get(name) is None]
            where = needs[0] if needs else factor["fact"]
            return {**out, "state": UNKNOWN, "why": "Not recorded", "where": where}
        level = band_level(float(value), factor["bands"], factor["direction"])
        bands = ", ".join(f"{b:,}" for b in factor["bands"])
        return {**out, "state": KNOWN, "level": level, "value": value, "source": factor["fact"],
                "why": f"{value:,} {factor.get('unit', '')}".strip()
                + f": bands {bands} ({factor['direction']})"}  # fmt: skip
    # computed
    state, level, why = computed[factor["compute"]]
    found = {**out, "state": state, "level": level, "why": why, "source": "computed"}
    if state == UNKNOWN:
        found["where"] = WHERE.get(factor["compute"], factor["compute"])
    return found


def _computed(facts: Mapping[str, Any], today: date, sign_in_level: int | None) -> dict:
    currency = technology_currency(facts, today)
    return {
        "technology_currency": currency,
        "capability_uniqueness": capability_uniqueness(facts),
        "dependents": dependents(facts),
        "data_exposure": data_exposure(facts, sign_in_level),
        "eol_exposure": eol_exposure(facts, currency),
        "continuity": continuity(facts, today),
    }


def _sign_in_level(profile: Mapping[str, Any], facts: Mapping[str, Any]) -> int | None:
    for factor in profile["factors"].get("technical_health", []):
        if factor["kind"] == "choice" and factor.get("fact") == "sign_in":
            value = facts.get("sign_in")
            return factor["map"].get(str(value)) if value is not None else None
    return None


# --- The whole --------------------------------------------------------------------------------


def evaluate(facts: Mapping[str, Any], model: Mapping[str, Any], *, today: date) -> dict[str, Any]:
    """Score one application. ``facts`` are as gathered by the assessment service."""
    facts = dict(facts)
    thresholds = model["thresholds"]
    profile = models.resolve(model, models.choose(model, facts))
    computed = _computed(facts, today, _sign_in_level(profile, facts))
    facts["sole_provider"] = any(
        item.get("others", 0) == 0 for item in facts.get("capabilities") or []
    )
    dimensions: dict[str, dict[str, Any]] = {}
    levels: dict[str, int] = {}
    missing: list[dict[str, Any]] = []
    for spec in model["dimensions"]:
        key = spec["key"]
        factors = [factor_result(f, facts, today, computed) for f in profile["factors"][key]]
        known = [f for f in factors if f["state"] == KNOWN]
        applicable = [f for f in factors if f["state"] != NOT_APPLICABLE]
        known_weight = sum(Decimal(str(f["weight"])) for f in known)
        applicable_weight = sum(Decimal(str(f["weight"])) for f in applicable)
        total = sum(Decimal(str(f["weight"])) * f["level"] for f in known)
        raw = total / known_weight if known_weight else None
        score = round1(raw) if raw is not None else None
        floor = None
        for rule in profile.get("floors", {}).get(key, []):
            if (
                conditions.evaluate(rule["when"], facts)
                and score is not None
                and score < rule["level"]
            ):
                floor = {"level": float(rule["level"]), "reason": rule["reason"], "was": score}
                score = float(rule["level"])
                break
        coverage = whole(known_weight * 100 / applicable_weight) if applicable_weight else 100
        dimensions[key] = {
            "key": key,
            "label": spec["label"],
            "score": score,
            "raw": float(raw) if raw is not None else None,
            "sum": float(total),
            "known_weight": float(known_weight),
            "applicable_weight": float(applicable_weight),
            "coverage": coverage,
            "thin": coverage < thresholds["thin"] or score is None,
            "floor": floor,
            "factors": factors,
        }
        for f in factors:
            if f["state"] == KNOWN:
                levels[f["key"]] = f["level"]
            elif f["state"] == UNKNOWN:
                missing.append({"dimension": key, "factor": f["key"], "label": f["label"],
                                "weight": f["weight"], "why": f["why"],
                                "where": f.get("where")})  # fmt: skip
    confidence = whole(
        sum(Decimal(d["coverage"]) for d in dimensions.values()) / Decimal(len(dimensions))
    )
    # A record nobody has confirmed in time is trusted less, whatever it says (CUR-03).
    stale = None
    if facts.get("stale"):
        penalty = models.stale_penalty(model)
        stale = {
            "penalty": penalty,
            "from": confidence,
            "due": facts.get("confirm_due"),
            "confirmed_on": facts.get("confirmed_on"),
        }
        confidence = max(0, confidence - penalty)
    bv = dimensions["business_value"]
    th = dimensions["technical_health"]
    cb = dimensions["cost_burden"]

    def at_least(score: float | None, threshold: float) -> bool | None:
        return None if score is None else score >= threshold

    peer = facts.get("peer")
    context = {
        **facts,
        "score": {key: d["score"] for key, d in dimensions.items()},
        "coverage": {key: d["coverage"] for key, d in dimensions.items()},
        "confidence": confidence,
        "level": levels,
        "high": {
            "value": at_least(bv["score"], thresholds["value"]),
            "health": at_least(th["score"], thresholds["health"]),
            "cost": at_least(cb["score"], thresholds["cost"]),
        },
        "enough": confidence >= thresholds["confidence"] and not bv["thin"] and not th["thin"],
        "overlap": bool(
            peer
            and peer.get("bv") is not None
            and bv["score"] is not None
            and bv["score"] < peer["bv"]
        ),
    }
    recommendation, fired, raised = None, None, []
    for rule in model["rules"]:
        if not conditions.evaluate(rule.get("when"), context):
            continue
        branch = next(
            (b for b in rule.get("then") or [rule]
             if b is rule or conditions.evaluate(b.get("when"), context)),
            None,
        )  # fmt: skip
        if branch is None:
            continue
        recommendation = branch.get("recommend")
        fired = {"key": rule["key"], "label": rule.get("label", rule["key"])}
        if branch.get("flag"):
            raised.append(branch["flag"])
        break
    guardrail = None
    for rule in model.get("guardrails") or []:
        if conditions.evaluate(rule["when"], {**context, "recommendation": recommendation}):
            guardrail = {"key": rule["key"], "label": rule.get("label", rule["key"]),
                         "from": recommendation, "to": rule["change_to"],
                         "reason": rule.get("reason")}  # fmt: skip
            recommendation = rule["change_to"]
    flags = []
    flag_specs = {flag["key"]: flag for flag in model.get("flags") or []}
    final = {**context, "recommendation": recommendation}
    for flag in model.get("flags") or []:
        if flag.get("by_rule"):
            if flag["key"] in raised:
                flags.append(
                    {"key": flag["key"], "severity": flag["severity"], "text": flag["text"]}
                )
        elif conditions.evaluate(flag.get("when"), final):
            flags.append({"key": flag["key"], "severity": flag["severity"], "text": flag["text"]})
    for key in raised:
        if key not in flag_specs:
            flags.append(
                {"key": key, "severity": "info", "text": key.replace("_", " ").capitalize()}
            )
    decision = facts.get("decision")
    if decision and recommendation and decision != recommendation:
        severity, text = BUILT_IN_FLAGS["mismatch"]
        flags.append({"key": "mismatch", "severity": severity, "text": text})
    if stale is not None:
        severity, text = BUILT_IN_FLAGS["stale"]
        flags.append({"key": "stale", "severity": severity, "text": text})
    order = {"danger": 0, "warning": 1, "info": 2}
    flags.sort(key=lambda item: order.get(item["severity"], 3))
    missing.sort(key=lambda item: -item["weight"])
    if stale is not None:
        since = stale["confirmed_on"]
        missing.insert(0, {
            "dimension": None, "factor": "confirm", "label": "Confirm the record",
            "weight": stale["penalty"],
            "why": (f"Last confirmed on {since.isoformat()}" if since else "Never confirmed")
            + f"; it was due by {stale['due'].isoformat()}. Confirming it gives back "
            f"{stale['penalty']} points.",
            "where": "confirm",
        })  # fmt: skip
    return {
        "profile": {"key": profile["key"], "label": profile["label"]},
        "dimensions": dimensions,
        "scores": {key: d["score"] for key, d in dimensions.items()},
        "confidence": confidence,
        "stale": stale,
        "thresholds": dict(thresholds),
        "recommendation": recommendation,
        "rule": fired,
        "guardrail": guardrail,
        "overlap_with": peer if context["overlap"] else None,
        "flags": flags,
        "missing": missing,
    }
