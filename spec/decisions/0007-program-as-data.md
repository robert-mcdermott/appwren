# ADR-0007: The program as data

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Every organization runs its portfolio a little differently. One calls a critical system "tier 1", another "mission critical". One weights reach heavily, another weights cost. A research institute needs fields about grant funding and research continuity that a retailer does not. A university's starter capability map is not a hospital's.

If those choices live in code, each adopter must fork the product or wait for a release. If they live in an open-ended configuration language, the product becomes a platform that needs a specialist to run it.

## Decision

The **program** is data, held in the database, versioned, edited in the app or loaded as a JSON **program pack**:

- **Vocabularies:** sourcing types, purposes, domains, hosting, lifecycle stages, data classes with their sensitivity, monitoring levels, and the rest.
- **Fields:** the attributes recorded about an application beyond its fixed header, each with a type, a section, help text, the sourcing types it applies to, the lifecycle stages at which it is required, and whether it is sensitive.
- **Questions:** the assessment question bank, each question with a definition for every level of its scale.
- **Scoring profiles:** the factors in each dimension, their weights, the bands that turn a measure into a level, and the floors; which profile applies to which applications.
- **Recommendation rules and guardrails:** an ordered list of rules, each a declarative condition over named facts and scores, producing a disposition or a flag.
- **Cadences:** how long an assessment or an attestation stays fresh, by tier.
- **Branding.**

Conditions are written in one small, declarative form (`all`, `any`, `not`, and comparisons of a named fact with a value), interpreted by a few hundred lines of Python. There are no expression strings, no scripting, and no evaluation of code.

A version of the scoring profiles and rules, once used to produce a recorded score, is never changed: editing produces a new version, and every score snapshot and decision keeps the version it was made under.

## Consequences

- An adopter tunes weights, renames tiers, adds a field, or adds a rule without code or a restart, and the history shows who changed it and when.
- Scores stay explainable: every factor, weight, band, and rule that produced a recommendation can be shown by name.
- The rule language is deliberately limited. A need it cannot express is a signal to add a named fact or a new kind of factor in code, with tests, rather than to grow a language.
- The default program pack is the product's opinion of a sensible starting point, built by a script from readable sources and loaded by `appwren init`.

## Alternatives

- **Hard-coded scoring:** simple and fast, and impossible to adopt without forking.
- **A general expression language or embedded scripting:** flexible, but hard to explain on screen, hard to validate, and a security problem.
