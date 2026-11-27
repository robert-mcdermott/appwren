# Changelog

AppWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

### Added

- **Interfaces.** Data passing from one application to another is a record of its own, with a
  reference (`INT-0007`), a method, how often, the classes of data it carries, and an owner.
  An application's new **Connections** part shows what it sends and receives. An interface
  is seen by whoever may see both of its applications and kept by whoever keeps either.
- **Data flows.** Landscape → Data flows follows a class of data between applications, and
  marks any interface that delivers a class the receiving application's record does not
  list.
- **How a record is connected.** Every application, component, capability, technology,
  vendor, and interface opens a picture of what it is joined to, with any neighbor opened a
  ring further. It works from the keyboard, and a list beside it says everything the
  picture does.
- **What breaks if this goes.** An application's Connections part lists what depends on it,
  directly and through those; the interfaces that would stop; the capabilities left with no
  provider, or without their primary; and the people and units affected.
- **Hosting platforms and deployments.** Landscape → Hosting holds the data centers, cloud
  accounts, clusters, and providers things run on. An application's Components part says
  where it, or any of its components, runs: which platform, in which environment, at what
  address. A platform's page lists everything on it, which is what would stop with it.
- **Cost lines and funding.** An application's new **Cost** part breaks its yearly cost into
  lines by what each is for and what pays for it. Once it has lines, its annual cost is
  their sum. Funding sources (budgets, grants, chargebacks, capital projects) are records of
  their own, each showing what it pays for.
- **Contracts.** Portfolio → Contracts holds agreements with vendors: the applications each
  covers and the licenses they use, the term, the date by which the vendor must be told, and
  whether a data agreement is in place. A contract is shown only to those who may see the
  cost of an application it covers.
- **Two cost factors and two flags.** Cost and burden now weighs cost per user, and the share
  of licenses bought that are in use. Flags are raised for a contract's notice date within
  90 days, and for confidential or restricted data under a contract with no data agreement.
- **Cost on the dashboard,** by category and by what pays, for those who see every
  application's cost.
- **Overlap.** Landscape → Overlap lists every capability served by more than one application
  in service, with those applications side by side: scores, recommendation, decision,
  people, and cost where the reader may see it.
- **The capability map, measured.** The map can show, for each capability, how many
  applications serve it, the average of any score, data confidence, or the technical health
  of the weakest application that serves it. Each figure opens the applications behind it.
- **Lifecycle.** Landscape → Lifecycle shows the technology releases applications run on,
  soonest end of support first, as a timeline with how many components and applications are
  on each; and the applications with a planned retirement.
- **Radar.** The technologies in use by ring (adopt, trial, assess, hold), with how much
  runs on each, and those in use that nobody has placed.
- **Support dates from a file.** `appwren technologies import-eol FILE`, or **Import support
  dates** on the Technologies page, adds releases and updates their dates from a file of
  end-of-life data, matched by each technology's end-of-life key. It says what it would
  change before it changes anything, and removes nothing. AppWren does not fetch the file.
- **Data handling.** Reports → Data handling lists the applications that handle a chosen class
  of data, with who answers for each, where it runs, how people sign in, what it is built on
  and whether that is supported, the interfaces that carry the class, and whether a data
  agreement covers it. The same rows export as CSV or JSON.
- **History, in one place.** Reports → History shows every change, newest first, to managers,
  auditors, and administrators: narrowed to a person, a record, a kind of record, or dates.
- **Links to other systems.** An identifier in another system is shown as a link where the
  program gives that system an address pattern, such as `https://code.example.org/{id}`.
- Lists of applications, the portfolio list, and their exports can be narrowed by capability
  and by class of data.

### Changed

- An application that receives data through an interface now counts among the dependents of
  the application that sends it, so recording interfaces can raise a source's business value.
- **The default scoring model has a new version.** Cost and burden is now annual cost 30,
  cost per user 15, license use 10, support effort 25, and change effort 20, so scores for
  cost and burden move. An installation still running the previous default gets the new
  one on upgrade; one that has shaped its model keeps it, and can take the new factors from
  the default program when it chooses.
- A record's history names the vendor, application, or person a change refers to, where it
  showed a number.

### Fixed

- A record's history told an assessment, a decision, a capability served, and a unit that
  uses an application each as "Added this application". Each is now told for what it is, and
  the copy of a decision onto its application is no longer told as a second change.

## 0.1.0 (2026-11-26)

Wave 1, *The portfolio*: install, sign in, and keep one record of every application, with
what it is built on and what it does for the organization; assess it, read four scores with
their working, see the recommendation and its rule, and record what people decided.

### Added

- **Foundation.** `appwren init`, `serve`, `db upgrade`, `db current`, `verify`, and `doctor`.
  Deployment settings in `appwren.toml` with environment overrides; secrets are refused in
  the file. SQLite by default and PostgreSQL by address, on one model and one set of
  migrations. Every change is written to an append-only, hash-chained history in the same
  transaction, and `appwren verify` finds the first event that has been altered.
- **Accounts and roles.** Local accounts with scrypt-hashed passwords, server-side sessions,
  CSRF protection, and throttled sign-in. Seven roles: admin, manager, architect, auditor,
  leader, steward, and member, some limited to a unit and everything beneath it. Every API
  route is checked against one policy table.
- **Single sign-on.** Optional OpenID Connect beside local accounts, with the provider's
  application roles or groups mapped to roles, unit scopes, and memberships under Admin.
- **Units.** The organization as a hierarchy of any depth, with CSV import of units and
  people that can be run dry first and reports every problem by row.
- **The web app.** Sign-in, the app shell with a command palette (⌘K), your account, and
  admin screens for people, units, single sign-on, and appearance. Light, dark, and system
  modes and three palettes, each checked for contrast. Branding with a live preview.
- **Applications.** Each with a permanent reference (`APP-0042`), the unit that answers for
  it, a lifecycle stage and its date, sourcing, purpose, pace, domain, criticality tier,
  vendor and product, hosting, users, maintainers, sign-in, data handled, monitoring,
  backup, cost and funding, research facts, and the organization's own fields. Exactly one
  accountable owner, and people in other roles. The units that use it. What its stage still
  requires, shown on the record.
- **Components, technologies, vendors, and capabilities.** Components with the technologies
  and releases they are built on; technologies with releases and their support dates, and
  whether each is supported, ending, or past its end; vendors; a capability map, loaded
  with a starter map, with at most one primary provider per capability. Applications
  depend on, are part of, and replace one another.
- **Sensitive fields.** Cost and security details are withheld from people with no role
  over an application, in records, lists, filters, sorting, and history.
- **Program packs.** `appwren program export` and `appwren program import` move the whole
  program between installations, checked whole before anything is loaded, with a dry run.
- **Assessment.** A short question bank, each question with a definition for every level and
  *Don't know* always allowed. Assessments are never edited; the next supersedes the last,
  and answers expire after 12 to 24 months depending on the tier.
- **Scores with their working.** Business value, technical health, cost and burden, and risk
  exposure, each a weighted average of defined factors from answers, recorded facts, and
  what the records around the application say (technology support, capabilities,
  dependents). Data confidence says how much is known. Every score opens to its factors,
  levels, weights, and the sum.
- **Recommendations and flags.** Ordered rules recommend invest, maintain, tolerate,
  modernize, replace, consolidate, retire, incubate, or assess, with guardrails; flags such
  as restricted data on unsupported technology, a grant ending, or one person keeping it.
  Profiles for shared platforms and research software. The scoring model and question bank
  are versioned, and a snapshot keeps a score as it was.
- **Decisions.** A manager, or a leader of the application's unit, records a disposition with
  a rationale, a review date, a target date, and a successor; never the application's own
  accountable owner. Each decision keeps the scores it was made against, and is never
  edited. Where today's recommendation differs, both are shown as a mismatch.
- **The portfolio chart.** Business value against technical health, or against cost and
  burden; bubbles sized by cost where the reader may see it and colored by risk exposure;
  thresholds and quadrants; a table of the same points; and the applications too little is
  known about to place.
- **Portfolio snapshots.** A manager keeps every application's scores together for a review;
  each snapshot reopens unchanged.
- **Home.** One list of what each person owes, most urgent first: applications to assess,
  flags, and records missing what their stage requires; for stewards, applications nobody
  answers for; for managers and leaders, decisions waiting.
- **The dashboard and data quality.** Where the portfolio stands by recommendation, decision,
  lifecycle, sourcing, flags, confidence, and technology support; and what is missing, by
  unit. Every figure opens exactly the list it counts.
- **Import and export.** Applications come in from CSV with a dry run that names every problem
  by row, and update by reference; nothing is loaded unless every row is good. Every list
  exports as CSV or JSON, withholding what the reader may not see, and each export is
  recorded.
- **The demo organization.** `appwren demo` builds the fictional Bramblewood Institute for
  Health Research, with two years of history made by the real services under a simulated
  clock: units, people, applications and their parts, assessments, quarterly snapshots, and
  decisions, with storylines for every screen. It marks itself as a demo, offers one-click
  sign-in as its sample people from the machine it runs on, and refuses to listen beyond it
  unless started with `--demo-on-network`.
- **Guides.** Getting started, the portfolio, running the program, configuration, and the
  API, with screenshots of the demo organization taken by `scripts/capture.mjs`; the
  command reference and the OpenAPI document are written from the code, and a test keeps
  them current.
- **Accessibility checks.** `scripts/a11y-audit.mjs` builds a fresh demo and checks 38
  screens in three palettes, light and dark, for names, labels, headings, landmarks, target
  sizes, and the contrast of every piece of text. `scripts/keyboard-check.mjs` checks the
  skip link, a record's parts, the working behind a score, and the portfolio chart from the
  keyboard. Neither needs anything installed beyond Node and Chrome.
