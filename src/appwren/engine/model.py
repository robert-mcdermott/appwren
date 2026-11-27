"""A scoring model as data: checking it whole, and resolving a profile's factors.

A model holds the dimensions, the profiles (each with its factors, weights, bands, floors, and
the condition that chooses it), the thresholds, the cadence, the recommendation rules, the
guardrails, and the flags (spec/engine.md). Everything wrong with a model is reported in one
pass, so a model that cannot be used is never published.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from appwren.core import conditions

KINDS = ("answer", "choice", "band", "computed")
COMPUTED = (
    "technology_currency",
    "capability_uniqueness",
    "dependents",
    "data_exposure",
    "eol_exposure",
    "continuity",
)
DIMENSIONS = ("business_value", "technical_health", "cost_burden", "risk_exposure")
DISPOSITIONS = (
    "invest", "maintain", "tolerate", "modernize", "replace", "consolidate", "retire",
    "incubate", "assess",
)  # fmt: skip
THRESHOLDS = ("value", "health", "cost", "confidence", "thin")
# The facts a condition may look at, by their first part.
FACTS = {
    "lifecycle", "sourcing", "vendor_sourced", "purpose", "pace", "domain", "tier", "users",
    "maintainers", "annual_cost", "sign_in", "monitoring", "backup", "data_classes",
    "sensitivity", "funding", "grant_ends_in_days", "research_continuity", "regulated_record",
    "records_retention", "external_users", "age_months", "dependents", "sole_provider",
    "accountable", "assessment_expired", "decided_within_year", "decision",
    "decision_review_due", "enough", "overlap", "high", "level", "score", "coverage",
    "confidence", "recommendation", "answer", "cost_per_user", "licensed", "license_use",
    "contract_notice_in_days", "data_agreement_missing",
}  # fmt: skip


def resolve(model: Mapping[str, Any], key: str) -> dict[str, Any]:
    """A profile with everything it inherits filled in: its factors by dimension, with the
    weights it changes, and its floors."""
    profiles = {profile["key"]: profile for profile in model["profiles"]}
    profile = profiles[key]
    if "extends" not in profile:
        return {
            "key": key,
            "label": profile.get("label", key),
            "factors": copy.deepcopy(profile.get("factors", {})),
            "floors": copy.deepcopy(profile.get("floors", {})),
        }
    base = resolve(model, profile["extends"])
    for dimension, weights in (profile.get("weights") or {}).items():
        for factor in base["factors"].get(dimension, []):
            if factor["key"] in weights:
                factor["weight"] = weights[factor["key"]]
    if "floors" in profile:
        base["floors"] = copy.deepcopy(profile["floors"])
    return {**base, "key": key, "label": profile.get("label", key)}


def choose(model: Mapping[str, Any], facts: Mapping[str, Any]) -> str:
    """The first profile whose condition holds; the last has none."""
    for profile in model["profiles"]:
        if conditions.evaluate(profile.get("when"), facts):
            return str(profile["key"])
    return str(model["profiles"][-1]["key"])


def _check_conditions(condition: Any, where: str) -> list[str]:
    found = conditions.problems(condition, where=where)
    if found:
        return found
    unknown = sorted(
        field for field in conditions.fields(condition) if field.split(".")[0] not in FACTS
    )
    return [f"{where}: {field} is not a fact the engine knows" for field in unknown]


def _check_factor(factor: Any, where: str, questions: set[str]) -> list[str]:
    found: list[str] = []
    if not isinstance(factor, Mapping) or not factor.get("key"):
        return [f"{where}: every factor needs a key"]
    where = f"{where} {factor['key']}"
    kind = factor.get("kind")
    if kind not in KINDS:
        found.append(f"{where}: the kind must be one of {', '.join(KINDS)}")
    weight = factor.get("weight")
    if not isinstance(weight, int | float) or isinstance(weight, bool) or weight <= 0:
        found.append(f"{where}: needs a weight above 0")
    if kind == "answer" and factor.get("question") not in questions:
        found.append(f"{where}: asks a question that is not in the questionnaire")
    if kind == "choice":
        mapping = factor.get("map")
        if not factor.get("fact") or not isinstance(mapping, Mapping) or not mapping:
            found.append(f"{where}: a choice needs a fact and a map from its values to levels")
        elif not all(isinstance(v, int) and 1 <= v <= 5 for v in mapping.values()):
            found.append(f"{where}: every level in the map must be 1 to 5")
    if kind == "band":
        bands = factor.get("bands")
        if not factor.get("fact") or not isinstance(bands, list) or len(bands) != 4:
            found.append(f"{where}: a band needs a fact and four boundaries")
        elif any(not isinstance(b, int | float) for b in bands) or bands != sorted(set(bands)):
            found.append(f"{where}: the boundaries of a band must rise")
        if factor.get("direction") not in ("rising", "falling"):
            found.append(f"{where}: a band is rising or falling")
    if kind == "computed" and factor.get("compute") not in COMPUTED:
        found.append(f"{where}: there is no computed factor called {factor.get('compute')}")
    if "applies" in factor:
        found += _check_conditions(factor["applies"], f"{where} applies")
    return found


def problems(model: Any, questions: set[str]) -> list[str]:
    """Everything wrong with a scoring model, in one pass. ``questions`` are the keys of the
    questionnaire it is used with."""
    if not isinstance(model, Mapping):
        return ["The scoring model is not a set of definitions."]
    found: list[str] = []
    thresholds = model.get("thresholds") or {}
    for name in THRESHOLDS:
        if not isinstance(thresholds.get(name), int | float):
            found.append(f"The threshold for {name} is missing.")
    for name in ("value", "health", "cost"):
        if isinstance(thresholds.get(name), int | float) and not 1 <= thresholds[name] <= 5:
            found.append(f"The threshold for {name} must be between 1 and 5.")
    for name in ("confidence", "thin"):
        if isinstance(thresholds.get(name), int | float) and not 0 <= thresholds[name] <= 100:
            found.append(f"The threshold for {name} is a percentage.")
    profiles = model.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        return [*found, "The model needs at least one profile."]
    keys = [profile.get("key") for profile in profiles if isinstance(profile, Mapping)]
    if len(keys) != len(set(keys)):
        found.append("A profile key appears twice.")
    if profiles[-1].get("when"):
        found.append(
            "The last profile is the one that applies when no other does; it has no condition."
        )
    for profile in profiles:
        where = f"Profile {profile.get('key')}"
        if profile.get("extends") is not None and profile["extends"] not in keys:
            found.append(f"{where} extends a profile that is not there.")
            continue
        found += _check_conditions(profile.get("when"), f"{where} condition")
        try:
            resolved = resolve(model, profile["key"])
        except (KeyError, RecursionError):
            found.append(f"{where} cannot be resolved.")
            continue
        for dimension in DIMENSIONS:
            factors = resolved["factors"].get(dimension)
            if not factors:
                found.append(f"{where} has no factors for {dimension}.")
                continue
            seen = [factor.get("key") for factor in factors]
            if len(seen) != len(set(seen)):
                found.append(f"{where}: a factor appears twice in {dimension}.")
            for factor in factors:
                found += _check_factor(factor, f"{where} {dimension}", questions)
            total = sum(
                factor.get("weight", 0) for factor in factors if isinstance(factor, Mapping)
            )
            if total != 100:
                found.append(f"{where}: the weights of {dimension} add up to {total}, not 100.")
        for dimension, floors in (resolved.get("floors") or {}).items():
            for index, floor in enumerate(floors):
                found += _check_conditions(
                    floor.get("when"), f"{where} {dimension} floor {index + 1}"
                )
                if not isinstance(floor.get("level"), int | float) or not 1 <= floor["level"] <= 5:
                    found.append(f"{where} floor {index + 1}: its level must be 1 to 5.")
    rules = model.get("rules") or []
    if not rules:
        found.append("The model needs recommendation rules.")
    for rule in rules:
        where = f"Rule {rule.get('key')}"
        found += _check_conditions(rule.get("when"), f"{where} condition")
        branches = rule.get("then") or [rule]
        for branch in branches:
            if branch is not rule:
                found += _check_conditions(branch.get("when"), f"{where} branch")
            if branch.get("recommend") is not None and branch["recommend"] not in DISPOSITIONS:
                found.append(
                    f"{where} recommends {branch['recommend']}, which is not a disposition."
                )
    for guardrail in model.get("guardrails") or []:
        where = f"Guardrail {guardrail.get('key')}"
        found += _check_conditions(guardrail.get("when"), f"{where} condition")
        if guardrail.get("change_to") not in DISPOSITIONS:
            found.append(f"{where} changes to something that is not a disposition.")
    for flag in model.get("flags") or []:
        where = f"Flag {flag.get('key')}"
        if flag.get("by_rule"):
            if flag.get("when"):
                found.append(f"{where} is raised by a rule, so it has no condition of its own.")
        elif not flag.get("when"):
            found.append(f"{where} needs a condition, or to be raised by a rule.")
        else:
            found += _check_conditions(flag.get("when"), f"{where} condition")
        if flag.get("severity") not in ("danger", "warning", "info"):
            found.append(f"{where}: severity is danger, warning, or info.")
        if not flag.get("text"):
            found.append(f"{where} needs words.")
    return found


def months_current(model: Mapping[str, Any], tier: int | None) -> int:
    """How long an assessment stays current for an application of this tier."""
    cadence = model.get("cadence") or {}
    by_tier = cadence.get("assessment_months") or {}
    return int(by_tier.get(str(tier), cadence.get("default_months", 24)))
