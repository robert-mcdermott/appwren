"""The engine on its own: facts and the default model in, scores and their working out
(spec/engine.md). No database."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

import pytest

from appwren.engine import evaluate, problems, resolve
from appwren.engine.score import KNOWN, NOT_APPLICABLE, UNKNOWN, band_level, round1
from appwren.program import vocab

TODAY = date(2026, 11, 26)
PACK = vocab.default_pack()
MODEL = PACK["scoring"]
QUESTIONS = {q["key"] for s in PACK["questionnaire"]["sections"] for q in s["questions"]}


def worked_example() -> dict[str, Any]:
    """*Specimen Tracker*, exactly as spec/engine.md describes it."""
    return {
        "lifecycle": "active",
        "sourcing": "built_here",
        "vendor_sourced": False,
        "purpose": "mission",
        "pace": "steady",
        "tier": 2,
        "users": 380,
        "maintainers": 1,
        "annual_cost": 60_000,
        "cost_per_user": 158,  # 60,000 over 380 people
        "licensed": False,
        "sign_in": "sso",
        "monitoring": "metrics",
        "backup": "unverified",
        "data_classes": ["identifiable_research"],
        "sensitivity": 3,
        "funding": "grant",
        "grant_ends_in_days": 240,
        "accountable": True,
        "decided_within_year": False,
        "has_components": True,
        "dependents": 3,
        "age_months": 80,
        "technologies": [
            {
                "name": "Python",
                "release": "3.9",
                "radar": "adopt",
                "support_ends": date(2025, 10, 31),
            }
        ],
        "capabilities": [
            {"ref": "CAP-0010", "name": "Biospecimen tracking", "others": 0, "primary": "self"}
        ],
        "answer": {
            "strategic_fit": 4,
            "functional_fit": 3,
            "future_need": 4,
            "reliability": 3,
            "maintainability": 2,
            "support_effort": 2,
            "change_effort": 2,
        },
    }


def run(**changes: Any) -> dict[str, Any]:
    return evaluate({**worked_example(), **changes}, MODEL, today=TODAY)


def factor(result: dict[str, Any], dimension: str, key: str) -> dict[str, Any]:
    return next(f for f in result["dimensions"][dimension]["factors"] if f["key"] == key)


def test_the_default_model_is_sound() -> None:
    assert problems(MODEL, QUESTIONS) == []
    for profile in MODEL["profiles"]:
        resolved = resolve(MODEL, profile["key"])
        for dimension, factors in resolved["factors"].items():
            assert sum(f["weight"] for f in factors) == 100, (profile["key"], dimension)


def test_the_worked_example_gives_exactly_the_figures_in_the_spec() -> None:
    result = run()
    assert result["profile"]["key"] == "standard"
    assert result["scores"] == {
        "business_value": 4.1,
        "technical_health": 2.5,
        "cost_burden": 2.7,
        "risk_exposure": 2.1,
    }
    dims = result["dimensions"]
    assert (dims["business_value"]["sum"], dims["business_value"]["known_weight"]) == (405, 100)
    assert (dims["technical_health"]["sum"], dims["technical_health"]["known_weight"]) == (235, 95)
    assert (dims["cost_burden"]["sum"], dims["cost_burden"]["known_weight"]) == (240, 90)
    assert factor(result, "cost_burden", "cost_per_user")["level"] == 4
    assert factor(result, "cost_burden", "license_use")["state"] == "not_applicable"
    assert (dims["risk_exposure"]["sum"], dims["risk_exposure"]["known_weight"]) == (170, 80)
    assert [d["coverage"] for d in dims.values()] == [100, 100, 100, 80]
    assert result["confidence"] == 95
    assert result["recommendation"] == "modernize"
    assert result["rule"]["key"] == "valuable_but_weak"
    assert [f["key"] for f in result["flags"]] == [
        "restricted_unsupported",
        "grant_ending",
        "single_maintainer",
    ]
    assert factor(result, "technical_health", "vendor_viability")["state"] == NOT_APPLICABLE
    assert factor(result, "risk_exposure", "compliance")["state"] == UNKNOWN
    assert result["missing"][0]["factor"] == "compliance"


def test_rounding_is_half_up_and_the_rounded_figure_is_compared() -> None:
    from decimal import Decimal

    assert round1(Decimal("4.05")) == 4.1
    assert round1(Decimal("2.95")) == 3.0  # and 3.0 reaches the threshold


@pytest.mark.parametrize(
    ("value", "bands", "direction", "level"),
    [
        (0, [1, 2, 3, 5], "rising", 1),
        (1, [1, 2, 3, 5], "rising", 2),
        (4, [1, 2, 3, 5], "rising", 4),
        (5, [1, 2, 3, 5], "rising", 5),
        (380, [10, 50, 250, 1000], "rising", 4),
        (4999, [5000, 25000, 100000, 500000], "falling", 5),
        (60_000, [5000, 25000, 100000, 500000], "falling", 3),
        (500_000, [5000, 25000, 100000, 500000], "falling", 1),
    ],
)
def test_bands(value: float, bands: list[float], direction: str, level: int) -> None:
    assert band_level(value, bands, direction) == level


def test_unknown_is_left_out_and_counted_against_confidence() -> None:
    known = run()
    unknown = run(users=None)
    reach = factor(unknown, "business_value", "reach")
    assert (reach["state"], reach["where"]) == (UNKNOWN, "users")
    assert unknown["dimensions"]["business_value"]["coverage"] == 85
    assert unknown["confidence"] < known["confidence"]
    assert unknown["scores"]["business_value"] == round1(
        __import__("decimal").Decimal(405 - 60) / 85
    )


def test_not_applicable_changes_neither_score_nor_confidence() -> None:
    saas = run(
        sourcing="saas",
        vendor_sourced=True,
        technologies=[],
        has_components=False,
        answer={**worked_example()["answer"], "vendor_viability": 4},
    )
    currency = factor(saas, "technical_health", "currency")
    assert currency["state"] == NOT_APPLICABLE
    assert factor(saas, "risk_exposure", "eol_exposure")["state"] == NOT_APPLICABLE
    assert saas["dimensions"]["technical_health"]["coverage"] == 100
    no_dependents = run(dependents=0)
    assert factor(no_dependents, "business_value", "dependents")["state"] == NOT_APPLICABLE
    assert no_dependents["dimensions"]["business_value"]["coverage"] == 100


def test_technology_currency() -> None:
    def currency(*techs: dict[str, Any]) -> int | None:
        result = run(technologies=list(techs))
        return factor(result, "technical_health", "currency")["level"]

    soon = TODAY + timedelta(days=100)
    later = TODAY + timedelta(days=900)
    assert currency({"name": "A", "support_ends": soon, "radar": "adopt"}) == 2
    assert currency({"name": "A", "support_ends": later, "radar": "hold"}) == 3
    assert currency({"name": "A", "support_ends": later, "radar": "trial"}) == 4
    assert currency({"name": "A", "support_ends": later, "radar": "adopt"}) == 5
    assert currency({"name": "A", "support_ends": None, "radar": "adopt"}) == 5
    extended = {
        "name": "A",
        "support_ends": TODAY - timedelta(days=5),
        "extended_ends": TODAY + timedelta(days=300),
    }
    assert currency(extended) == 2
    none = run(technologies=[])
    assert factor(none, "technical_health", "currency")["state"] == UNKNOWN


def test_capability_uniqueness_and_floors() -> None:
    def level(primary: str | None, others: int) -> int | None:
        caps = [{"ref": "CAP-1", "name": "X", "others": others, "primary": primary}]
        return factor(run(capabilities=caps), "business_value", "uniqueness")["level"]

    assert [level("self", 0), level("self", 2), level(None, 2), level("other", 2)] == [5, 4, 3, 2]
    low = run(
        tier=5,
        users=3,
        capabilities=[],
        dependents=0,
        answer={"strategic_fit": 1, "functional_fit": 1, "future_need": 1},
    )
    assert low["scores"]["business_value"] == 1.0
    floored = run(
        tier=5,
        users=3,
        capabilities=[],
        dependents=0,
        research_continuity=True,
        answer={"strategic_fit": 1, "functional_fit": 1, "future_need": 1},
    )
    assert floored["scores"]["business_value"] == 4.0
    assert (
        floored["dimensions"]["business_value"]["floor"]["reason"] == "Active studies depend on it"
    )


def test_data_exposure_and_continuity() -> None:
    public = run(sensitivity=0, data_classes=["public"])
    assert factor(public, "risk_exposure", "data_exposure")["level"] == 5
    strong = run(sign_in="sso_mfa")
    assert factor(strong, "risk_exposure", "data_exposure")["level"] == 4  # never 5 when restricted
    open_door = run(sign_in="none")
    assert factor(open_door, "risk_exposure", "data_exposure")["level"] == 1
    assert factor(open_door, "technical_health", "security")["state"] == NOT_APPLICABLE
    tested = run(backup="tested", last_restore_test=TODAY - timedelta(days=30))
    stale = run(backup="tested", last_restore_test=TODAY - timedelta(days=400))
    assert factor(tested, "risk_exposure", "continuity")["level"] == 5
    assert factor(stale, "risk_exposure", "continuity")["level"] == 2  # tier 2, unverified
    assert factor(run(tier=4, backup="none"), "risk_exposure", "continuity")["level"] == 3


def strong_app(**changes: Any) -> dict[str, Any]:
    """An application that scores well on everything, to move one thing at a time."""
    facts = worked_example()
    facts.update(
        technologies=[
            {
                "name": "Python",
                "release": "3.13",
                "radar": "adopt",
                "support_ends": TODAY + timedelta(days=900),
            }
        ],
        maintainers=4,
        monitoring="on_call",
        backup="tested",
        last_restore_test=TODAY,
        annual_cost=10_000,
        funding="operating",
        grant_ends_in_days=None,
        sign_in="sso_mfa",
        answer=dict.fromkeys(QUESTIONS, 5),
    )
    facts.update(changes)
    return evaluate(facts, MODEL, today=TODAY)


def test_every_rule_fires_and_keeps_quiet() -> None:
    assert strong_app()["recommendation"] == "invest"
    assert strong_app(lifecycle="retired")["recommendation"] is None
    assert strong_app(lifecycle="evaluating")["recommendation"] == "incubate"
    assert strong_app(pace="experimental", age_months=6)["recommendation"] == "incubate"
    assert strong_app(pace="experimental", age_months=14)["recommendation"] == "invest"
    thin = strong_app(answer={})
    assert (thin["recommendation"], thin["rule"]["key"]) == ("assess", "not_enough")
    costly = strong_app(
        annual_cost=900_000,
        answer={**dict.fromkeys(QUESTIONS, 5), "support_effort": 1, "change_effort": 1},
    )
    assert costly["recommendation"] == "maintain"
    assert "cost_review" in [f["key"] for f in costly["flags"]]
    weak = {
        "technologies": [{"name": "Old", "support_ends": TODAY - timedelta(days=9)}],
        "monitoring": "none",
        "maintainers": 0,
        "sign_in": "local",
        "answer": {**dict.fromkeys(QUESTIONS, 5), "reliability": 1, "maintainability": 1},
    }
    assert strong_app(**weak)["recommendation"] == "modernize"
    vendor_weak = {
        **weak,
        "sourcing": "commercial",
        "vendor_sourced": True,
        "answer": {**weak["answer"], "vendor_viability": 2},
    }
    assert strong_app(**vendor_weak)["recommendation"] == "replace"
    little = {
        "tier": 5,
        "users": 5,
        "dependents": 0,
        "capabilities": [{"ref": "C", "name": "C", "others": 1, "primary": None}],
        "answer": {
            **dict.fromkeys(QUESTIONS, 5),
            "strategic_fit": 1,
            "functional_fit": 1,
            "future_need": 1,
        },
    }
    assert strong_app(**little)["recommendation"] == "tolerate"
    both = {
        **weak,
        **little,
        "answer": {**little["answer"], "reliability": 1, "maintainability": 1},
    }
    assert strong_app(**both, research_continuity=False)["recommendation"] == "retire"


def test_overlap_recommends_consolidation_into_the_primary() -> None:
    caps = [{"ref": "C", "name": "Surveys", "others": 2, "primary": "other"}]
    peer = {"ref": "APP-0009", "name": "Survey Hub", "bv": 4.8}
    result = strong_app(capabilities=caps, peer=peer)
    assert result["recommendation"] == "consolidate"
    assert result["overlap_with"]["ref"] == "APP-0009"
    assert strong_app(capabilities=caps, peer={**peer, "bv": 1.0})["recommendation"] == "invest"


def test_the_guardrail_protects_critical_applications_from_retirement() -> None:
    weak = {
        "technologies": [{"name": "Old", "support_ends": TODAY - timedelta(days=9)}],
        "monitoring": "none",
        "maintainers": 0,
        "sign_in": "local",
        "users": 5,
        "dependents": 0,
        "capabilities": [{"ref": "C", "name": "C", "others": 1, "primary": None}],
        "answer": {**dict.fromkeys(QUESTIONS, 1)},
    }
    plain = strong_app(**weak, tier=4)
    assert (plain["recommendation"], plain["guardrail"]) == ("retire", None)
    for protected in (
        {"tier": 1},
        {"tier": 4, "regulated_record": True},
        {"tier": 4, "capabilities": [{"ref": "C", "name": "C", "others": 0, "primary": None}]},
    ):
        result = strong_app(**{**weak, **protected})
        if protected.get("regulated_record"):
            # Its value floor already lifts it out of retirement: valuable, but weak.
            assert result["recommendation"] == "modernize"
            continue
        assert result["recommendation"] == "replace", protected
        assert result["guardrail"]["from"] == "retire"


def test_every_flag_fires_and_keeps_quiet() -> None:
    def flags(**changes: Any) -> set[str]:
        return {f["key"] for f in strong_app(**changes)["flags"]}

    assert flags() == set()
    assert "no_accountable" in flags(accountable=False)
    assert "assessment_expired" in flags(assessment_expired=True)
    assert "grant_ending" in flags(funding="grant", grant_ends_in_days=100)
    assert "grant_ending" not in flags(
        funding="grant", grant_ends_in_days=100, decided_within_year=True
    )
    assert "grant_ending" not in flags(funding="grant", grant_ends_in_days=500)
    assert "single_maintainer" in flags(maintainers=1)
    assert "single_maintainer" not in flags(maintainers=1, tier=4)
    old = [{"name": "Old", "support_ends": TODAY - timedelta(days=1)}]
    assert "restricted_unsupported" in flags(technologies=old)
    assert "restricted_unsupported" not in flags(technologies=old, sensitivity=2)
    assert "archive_before_retiring" in flags(records_retention=True, decision="retire")
    assert "decision_review_due" in flags(decision_review_due=True)
    assert "mismatch" in flags(decision="maintain")
    assert "mismatch" not in flags(decision="invest")


def test_profiles_are_chosen_by_condition() -> None:
    assert strong_app(purpose="foundation")["profile"]["key"] == "foundation"
    research = strong_app(sourcing="research_software")
    assert research["profile"]["key"] == "research_software"
    weights = {f["key"]: f["weight"] for f in research["dimensions"]["technical_health"]["factors"]}
    assert weights["sustainability"] == 20 and weights["currency"] == 15


def test_a_model_that_cannot_be_used_says_everything_wrong_with_it() -> None:
    broken = copy.deepcopy(MODEL)
    standard = broken["profiles"][-1]
    standard["factors"]["business_value"][0]["weight"] = 99
    standard["factors"]["technical_health"][5]["bands"] = [3, 2, 1, 0]
    standard["factors"]["cost_burden"][3]["question"] = "no_such_question"
    broken["rules"][0]["when"] = {"field": "colour", "op": "eq", "value": "red"}
    broken["rules"][1]["recommend"] = "panic"
    broken["profiles"][-1]["when"] = {"field": "tier", "op": "eq", "value": 1}
    found = " | ".join(problems(broken, QUESTIONS))
    for words in (
        "add up to",
        "must rise",
        "not in the questionnaire",
        "colour",
        "panic",
        "last profile",
    ):
        assert words in found, words


def test_known_unknown_and_not_applicable_are_the_only_states() -> None:
    result = run()
    states = {f["state"] for d in result["dimensions"].values() for f in d["factors"]}
    assert states <= {KNOWN, UNKNOWN, NOT_APPLICABLE}
