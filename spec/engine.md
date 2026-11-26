# The portfolio engine

This document defines how AppWren turns what it knows about an application into scores, a data confidence figure, flags, and a recommended disposition. Everything here is **data in the program** ([ADR-0007](decisions/0007-program-as-data.md)) except the handful of computed factors named below, which are code with tests. The defaults described here are the default program's; an organization changes them in the app.

The engine runs on the server and nowhere else. The assessment form asks the server for a preview as answers change, so there is one implementation of the arithmetic and the browser never disagrees with the record.

## The principles

1. **Explainable.** Every number can be redone by hand from what the screen shows: each factor's level and where it came from, each weight, the sum, and the rule that fired.
2. **Advisory.** The engine recommends. A named person decides, and the decision is a separate record ([ADR-0011](decisions/0011-recommendations-advise.md)).
3. **Objective where possible.** A fact that can be measured is a field, filled by a person, an import, or (from wave 4) a connector. Questions are kept for judgment.
4. **Unknown is not zero.** A factor with no data is left out of its dimension's score and counted against data confidence. It is never assumed.
5. **Judged by the right rubric.** The profile, and some rules, depend on the application's lifecycle stage, sourcing, purpose, and pace.
6. **Stable.** A score changes only when something about the application, its links, or the program changes. Measures become levels through defined bands, never through ranking against the rest of the portfolio ([ADR-0012](decisions/0012-defined-bands.md)).

## From facts to a recommendation

```text
 fields ─┐                 ┌─▶ Business value     ─┐
 links  ─┤                 ├─▶ Technical health   ─┤
 parts  ─┼─▶ facts ─▶ factors ─▶ Cost and burden    ─┼─▶ rules ─▶ recommendation
 answers─┤  (with source   ├─▶ Risk exposure      ─┤    guardrails      + flags
 signals─┘   and date)     └─▶ Data confidence    ─┘
                                                         decision (a person) ─▶ mismatch?
```

1. **Facts** are gathered for the application: its fields, its links, its components and their technologies, the answers in its latest current assessment, and values computed from those. Each fact has a value or is *unknown*, and a source and date.
2. **Factors** turn facts into a **level** from 1 to 5, where 5 is always best for the organization, or into *unknown* or *not applicable*.
3. Each **dimension** is the weighted average of its known factors' levels, with any floors applied.
4. **Data confidence** says how much of the applicable weight was known.
5. **Rules**, in order, choose a recommended disposition; **guardrails** adjust it; **flag rules** raise flags.
6. A **decision** made by a person is compared with the recommendation.

## Facts

A fact is named, so rules and factors can refer to it. The default program uses these.

| Fact | From | Notes |
|---|---|---|
| `lifecycle` | Field | Proposed, Evaluating, Phase-in, Active, Containment, Phase-out, Retired, Archived |
| `sourcing` | Field | SaaS, Commercial (run here), Built here, Open source (run here), Low-code, Research software, Vendor-hosted custom |
| `vendor_sourced` | Computed | True for SaaS, Commercial, and Vendor-hosted custom |
| `purpose` | Field | Mission, Operations, Insight, Foundation |
| `pace` | Field | Steady, Evolving, Experimental |
| `domain` | Field | Research, Clinical, Administrative, Education, IT and infrastructure |
| `tier` | Field | Criticality, 1 (mission critical) to 5 (minimal) |
| `users` | Field | Estimated number of people who use it (a number); from wave 4, active users from the identity provider |
| `maintainers` | Field | People who can maintain or administer it |
| `annual_cost` | Field | Estimated yearly cost, all in; from wave 2, the sum of its cost lines. Sensitive |
| `sign_in` | Field | SSO with MFA, SSO, Local with MFA, Local, Shared accounts, Not applicable (no sign-in) |
| `monitoring` | Field | None, Uptime only, Metrics and logs, Alerting, Alerting to a staffed on-call |
| `backup` | Field | None, Unverified, Tested, Vendor managed |
| `last_restore_test` | Field | A date |
| `data_classes` | Field | Any of the data-class vocabulary; each class has a sensitivity |
| `sensitivity` | Computed | The highest sensitivity of its data classes: 0 public, 1 internal, 2 confidential, 3 restricted |
| `funding` | Field | Operating, Grant, Chargeback, Capital, Mixed |
| `grant_end` | Field | A date |
| `research_continuity` | Field | Active studies or trials depend on it |
| `regulated_record` | Field | It is the system of record for regulated information |
| `records_retention` | Field | Its data has retention requirements that outlive the application |
| `age_months` | Computed | Months since its go-live date, or since it was recorded |
| `currency` | Computed | See *Technology currency* |
| `uniqueness` | Computed | See *Capability uniqueness* |
| `dependents` | Computed | How many active applications depend on it |
| `primary_peer` | Computed | The primary provider of a capability it shares, if it is not one itself |
| `decided_within_year` | Computed | A disposition has been recorded in the last 365 days |
| `answer.<key>` | Assessment | The answer to a question, if the assessment is current |
| `score.<dimension>` | Engine | A dimension's score, available to rules once computed |
| `coverage.<dimension>` | Engine | The share of a dimension's applicable weight that was known |
| `confidence` | Engine | Data confidence, as a percentage |

### Current answers

Answers come from the application's latest **assessment** (a set of answers to the question bank by a named person on a date). An assessment is current for a period that depends on the tier, from the cadence table: 12 months for tiers 1 and 2, 18 months for tier 3, and 24 months for tiers 4 and 5. After that its answers are *expired*: they are shown, marked as such, and count as unknown. An answer of *Don't know* is unknown.

## Factors

Each factor belongs to one dimension, has a weight, and has one of these kinds:

| Kind | Level from | Example |
|---|---|---|
| `answer` | An answer to a question, which is already a level | Strategic fit |
| `choice` | A table from the values of a field to levels; values not in the table are *not applicable* | Sign-in method |
| `band` | A number and its bands, rising or falling | Users: 10, 50, 250, 1,000 |
| `computed` | A named calculation in code | Technology currency |

A factor may say which applications it **applies to**, as a condition. Where it does not apply it is *not applicable*: left out of the score *and* of the weight that confidence is measured against. Vendor viability does not apply to software built here; technology currency does not apply to a SaaS product with no components the organization maintains.

### Band levels

A band factor has four ascending boundaries. For a rising factor, a value below the first boundary is level 1, at or above the first is 2, and so on to level 5 at or above the fourth. A falling factor (cost) counts down from 5.

### Computed factors

**Technology currency.** From the technologies recorded on the application's components and their support dates, on the day of scoring:

| Situation | Level |
|---|---|
| Any technology past its end of support | 1 |
| Any technology reaching end of support within 12 months | 2 |
| All supported, but any on *Hold* in the technology radar | 3 |
| All supported | 4 |
| All supported, and every one *Adopt* | 5 |
| No technologies recorded, and the application has components or is not vendor sourced | Unknown |
| Vendor sourced, with no components recorded | Not applicable |

A technology with no support dates recorded counts as supported but makes the factor's working say so.

**Capability uniqueness.** From the application's links to capabilities:

| Situation | Level |
|---|---|
| The only active application for at least one of its capabilities | 5 |
| The primary provider of a capability that others also serve | 4 |
| One of several, where no primary is named | 3 |
| One of several, where another application is the primary | 2 |
| No capability recorded | Unknown |

**Dependents.** The number of active applications recorded as depending on it: none is *not applicable* (nothing is known to depend on it, which neither raises nor lowers its value); 1 is level 3; 2 to 4 is level 4; 5 or more is level 5.

**Data exposure.** Sensitivity against the sign-in level (the level of the security factor):

| Sensitivity | Sign-in 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|
| 0 Public | 5 | 5 | 5 | 5 | 5 |
| 1 Internal | 5 | 5 | 5 | 4 | 4 |
| 2 Confidential | 4 | 4 | 3 | 2 | 2 |
| 3 Restricted | 4 | 3 | 2 | 1 | 1 |

Unknown when no data classes are recorded, or when sensitivity is above 0 and the sign-in method is unknown. Restricted data never scores 5: holding it is never free of risk.

**End-of-life exposure.** Technology currency against sensitivity: currency 4 or 5 gives 5; currency 3 gives 4; currency 2 gives 2 for confidential or restricted data and 3 otherwise; currency 1 gives 1 for confidential or restricted data and 2 otherwise. Unknown or not applicable when currency is.

**Continuity.** Backup and restore against the tier. A backup marked *Tested* whose last restore test is more than 12 months old counts as *Unverified*.

| Backup | Tiers 1 and 2 | Tiers 3 to 5 |
|---|---|---|
| Tested | 5 | 5 |
| Vendor managed | 4 | 4 |
| Unverified | 2 | 4 |
| None | 1 | 3 |

Unknown when backup is not recorded. An unknown tier counts as tier 3.

## The dimensions

### Business value (BV)

How much the organization would lose without it.

| Factor | Kind | Weight | Source and levels |
|---|---|---|---|
| Criticality | choice | 25 | Tier 1 → 5, 2 → 4, 3 → 3, 4 → 2, 5 → 1 |
| Strategic fit | answer | 20 | *How closely does it support what the organization is trying to achieve?* |
| Reach | band, rising | 15 | Users: 10, 50, 250, 1,000 |
| Capability uniqueness | computed | 15 | As above |
| Dependents | computed | 10 | As above |
| Functional fit | answer | 10 | *How well does it do what its users need today?* |
| Future need | answer | 5 | *Will the organization still need what it does in three years?* |

**Floors:** an application that active studies depend on, or that is a system of record for regulated information, has business value of at least 4.0. The floor and its reason are shown in the working.

### Technical health (TH)

How well it is built, run, and kept current.

| Factor | Kind | Weight | Source and levels |
|---|---|---|---|
| Technology currency | computed | 25 | As above |
| Security | choice | 20 | SSO with MFA 5, SSO 4, Local with MFA 3, Local 2, Shared accounts 1; *Not applicable* for none |
| Operability | choice | 15 | Alerting to on-call 5, Alerting 4, Metrics and logs 3, Uptime only 2, None 1 |
| Reliability | answer | 15 | *How well does it meet the service its users expect?* |
| Maintainability | answer | 10 | *How easy is it to change, upgrade, and keep current?* |
| Sustainability | band, rising | 10 | Maintainers: 1, 2, 3, 5 (none is level 1, one person is level 2) |
| Vendor viability | answer | 5 | *How confident are we in the vendor and the product's future?* Vendor-sourced only |

### Cost and burden (CB)

What it takes to keep. Here 5 means a light burden.

| Factor | Kind | Weight | Source and levels |
|---|---|---|---|
| Annual cost | band, falling | 40 | Annual cost: 5,000; 25,000; 100,000; 500,000 |
| Support effort | answer | 30 | *How much effort does it take to keep running?* |
| Change effort | answer | 30 | *How much effort does it take to change or upgrade?* |

From wave 2, cost per user and license use join this dimension; from wave 4, ticket and incident counts.

### Risk exposure (RE)

What could go wrong while it is kept. Here 5 means little exposure.

| Factor | Kind | Weight | Source and levels |
|---|---|---|---|
| Data exposure | computed | 35 | As above |
| End-of-life exposure | computed | 25 | As above |
| Continuity | computed | 20 | As above |
| Compliance | answer | 20 | *Are there known gaps against the rules that apply to it, such as open audit findings or a missing agreement?* |

### Questions and their levels

Every question has a definition for each of its five levels, shown as the respondent chooses, so that a 4 means the same thing in every department. For example, *Maintainability*:

| Level | Definition |
|---|---|
| 1 | Changes are avoided because they break things; nobody fully understands it |
| 2 | Changes are slow and risky; little documentation or testing |
| 3 | Changes are routine but manual; some documentation |
| 4 | Changes are routine and mostly tested; documented |
| 5 | Changes are safe and frequent: automated tests, deployment, and current documentation |

The default question bank has ten questions: three for business value, three for technical health, two for cost and burden, one for risk exposure, and one (*Future need*) asked in the same section as business value. Each respondent may add a note to any answer. From wave 3 an organization edits the bank in the app; until then, through the program pack.

## Combining

- **A dimension's score** is the weighted average of its known factors: Σ(weight × level) ÷ Σ(weight of known factors), rounded half up to one decimal. The rounded figure is the one shown and the one rules compare, so what is on the screen is what was decided on.
- **Floors** apply after the average and are named in the working.
- **Coverage** is Σ(weight of known factors) ÷ Σ(weight of applicable factors). A dimension with coverage under 50% is *thin*: its score is shown, labelled with its coverage, and it cannot carry a recommendation.
- **Data confidence** is the average of the four dimensions' coverage, as a whole percentage.
- **Scores are kept as snapshots** when a decision is recorded (so the decision shows exactly what it saw), when a portfolio manager closes a review period, and, from wave 3, monthly. A snapshot keeps every factor's level and source, the profile version, and the result, so it reopens unchanged after the program changes.

## Profiles

A **scoring profile** holds the factors, weights, bands, floors, and thresholds. The default program has three, tried in order; the first whose condition matches applies, and the last has none. Weights not named are those of the Standard profile, and each dimension's weights add up to 100:

| Profile | Applies to | What differs |
|---|---|---|
| **Foundation** | Purpose is Foundation | Shared platforms are judged on what rests on them. Business value: strategic fit 10, reach 20, dependents 20, functional fit 5 |
| **Research software** | Sourcing is Research software | Judged on whether it can be kept going. Technical health: technology currency 15, reliability 10, maintainability 15, sustainability 20. Business value: reach 5, functional fit 15, future need 10 |
| **Standard** | Everything else | As in the tables above |

Profiles are versioned. A profile in use is never changed: editing it makes a new version, and every snapshot names the version it used.

## Recommendations

The rules are tried in order and the first that matches gives the recommendation. Thresholds come from the profile; the defaults are 3.0 for value, health, and cost, and 70% for confidence.

| # | Rule | When | Recommends |
|---|---|---|---|
| 1 | Not in service | Lifecycle is Retired or Archived | Nothing; it is no longer scored |
| 2 | New | Lifecycle is Proposed, Evaluating, or Phase-in; or pace is Experimental and it is under 12 months old | **Incubate** |
| 3 | Not enough data | Confidence under the threshold, or business value or technical health thin | **Assess** |
| 4 | Overlap | It shares a capability with an application named as that capability's primary provider, it is primary for none, and its business value is lower than that application's | **Consolidate** into the primary |
| 5 | Strong | BV ≥ 3.0 and TH ≥ 3.0 | **Invest** if CB ≥ 3.0, otherwise **Maintain** with a *cost review* flag |
| 6 | Valuable but weak | BV ≥ 3.0 and TH < 3.0 | **Replace** if vendor sourced and vendor viability is 2 or less; otherwise **Modernize** |
| 7 | Sound but little used | BV < 3.0 and TH ≥ 3.0 | **Tolerate** |
| 8 | Weak and little used | BV < 3.0 and TH < 3.0 | **Retire** |

### Guardrails

Applied after the rules, in order:

1. **Protected from retirement.** A *Retire* for an application of tier 1 or 2, the only provider of a capability, or a system of record for regulated information becomes **Replace**, and the working says a successor is needed.

### Flags

Flags are raised whatever the recommendation. They are separate signals with their own words and marks, and each names the facts that raised it.

| Flag | When | Severity |
|---|---|---|
| **Restricted data on unsupported technology** | Sensitivity is restricted and technology currency is 1 | Danger |
| **Grant ending** | Funding is Grant, the grant ends within 12 months, and no disposition has been recorded in the last year | Warning |
| **One person keeps this** | Built here, Low-code, or Research software, tier 1 to 3, and one maintainer or none | Warning |
| **Archive before retiring** | Recommended or decided Retire, Replace, or Consolidate, and its data must be retained | Information |
| **Cost review** | Raised by rule 5 | Information |
| **No accountable owner** | Nobody is accountable | Danger |
| **Assessment expired** | The latest assessment is no longer current | Warning |
| **Decision review due** | The decision on record is past its review date | Warning |
| **Mismatch** | The decision on record differs from today's recommendation | Information |

## Dispositions

| Disposition | Meaning | Typical action |
|---|---|---|
| **Invest** | Grow its capability and use | Fund enhancements; widen adoption |
| **Maintain** | Keep it as it is, run efficiently | Keep current; control cost |
| **Tolerate** | Keep it at the least cost, and look again | Freeze features; look for consolidation |
| **Modernize** | Valuable, but technically weak | Upgrade, re-platform, or refactor |
| **Replace** | The function is needed; this asset should go | Buy or build a successor |
| **Consolidate** | Does what another application does | Move its users to the primary |
| **Retire** | Little value; retire without a successor | Archive its data; decommission |
| **Incubate** | New or experimental; not yet judged on use | Review against its pilot's success criteria |
| **Assess** | Not enough is known to recommend | Complete the record, then look again |

*Incubate* and *Assess* are recommendations; a person may record them as decisions too. A decision may be any disposition, whatever the recommendation.

## Decisions and mismatches

A **decision** records a disposition for an application by a named person with the authority (a portfolio manager, or a leader for the applications in their units), with a rationale, a date to review it, an optional target date, and the snapshot of the scores it was made against. Decisions are never edited; a new one supersedes the last.

When today's recommendation differs from the decision on record, the application shows a **mismatch**: both dispositions, side by side, with the working of each. Mismatches are listed on the dashboard as a prompt for the next portfolio review. They change nothing on their own.

## A worked example

*Specimen Tracker* is built here, tier 2, used by about 380 people. Its components run on a version of Python whose support has ended, behind SSO, with metrics and logs, and one developer. It holds identifiable research data. Backups have never been restore-tested. It is the only application for the *Biospecimen tracking* capability, three others depend on it, it costs about 60,000 a year, and it is paid for by a grant that ends in eight months. Its owner's assessment, done four months ago, answered: strategic fit 4, functional fit 3, future need 4, reliability 3, maintainability 2, support effort 2, change effort 2, and *Don't know* for compliance.

**Business value** (Standard profile): criticality 4 × 25, strategic fit 4 × 20, reach 4 × 15 (380 is at least 250), uniqueness 5 × 15, dependents 4 × 10 (three), functional fit 3 × 10, future need 4 × 5. That is 405 ÷ 100 = **4.1**, coverage 100%.

**Technical health:** currency 1 × 25, security 4 × 20 (SSO), operability 3 × 15, reliability 3 × 15, maintainability 2 × 10, sustainability 2 × 10 (one maintainer); vendor viability is not applicable. That is 235 ÷ 95 = 2.47, so **2.5**, coverage 100%.

**Cost and burden:** annual cost 3 × 40 (under 100,000), support effort 2 × 30, change effort 2 × 30. That is 240 ÷ 100 = **2.4**.

**Risk exposure:** data exposure 3 × 35 (restricted, sign-in 4), end-of-life exposure 1 × 25 (currency 1, restricted), continuity 2 × 20 (tier 2, unverified); compliance unknown. That is 170 ÷ 80 = 2.13, so **2.1**, coverage 80%.

**Data confidence:** (100 + 100 + 100 + 80) ÷ 4 = **95%**.

**Recommendation:** it is active, confidence is above 70%, and it is the only provider of its capability, so rules 1 to 4 do not match. Value is 4.1 and health 2.5, so rule 6 matches; it is not vendor sourced, so the recommendation is **Modernize**.

**Flags:** *Restricted data on unsupported technology* (restricted, currency 1); *One person keeps this* (built here, tier 2, one maintainer); *Grant ending* (eight months, no decision this year).

This example is a test: the default program must produce exactly these figures.

## What the screen shows

- **Scores** as four figures with a short bar each, coverage beneath any that is under 100%, and data confidence as a percentage with what is missing.
- **The working** for any dimension: each factor, its level, its weight, where its value came from and when (*Field, edited by … on …*, *Assessment ASM-0042 by … on …*, *Computed from 3 components*), and the sum. Unknown and not-applicable factors are listed with the reason.
- **The recommendation** with the rule that fired, any guardrail that changed it, and the thresholds compared.
- **The decision** on record beside it, and the mismatch if there is one.
- **What would raise confidence:** the unknown factors in order of weight, each with a link to where it is entered.
