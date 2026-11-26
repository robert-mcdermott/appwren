# ADR-0011: The scores recommend; named people decide

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

A portfolio tool can treat its calculated recommendation in one of two ways. It can be the answer: the tool says *retire* and the application is on the retirement list. Or it can be advice: the tool says *retire*, shows why, and a named person decides.

When the calculation is the answer, two things go wrong. Owners learn to game the inputs until the number is comfortable, and decisions get made on data nobody has checked. Retiring something people depend on is also political, and a formula is no defence when it turns out to be wrong.

When nothing is calculated, the portfolio review becomes a series of opinions, and the same evidence leads to different decisions on different days.

## Decision

- **Every recommendation is advice, with its working shown.** The factors, their levels and sources, the weights, the dimension scores, and the rule that fired are all on the screen, one click from the recommendation.
- **A disposition is a decision by a named person** with a rationale and a date to look again. Decisions are never edited, only superseded.
- **Disagreement is information, not error.** When the current recommendation differs from the decision on record, both are shown and the difference is flagged as a *mismatch*. A mismatch asks for a conversation; it never changes the decision.
- **No recommendation without enough data.** Below the confidence threshold, the recommendation is *Assess*: complete the record first. Scores are still shown, marked with what is missing, so an owner can see what to supply.
- **Unknown counts for nothing.** A factor with no data is left out of the score and counted against confidence. It is never assumed to be average, good, or bad.
- **Flags are separate from dispositions.** Some conditions need attention whatever the disposition: restricted data on unsupported technology, a grant ending, a single maintainer. These are flags with their own words and marks, never folded into the disposition or its color.
- **Guardrails override the arithmetic in one direction only.** An application that is mission critical, the only provider of a capability, or a system of record for regulated data never receives a plain *Retire*; it becomes *Replace*, which needs a successor.

## Consequences

- The record of a portfolio review is a series of attributable decisions, each with what the system recommended at the time.
- Tuning the model is driven by evidence: mismatches show where the rules and people disagree.
- Owners have a reason to complete their records, because an incomplete record produces *Assess* rather than a judgment they might not like.
- The arithmetic must stay simple enough to follow on the screen: weighted averages of defined levels, a short ordered list of rules, and nothing a reviewer cannot redo by hand.

## Alternatives

- **Automatic dispositions:** consistent, but nobody owns the decision, and inputs get gamed.
- **No calculation at all:** honest, but inconsistent, and it wastes the evidence the record holds.
- **Opaque or statistical models:** might fit past decisions better, but could not be explained to the owner of the application they judge.
