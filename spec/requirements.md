# Requirements

The capability catalog. IDs are stable: code, tests, and changelog entries can cite them.

**Priority:** **M**ust (required for the capability to ship), **S**hould (high value, next in line), **C**ould (optional expansion).
**Wave:** the release that delivers it (see [roadmap.md](roadmap.md)). `—` means not yet scheduled.

## Inventory (INV)

What the organization runs, and who answers for it.

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| INV-01 | M | Units are the backbone | Every application belongs to one unit in a hierarchy of any depth; every list and figure can be narrowed to a unit and everything beneath it | 1 |
| INV-02 | M | Applications | An application has a permanent reference, a name and aliases, a description, a unit, a lifecycle stage with its date, a sourcing type, a purpose, a pace, a domain, a tier, and the facts the engine reads ([engine.md](engine.md#facts)) | 1 |
| INV-03 | M | One accountable owner | Every application has exactly one accountable owner, and may name people in other roles; one imported with nobody named, or whose accountable owner has left, is shown as orphaned | 1 |
| INV-04 | M | Sourcing types | SaaS, commercial run here, built here, open source run here, low-code, research software, and vendor-hosted custom, each showing the fields that apply to it | 1 |
| INV-05 | M | Components | An application is decomposed into components with a kind, a repository, hosting, and the technologies and versions each uses | 1 |
| INV-06 | M | Vendors | Vendors are records, linked from the applications and technologies they supply | 1 |
| INV-07 | M | Technologies and their support | Technologies are records with a radar ring and releases, each with support dates; each release shows the components that use it | 1 |
| INV-08 | M | Who uses it | Everyone in the organization, or the units that use an application and the kinds of people who use it wherever they work (managers, hourly employees, contractors); an estimate of how many people; and whether people outside the organization use it | 1, 9 |
| INV-09 | M | History on every record | Each record shows who changed what and when, with the value before and after | 1 |
| INV-10 | M | Lists that hold their state | Every list searches, filters, sorts, and pages, with its state in the address so any view can be shared | 1 |
| INV-11 | M | The organization's own fields | The program defines extra fields for applications, with a type, a section, help, the sourcing types they apply to, and whether they are sensitive, without code | 1 |
| INV-12 | M | Spreadsheet import and export | Applications are imported from CSV with column mapping and a dry run that reports every problem by row, adding new ones and updating existing ones by reference; every list exports as CSV and JSON | 1 |
| INV-13 | M | Required fields by stage | Each lifecycle stage names the fields an application must have to be in it; the record shows what is missing for its stage and the next | 1 |
| INV-14 | S | What counts as an application | The program holds a short definition with examples, shown wherever an application is added | 1 |
| INV-15 | S | Likely duplicates | Adding an application with a name, alias, or vendor product close to an existing one shows the candidates first | 3 |
| INV-16 | S | External references | A record can carry its identifier in another system (a configuration item, a ticket queue), shown as a link where a pattern is configured | 2 |
| INV-17 | S | Software catalog files | Engineering teams describe applications and components in a file kept in their repository, imported and exported in a common descriptor format | 4 |
| INV-18 | S | Organization-wide history | Those who may read everything browse every change in one place, filtered by person, record, and date | 2 |

## Landscape (LND)

How the applications fit together.

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| LND-01 | M | Capability map | A hierarchy of capabilities; each application is mapped to the capabilities it serves, one application per capability named as the primary provider | 1 |
| LND-02 | M | Dependencies | An application can be recorded as depending on another; each shows what it depends on and what depends on it | 1 |
| LND-03 | S | Interfaces and data flows | An interface between applications has a direction, a method, a frequency, an owner, and the data classes it carries; a view shows every flow of a chosen data class | 2 |
| LND-04 | S | Dependency graph and impact | A focused picture around any application; *what breaks if this goes* lists the dependents, interfaces, capabilities left uncovered, and users affected | 2 |
| LND-05 | S | Deployments | An application or component runs as deployments in environments on hosting platforms | 2 |
| LND-06 | S | Overlap | Capabilities served by more than one application are listed, with their applications' scores side by side | 2 |
| LND-07 | S | Capability heat map | The capability tree colored by any score, coverage, or count | 2 |
| LND-08 | S | Lifecycle view | Applications and technology releases on a timeline with their go-live, end-of-support, and planned retirement dates | 2 |
| LND-09 | S | Technology radar | The technologies in use, by ring and kind, with how many components use each | 2 |

## Cost and funding (CST)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| CST-01 | M | An estimate first | An application carries an annual cost estimate that feeds the cost factor; ranges are acceptable | 1 |
| CST-02 | M | Funding | The funding source, and for a grant its reference and end date | 1 |
| CST-03 | S | Cost lines | Costs by category (license or subscription, hosting, support contract, internal effort) and funding source, adding up to the annual cost | 2 |
| CST-04 | S | Contracts and renewals | Contracts with a vendor, the applications they cover, term, renewal and notice dates, auto-renewal, licenses bought, and whether a data agreement is in place | 2 |
| CST-05 | S | Cost per user and license use | Cost per active user, and licenses used against those bought, as factors and in reports | 2 |
| CST-06 | C | A standard cost taxonomy | Cost lines classified in a published, open taxonomy of technology costs for roll-up | — |

## Assessment and scoring (SCR)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| SCR-01 | M | Four dimensions | Business value, technical health, cost and burden, and risk exposure are worked out as defined in [engine.md](engine.md), on a scale of 1 to 5 where 5 is best | 1 |
| SCR-02 | M | The working | Every score shows each factor's level, weight, value, source, and date, the sum, and the rule that fired; anyone can redo it by hand | 1 |
| SCR-03 | M | Unknown is not zero | A factor with no data is left out of its score and counted against confidence; an expired answer counts as unknown | 1 |
| SCR-04 | M | Data confidence | Confidence is shown for every application; below the threshold the recommendation is *Assess*, and the screen lists what would raise it | 1 |
| SCR-05 | M | Defined questions | The question bank has a definition for every level of every question, shown as the respondent chooses, and *Don't know* | 1 |
| SCR-06 | M | Assessments | An owner, steward, architect, or manager answers the questions; assessments are never edited, only superseded; how long one stays current depends on the tier | 1 |
| SCR-07 | M | Preview | While answering, the respondent sees the scores and recommendation that would result, computed by the same engine as the record | 1 |
| SCR-08 | M | Profiles | Factors, weights, bands, floors, and thresholds are held in versioned profiles chosen by condition; a profile in use is never changed | 1 |
| SCR-09 | M | Defined bands | Measures become levels through bands held in the profile, never by ranking against the portfolio ([ADR-0012](decisions/0012-defined-bands.md)) | 1 |
| SCR-10 | M | Snapshots | Scores are kept as snapshots when a decision is recorded and when a portfolio snapshot is taken, and reopen unchanged after the program changes | 1 |
| SCR-11 | S | Signals as factors | Facts from connectors (code activity, sign-ins, incidents, tickets) join the factors that they inform, with their source | 4 |
| SCR-12 | S | Engineering maturity | Automated checks per component (monitoring, backups, tests, documentation, dependency updates) roll up to a bronze, silver, or gold level | 4 |
| SCR-13 | S | Contest a score | An owner contests a factor's value with evidence and a note; the portfolio team accepts or answers it, on the record | 3 |
| SCR-14 | C | Portfolio-relative reports | Reports by portfolio share (the costliest tenth, the least used fifth), which never feed a score | 6 |

## Decisions (DEC)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| DEC-01 | M | Recommendations | Each scored application receives a recommended disposition from ordered, configurable rules and guardrails, with the rule that fired | 1 |
| DEC-02 | M | Flags | Conditions that need attention (restricted data on unsupported technology, a grant ending, one maintainer, no accountable owner, an expired assessment) are raised as flags, separate from the disposition | 1 |
| DEC-03 | M | Decisions | A manager, or a leader for their units, records a disposition with a rationale, a review date, a target date, and for a replacement or consolidation the successor; never as the application's accountable owner; never edited, only superseded | 1 |
| DEC-04 | M | Mismatches | Where today's recommendation differs from the decision on record, both are shown with their working and the difference is listed | 1 |
| DEC-05 | M | Lifecycle stages | Applications move through Proposed, Evaluating, Phase-in, Active, Containment, Phase-out, Retired, and Archived, with the date of each stage on the record | 1 |
| DEC-06 | S | Stage gates | Moving to a stage requires that stage's required fields; a move short of them is refused with what is missing | 5 |
| DEC-07 | S | Retirement playbook | A retirement plan with a checklist (notice, data archived, interfaces removed, licenses ended, access removed, infrastructure torn down) and the savings realized | 5 |

## Keeping current (CUR)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| CUR-01 | M | Home | Each person sees one list of what they owe, most urgent first | 1 |
| CUR-02 | M | Data quality | A page of applications without an accountable owner, a capability, a current assessment, or the fields their stage requires, by unit, each figure opening its list | 1 |
| CUR-03 | M | Attestation | Owners confirm their records on a cadence by tier; a record past its attestation counts as stale and lowers confidence | 3 |
| CUR-04 | M | Reminders and email | Reminders before and after things fall due, by email and in the app, with digests and preferences | 3 |
| CUR-05 | S | Campaigns | Assessment and attestation campaigns to the owners in a scope, with progress by unit | 3 |
| CUR-06 | S | Triggers | Tasks raised when an owner leaves, a contract renews, a technology nears end of support, a grant nears its end, or a signal crosses a threshold | 3 |
| CUR-07 | S | Reassignment | Everything a departing person answers for is reassigned in one step | 3 |
| CUR-08 | S | Search and saved views | One search across every record type, filtered by what the searcher may see; a filtered list can be saved and shared | 3 |
| CUR-09 | S | Program editors | Vocabularies, fields, questions, profiles, rules, and cadences edited in the app with an impact preview | 3 |

## Signals (SIG)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| SIG-01 | M | Connectors an administrator turns on | Each connector is off until enabled, read-only, with its credential from the environment, and every run recorded ([ADR-0003](decisions/0003-quiet-by-default.md)) | 4 |
| SIG-02 | M | Sourced values | Every value a connector supplies is kept with its source and time, shown as such, and can be overridden by a person with a reason | 4 |
| SIG-03 | S | Source code hosting | Repositories give a component its languages, last change, active contributors, and open dependency alerts | 4 |
| SIG-04 | S | End-of-life data | Support dates for technology releases from a public end-of-life dataset, matched by key | 4 |
| SIG-05 | S | Identity provider | Applications registered with the identity provider, and sign-in counts as active users | 4 |
| SIG-06 | S | Push for everything else | Incident and ticket counts, cloud cost by tag, and any other fact can be posted to the API in one generic format | 4 |

## Planning (PLN)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| PLN-01 | S | Review cycles | A portfolio review with its scope, agenda of applications, the recommendations and mismatches, and the decisions taken | 5 |
| PLN-02 | S | Initiatives and roadmap | Modernizations, migrations, consolidations, and retirements as initiatives linked to applications, on a roadmap with their dates | 5 |
| PLN-03 | S | Intake | A request for a new application: the need, the capability, a check for existing applications that already serve it, and a build, buy, or partner evaluation | 5 |
| PLN-04 | C | Scenarios | A proposed set of changes (retire this, consolidate that) with its effect on cost, users, interfaces, capabilities left uncovered, and risk | 6 |

## Insight (RPT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| RPT-01 | M | Portfolio chart | Business value against technical health, sized by cost where the viewer may see it, colored by risk exposure, with quadrants, filters, and a table of the same points | 1 |
| RPT-02 | M | Dashboard | Counts by recommendation, decision, lifecycle, and sourcing; mismatches; flags; confidence; end-of-life exposure; each figure opens the list it counts | 1 |
| RPT-03 | M | Figures equal their lists | Every figure is the count of a list filter and opens exactly that list, for every role | 1 |
| RPT-04 | S | Trends | Movement between snapshots: what changed disposition, scores over time | 6 |
| RPT-05 | S | Leadership report | A periodic report frozen as a snapshot that reopens unchanged, printable for a budget or roadmap meeting | 6 |
| RPT-06 | S | As of | Any application, and the portfolio, as it stood on a chosen date | 6 |
| RPT-07 | S | Evidence for a risk analysis | An export of the applications that handle a data class, with owners, versions, hosting, sign-in, and support status | 2 |

## Platform (PLT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| PLT-01 | M | Install in minutes | Three commands produce a running system on SQLite with a first administrator and no other software | 1 |
| PLT-02 | M | SQLite and PostgreSQL | One model and one set of migrations run on both; the whole test suite passes on both | 1 |
| PLT-03 | M | Sign-in always required | Local accounts with hashed passwords, server-side sessions, and throttled sign-in | 1 |
| PLT-04 | M | Roles with scope | Seven roles, some limited to a unit and everything beneath it; every API route is checked against one policy table | 1 |
| PLT-05 | M | A permanent history | Every change is an event in an append-only, hash-chained log; a command verifies the chain | 1 |
| PLT-06 | M | Optimistic concurrency | A change made against an older version of a record is refused with the current values | 1 |
| PLT-07 | M | Themes | Light, dark, and system modes and three palettes, each checked for contrast | 1 |
| PLT-08 | M | Branding in the app | An administrator sets names, logo, palette, and accent with a live preview | 1 |
| PLT-09 | M | A default program | A new installation is loaded with vocabularies, a question bank, scoring profiles, rules, cadences, and a starter capability map | 1 |
| PLT-10 | M | Demo organization | One command builds a fictional organization through the real services, with data on every screen | 1 |
| PLT-11 | M | Command line | Installation, accounts, the database, program packs, verification, and health checks from one command | 1 |
| PLT-12 | M | Accessibility | WCAG 2.2 AA, with an automated audit over every documented screen in every palette and mode | 1 |
| PLT-13 | M | Single sign-on | OpenID Connect with any standards-based provider; groups or application roles mapped to roles and unit scopes | 1 |
| PLT-14 | M | Sensitive fields | Fields the program marks sensitive are withheld from those without a role over the application, everywhere: records, lists, filters, exports, charts, and the working | 1 |
| PLT-15 | S | Program packs | The whole program exports to one file and imports into another installation, checked before any of it is loaded | 1 |
| PLT-16 | S | Backup and moving | An installation is backed up, restored, and moved between SQLite and PostgreSQL by command | 7 |
| PLT-17 | S | Deployment recipes | A container image, a compose file with PostgreSQL, a hardened service unit, and proxy examples | 7 |
| PLT-18 | S | Brand kit | A full custom palette, sign-in page message, email header, footer links, and the organization's own words for key terms | 7 |
| PLT-19 | S | Starter programs | Program packs for a research institute, an academic medical center, a university, a general nonprofit, and a company | 7 |
| PLT-20 | S | Security review | A review against a published application security verification standard, with findings and their resolution recorded | 7 |
| PLT-21 | S | Several portfolios | Units run their own portfolio views with delegated administration, and roll up to the organization's | Later |
| PLT-22 | S | Performance | Measured at 5,000 applications and 50,000 components with many people at once | 7 |
| PLT-23 | C | Other languages | The interface in languages other than English | — |

## Integration (INT)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| INT-01 | M | One API | Everything the web app does, it does through `/api/v1`; the OpenAPI document is generated, committed, and kept current by a test | 1 |
| INT-02 | S | Scoped tokens | An administrator issues a token limited to a role and optionally to reading, shown once, stored as a hash, with an expiry | 7 |
| INT-03 | S | Signed webhooks | Named events (a decision, a stage change, an attestation lapsing) are sent, signed, to addresses an administrator registers | 7 |
| INT-04 | S | A reference others can check | Another process asks whether an application is approved for a use or a data class, and gets an answer with its reasons | 8 |
| INT-05 | C | Tool server for assistants | An optional server through which an AI assistant reads the portfolio under the same permissions as a person, and drafts changes that a person confirms | 8 |
| INT-06 | C | Optional assistant | Off and invisible by default; drafts an application record from a document or a repository's description, and answers questions with links to the records behind the answer; every exchange logged | 8 |
| INT-07 | C | Records in other governance systems | An application links to its records in other systems of record (an AI-use review, a risk register) by external reference, with their standing where that system offers it | 8 |

## Documentation (DOC)

| ID | Pri | Requirement | Acceptance | Wave |
|---|---|---|---|---|
| DOC-01 | M | Guides with every release | Getting started, configuration, the portfolio, running the program, the command-line reference, and the API guide, updated in each wave | 1 |
| DOC-02 | S | A product site | A site built from the guides, with screenshots of the demo organization, an API reference, and search, published with each release | 2 |
| DOC-03 | S | The program handbook | One guide for a portfolio team, from first decisions to the yearly rhythm of reviews | 7 |
