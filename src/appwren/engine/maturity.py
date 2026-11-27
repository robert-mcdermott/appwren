"""Engineering maturity as the program defines it: the checks there are, and the levels they
make (SCR-12). Measured against records in ``appwren.inventory.maturity``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CHECKS: dict[str, str] = {
    "monitoring": "Monitoring",
    "backups": "Backups",
    "documentation": "Documentation",
    "tests": "Tests",
    "ci": "Continuous integration",
    "dependency_updates": "Automated dependency updates",
    "no_critical_alerts": "No open critical dependency alert",
}
CODE_CHECKS = {"tests", "ci", "dependency_updates", "no_critical_alerts"}
DEFAULT = {
    "levels": [
        {"key": "bronze", "label": "Bronze", "checks": ["monitoring", "backups", "documentation"]},
        {"key": "silver", "label": "Silver", "checks": ["tests", "ci"]},
        {"key": "gold", "label": "Gold", "checks": ["dependency_updates", "no_critical_alerts"]},
    ]
}
NONE = "none"  # below the first level


def levels(model: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The levels, lowest first, each with only the checks it adds."""
    found = (model or {}).get("maturity") or DEFAULT
    return [dict(level) for level in found["levels"]]


def problems(maturity: Any) -> list[str]:
    """Everything wrong with a model's maturity levels."""
    if maturity is None:
        return []
    if not isinstance(maturity, Mapping) or not isinstance(maturity.get("levels"), list):
        return ["The maturity levels must be a list."]
    found: list[str] = []
    keys: list[str] = []
    seen: set[str] = set()
    if not 1 <= len(maturity["levels"]) <= 5:
        found.append("Give 1 to 5 maturity levels.")
    for level in maturity["levels"]:
        if not isinstance(level, Mapping) or not level.get("key") or not level.get("label"):
            found.append("Every maturity level needs a key and a label.")
            continue
        keys.append(str(level["key"]))
        for check in level.get("checks") or []:
            if check not in CHECKS:
                found.append(f"The maturity level {level['key']} has no check called {check}.")
            elif check in seen:
                found.append(f"The check {check} is in more than one maturity level.")
            seen.add(check)
        if not level.get("checks"):
            found.append(f"The maturity level {level['key']} needs at least one check.")
    if len(set(keys)) != len(keys) or NONE in keys:
        found.append("Each maturity level needs a key of its own, and none may be called none.")
    return found


def ranks(model: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """Every level, lowest first, with the one below the first: (key, label)."""
    chain = levels(model)
    return [
        (NONE, "Below " + chain[0]["label"].lower()),
        *[(lv["key"], lv["label"]) for lv in chain],
    ]
