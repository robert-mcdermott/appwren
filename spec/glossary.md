# Glossary

| Term | Meaning |
|---|---|
| **Accountable owner** | The one person who answers for an application. Every application past Proposed has exactly one |
| **Application** | The logical thing people name, own, use, and decide about. The unit of the portfolio ([ADR-0013](decisions/0013-applications-components-deployments.md)) |
| **Assessment** | A set of answers to the question bank about one application, by a named person on a date. Never edited; superseded by the next |
| **Band** | The boundaries that turn a measure (users, cost, maintainers) into a level from 1 to 5 ([ADR-0012](decisions/0012-defined-bands.md)) |
| **Capability** | Something the organization does, independent of how or with which system: "Biospecimen tracking", "Payroll" |
| **Component** | A part of an application that is built, bought, or maintained on its own: a service, a database, a batch job |
| **Coverage** | The share of a dimension's applicable weight whose factors were known |
| **Current** | Of an assessment: within the period the cadence table allows for the application's tier |
| **Data class** | A kind of data an application handles, with a sensitivity from public to restricted |
| **Data confidence** | The average coverage of the four dimensions, as a percentage. Below the threshold, the recommendation is *Assess* |
| **Decision** | A disposition recorded for an application by a named person, with a rationale and a review date |
| **Deployment** | A running instance of an application or component in an environment (wave 2) |
| **Dimension** | One of the four scores: business value, technical health, cost and burden, risk exposure |
| **Disposition** | What to do with an application: Invest, Maintain, Tolerate, Modernize, Replace, Consolidate, Retire, Incubate, or Assess |
| **End of support** | The date after which a technology release no longer receives fixes from its maintainers |
| **Factor** | One input to a dimension, with a weight, turned into a level |
| **Fact** | A named value about an application that factors and rules read, with its source and date |
| **Flag** | A condition that needs attention whatever the disposition, such as restricted data on unsupported technology |
| **Guardrail** | A rule that adjusts a recommendation in one direction, such as never recommending a plain *Retire* for a mission-critical application |
| **Lifecycle** | The stage an application is in: Proposed, Evaluating, Phase-in, Active, Containment, Phase-out, Retired, Archived |
| **Mismatch** | A difference between today's recommendation and the decision on record. A prompt for discussion, not an error |
| **Pace** | How fast an application is expected to change: Steady, Evolving, or Experimental |
| **Portfolio snapshot** | Every application's scores, kept together at a moment, for a review or the end of a period |
| **Profile** | A set of factors, weights, bands, floors, and thresholds, chosen for an application by a condition |
| **Program** | Everything the portfolio team configures: vocabularies, fields, questions, the scoring model, cadences, branding |
| **Purpose** | What kind of work an application does: Mission, Operations, Insight, or Foundation |
| **Radar** | The organization's view of a technology: Adopt, Trial, Assess, or Hold |
| **Recommendation** | The disposition the rules produce from the scores and facts. Advice, never a decision ([ADR-0011](decisions/0011-recommendations-advise.md)) |
| **Reference** | A record's short, permanent identifier, such as `APP-0042` |
| **Release** | A version line of a technology (such as `3.11`), with its support dates |
| **Restricted** | Of a record: visible only to the people named on it and those with a role over its unit |
| **Sensitive field** | A field visible only to the people named on the application and those with a role over it, such as cost |
| **Sourcing** | Where an application comes from: SaaS, commercial, built here, open source, low-code, research software, vendor-hosted custom |
| **Steward** | Someone who keeps a unit's records current |
| **Thin** | Of a dimension: coverage under 50%, so it cannot carry a recommendation |
| **Tier** | Criticality, from 1 (mission critical) to 5 (minimal) |
| **Unit** | A part of the organization: a division, a department, a lab, a team. Units form a tree |
| **Working** | The explanation of a score or recommendation: every factor, level, weight, source, and rule |
