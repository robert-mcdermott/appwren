# Changelog

AppWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

### Added

- **Connectors.** Admin → Connectors lists the tools AppWren can read facts from. Each
  connector is added switched off, for one named source; it only reads; its credential
  stays in an environment variable named on the connector and is never stored. It can be
  checked before it is switched on, runs daily on the scheduler or when asked, and every run
  is recorded: what it read, what it changed, what it could not match, and why it failed. A
  run reads everything first, under a time limit and a size limit, and writes only if all of
  that succeeded, so a failed run changes nothing.
- **Values from other systems.** A value a connector supplies is written to the record's own
  field, kept with its source and when it was read, marked as such on the record, and
  recorded in the history. A person who keeps the record can override it with a reason; the
  override wins until it is removed. Changing such a field by hand counts as an override.
- **End-of-life data.** The first connector reads support dates for technology releases from
  the public endoflife.date dataset, for each technology with an end-of-life key, by the same
  rules as the import from a file: releases are added and dates updated, and nothing is
  removed.
- The history names the release whose dates changed, and shows the reason given for an
  override.

## 0.3.0 (2026-11-26)

Wave 3, *Keeping current*: a portfolio that stays true without a central team chasing it.
The app knows what falls due and says so, in the app and by email; owners confirm their
records on a cadence, and a record nobody confirms lowers confidence where everyone can see
it; campaigns ask the owners in a unit, by a date; departures, renewals, end of support, and
grant ends raise tasks for whoever must act; anything on record can be found; and the
program is shaped in the app, with a preview of what a change would do.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept, and no
record is stale on the day of the upgrade.

### Added

- **The documentation site.** The guides, with their pictures of the demo organization, are
  published at <https://robert-mcdermott.github.io/appwren/>: a home page, one page for each
  guide, the changelog, an API reference written from the OpenAPI document, search, and light
  and dark themes. `node scripts/site/build.mjs` builds it from `docs/` with Node 22 and no
  packages, and fails on a broken link, anchor, or picture; `node scripts/site/audit.mjs`
  checks every page in both themes at desk and phone widths.
- **Scheduled work.** The server runs jobs by itself: triggers, reminders, email, a monthly
  snapshot, and housekeeping. A
  process claims a job before running it, so several servers, or `appwren jobs run` from a
  scheduled task, run each one once between them. Admin → Scheduled work shows each job,
  when it last ran and what it did, and can run or pause it. `[server] scheduler = false`
  leaves the work to `appwren jobs run`.
- **Notices and reminders.** A bell in the top bar counts what is new for you, and opens a
  page of it. Whoever something waits on is reminded two weeks before its date and the day
  after: an assessment about to expire, and a decision's review date and target date. An assessment or a target that stays late goes to the unit's
  steward after a week and its leader after three. Each is said once for a given date.
- **Email, optional.** Name an SMTP server under `[mail]` and notices go by email as well,
  each as it happens or in a daily summary, as each person chooses under Your account. The
  password comes from the environment. Until email is set up nothing is attempted, and
  nothing written before then is ever sent. `appwren mail test` sends a test message, and
  `appwren doctor` checks the server.
- **Confirming a record.** The people named on an application, its unit's stewards, and
  managers confirm that its record is right, in one step from its page: every 6 months for
  tiers 1 and 2, every 12 for the rest. A record past its confirmation is stale: its page
  says so, it is flagged, data quality and the portfolio list count it, its owner is
  reminded, and its data confidence is 15 points lower until someone confirms it. A record
  never confirmed is due one period after it was added or after the upgrade, whichever is
  later, so nothing is stale on the day of the upgrade.
- **Campaigns.** Managers and stewards ask the owners of the applications in a unit, narrowed
  by tier and stage if they wish, to confirm their records or to assess their applications by
  a date (`CMG-0002`). Before starting, it says how many people it would ask and which
  applications have nobody to ask. Each person is told once, with a count, and finds what is
  asked of them on Home. An item closes itself when the record is confirmed or the
  application assessed after the campaign began. The campaign's page shows its progress and
  its coverage by unit, least covered first, and can remind, excuse an application with a
  reason, close, or cancel.
- **Tasks, raised by what happens.** Each hour the triggers look at the dates and the people
  on record. A contract's notice date within 60 days, a release in use within 180 days of its
  end of support, a grant within 180 days of its end, and an accountable owner who has left
  each raise a task for the person who must act, with a date and the reason, and tell them.
  A cause raises one task, never two. A task closes by itself when its cause is settled (the
  contract renewed, nothing on the release, a decision recorded, someone named) or by a person
  with a note. Tasks are on Home, on a page of their own, and in the reminders; the reminder
  of a contract's notice date is now its task's.
- **Passing on what someone holds.** Every person has a page of what they hold: the records
  they are named on and in what role, the contracts and interfaces they own, their open
  tasks, and what campaigns still ask of them. An administrator or a manager passes all of it
  to someone else in one step. Assessments and decisions stay with whoever made them.
- **One search.** The command palette finds records as well as pages, and Search lists
  every kind of record that matches, the best answer first: by name, reference, summary, or
  what something is called elsewhere. It finds only what the searcher may open.
- **Saved views.** Any list's filters are kept under a name from its **Views** button,
  privately, or shared with everyone by stewards, architects, and managers. A view keeps the
  question, so each person who opens it sees only what they may.
- **Applications by what they are built on.** The applications and components lists, and
  their exports, narrow to a technology, one of its releases, or an exact version, such as
  every application on .NET 6, or on 6.0.25. A technology's page links each release to that
  list. An application counts when any of its components is on it.
- **Likely duplicates.** Adding or renaming an application shows those already on record
  whose name or alias is close, or that are the same product from the same vendor.
- **Contesting a score.** Whoever keeps an application says a factor is wrong, what it should
  be, and why, with a link to the evidence. A manager or an architect accepts or answers it,
  and the owner is told. Both stay on the record and in its history. A contest does not move
  a score; putting the record or the assessment right does.
- **The program, shaped in the app.** Admin → Program, for managers of the whole
  organization and administrators: rename, describe, reorder, add to, and retire the values
  of a list (those AppWren's rules read can be renamed and reordered only); add and edit the
  organization's own fields and say which are sensitive; reword the questions and their
  levels; and change the thresholds, every profile's weights, and the cadence. A changed
  scoring model is previewed first, listing every application whose scores, confidence,
  recommendation, or flags would differ, and publishing it changes exactly those. Each change
  publishes a new version or is kept in the history.
- **A portfolio snapshot each month,** kept by the scheduler on the first turn of the month.
- **Starting with one team.** `appwren init` asks for the organization's name and a first
  unit within it, such as the team starting with AppWren (`--organization` and
  `--first-unit` when unattended), so an application can be added at once. **Admin →
  Units → Put a unit above the top** puts a new top unit above the existing one, for a team
  that began at the top. *Getting started* has a section on starting with one team.
- **Owners deciding about their own applications, if switched on.** A program setting, off
  by default, on **Admin → Program → Decisions**: an application's accountable owner who is
  also a manager or a leader over it may record its decision, for a team too small for
  anyone else to. Each such decision is marked *Recorded by its own owner* on the decision,
  in the application's history, and on the Decisions page.
- **Guides:** a new guide, *Keeping current*; shaping the program in the app, scheduled work,
  and email in *Running the program* and *Configuration*; what a stale record costs in *The
  portfolio*; the new routes in the API guide; and pictures of the new screens.

### Changed

- **The default scoring model gains the cadence of wave 3:** how often records are
  confirmed and what a stale one costs, when reminders go, and how far ahead tasks are
  raised. An upgrade brings it to a model that nobody has changed since 0.1.0 or 0.2.0; one
  the organization has shaped is left alone and uses the same values until it says otherwise.

### Fixed

- **A bubble on the portfolio chart opened a page that was not there.** Links inside a
  drawing were followed by the wrong address. Clicking a bubble now opens its application,
  and hovering one shows which application it is and where it stands. Present since 0.1.0.
- **The demo's research software engineer** was named on no application, though the guides
  sent people to see the applications they keep. They now keep the two pieces of research
  software in the demo's storylines.

## 0.2.0 (2026-11-26)

Wave 2, *The landscape*: each application in its surroundings. What it sends and receives
and what data passes, what depends on it and what breaks if it goes, where it runs, what it
costs and what pays, the contracts behind it, what else does the same job, and what it is
built on that is falling out of support.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept.

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
- **Guides.** A new guide, *The landscape*; cost and contracts in *The portfolio*; and what an
  upgrade does to the program in *Running the program*.

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
