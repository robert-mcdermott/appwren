# Wave 1: The portfolio (v0.1.0)

**Goal:** prove the core loop. The organization knows what applications it runs and who answers for each; owners describe them and answer a short assessment; AppWren works out four scores with their working, a confidence figure, flags, and a recommendation; and a named person records what to do, on a record that cannot be quietly changed. Everything else in the roadmap builds on this loop being quick, clear, and trustworthy.

**Branch:** `wave-1` · **Target version:** `0.1.0` · **Status:** ◐ in progress

## Exit criteria

The wave is done when, on a fresh checkout:

1. `uv sync`, `uv run appwren init`, and `uv run appwren serve` produce a running system on SQLite with a first administrator, in under five minutes, with no other software installed (PLT-01).
2. The full test suite passes on SQLite and on PostgreSQL (PLT-02).
3. Signed in as each of the seven roles, a person sees and can do exactly what [security.md](../security.md) says, in the API and in the web app; a test fails if any route lacks a policy (PLT-03, PLT-04). Single sign-on with OpenID Connect works beside local accounts (PLT-13).
4. A steward imports an application list from a spreadsheet with a dry run that reports every problem by row, then fixes and loads it (INV-12).
5. An owner records an application with its accountable owner and other people in roles, its components and their technologies and versions, its vendor, its capabilities, the units that use it, and what it depends on; every record shows what it is linked to (INV-01 to INV-08, LND-01, LND-02).
6. The record shows which fields its lifecycle stage requires and which are missing (INV-13), and an organization's own field defined in the program appears on the form and the record (INV-11).
7. An owner answers the assessment: each question shows the definition of each level as it is chosen, *Don't know* is always available, and the scores and recommendation that would result update as they answer (SCR-05 to SCR-07).
8. The application shows four scores, data confidence, flags, and a recommendation; each opens its working, which can be redone by hand; unknown factors are listed with what would supply them; the worked example in [engine.md](../engine.md#a-worked-example) produces exactly the figures shown there (SCR-01 to SCR-04, SCR-08, SCR-09, DEC-01, DEC-02).
9. A manager, or a leader for their unit, records a decision with a rationale and a review date; a decision by the application's accountable owner is refused; a decision that differs from the recommendation shows a mismatch, on the application and on the dashboard; the snapshot taken with the decision reopens unchanged after the scoring model changes (DEC-03, DEC-04, SCR-10).
10. Sensitive fields are withheld from those without a role over the application in records, lists, filters, exports, the chart, and the working (PLT-14).
11. The portfolio chart places every application that can be placed, sized and colored as specified, with a table of the same points; the dashboard and data-quality pages' every figure opens a list whose length equals it, for every role (RPT-01 to RPT-03, CUR-01, CUR-02).
12. Every change above appears in the record's history with who, when, and before and after; `appwren verify` confirms the chain, and reports the exact event after a row is altered by hand (INV-09, PLT-05).
13. An administrator sets the product name, logo, palette, and accent in the app and sees them applied at once, in light and dark, with contrast checked (PLT-07, PLT-08).
14. `appwren demo` builds the demo organization in under a minute, and every wave 1 screen has convincing data (PLT-10).
15. The app passes the automated accessibility checks in every palette and mode (PLT-12); lint and the private-terms check are clean.

Requirements delivered: INV-01 to INV-14; LND-01, LND-02; CST-01, CST-02; SCR-01 to SCR-10; DEC-01 to DEC-05; CUR-01, CUR-02; RPT-01 to RPT-03; PLT-01 to PLT-15; INT-01; DOC-01.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Role names:** admin, manager, architect, leader, steward, auditor, member (slice 2).
- **Default palette:** Wren, with a deep spruce accent (slice 3).
- **Sensitive by default:** annual cost, sign-in method, backup and restore state (slice 4).
- **Dispositions:** Invest, Maintain, Tolerate, Modernize, Replace, Consolidate, Retire, Incubate, Assess (slice 5).
- **Thresholds:** 3.0 for value, health, and cost; 70% for confidence (slice 5).
- **Demo organization name:** Bramblewood Institute for Health Research (slice 8).
- **Connectors:** none in this wave; quiet by default, with opt-in connectors from wave 4 ([ADR-0003](../decisions/0003-quiet-by-default.md)).

---

## Slice 1: Foundation ☑

**Goal:** a skeleton in which the rules of the architecture are already enforced.

- [x] Project: `pyproject.toml` with the five runtime dependencies and the optional PostgreSQL driver, `uv.lock`, `.python-version`, `src/appwren` layout, `appwren` entry point, ruff and pytest configuration, Apache 2.0 `LICENSE` and `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- [x] Configuration: `appwren.toml` read with the standard library into frozen typed settings; unknown keys are errors; all problems reported together; environment overrides; secrets refused in the file
- [x] Data home: creation, marker, and checks
- [x] Database: engine for SQLite (write-ahead log, foreign keys on) and PostgreSQL; portable JSON and UTC date-time types; a naming convention for constraints; declarative ORM base; one session per request
- [x] Migrations: Alembic inside the package with no `alembic.ini`; revision `0001`; `appwren db upgrade | current`; `serve` refuses a schema that is behind
- [x] History: the `event` table; sessions that record every change to an audited row, with before and after values, in the same transaction; refusal of writes with no actor and of bulk statements on audited tables; the hash chain; `appwren verify`; triggers on both databases refusing update and delete
- [x] References: per-prefix counters that never reuse a number
- [x] Command line: `init`, `serve`, `db`, `verify`, `doctor`, with a reference page generated from the parser
- [x] API: the app factory, the envelope and problem-document conventions, security headers, health and `meta` endpoints, the static shell with a fallback route, `docs/openapi.json` kept current by a test
- [x] Tests on both databases: fixtures, a script to start a local PostgreSQL, `scripts/test-both.sh`
- [x] Continuous integration: lint, format check, tests on SQLite and PostgreSQL (the private-terms check runs locally, from git hooks, because its list is never published)
- [x] `scripts/check_terms.py` with pre-commit and commit-message hooks

**Acceptance (met):** a fresh clone initializes and serves an empty shell; the suite passes on both databases; altering an event row by hand is caught by `appwren verify`; a write that bypasses the service helper fails a test that compares table changes with events.

## Slice 2: Accounts, roles, and units ☑

**Goal:** people can sign in, and the system knows who may do what, where.

- [x] `account`, `credential`, `membership`, `role_grant`, `session_token`, `failed_sign_in`; scrypt hashing; password rules; throttling per account and address; `HttpOnly`, `SameSite=Strict` cookies; CSRF token and origin checks
- [x] `appwren init` creates the first administrator; `appwren users add | list | disable | enable | reset-password | roles`; `serve` refuses to start with no administrator
- [x] `role_grant` with unit scope for the seven roles; the principal, with the units each scoped role covers worked out at sign-in; the policy table as an app-wide dependency; refusal of any route without a policy
- [x] `org_unit` tree and `membership`; import of units and people from CSV with a dry run that lists every problem by row
- [x] Single sign-on: OpenID Connect with discovery, PKCE, and verified tokens, beside local accounts; accounts created at first sign-in; claims mapped to roles, unit scopes, and memberships in a table kept under Admin
- [x] API: session, accounts, roles, units, imports, and sign-on settings

**Acceptance (met):** the role-by-route matrix test signs in as each role and exercises every route, and a second test fails when a route has no policy or a policy has no route; a steward of a division covers its labs and no others; the last administrator can be neither demoted nor disabled, in the app, at the command line, or through the identity provider; CSRF, cross-site requests, throttling, idle and absolute expiry, sign-out, and the ending of sessions on disablement and password change are tested; a sign-in against a local test identity provider creates an account with its mapped roles.

## Slice 3: Web app and design system ☑

**Goal:** a shell that already looks and behaves like a finished product.

- [x] The sign-in page, user menu, password change, and Admin → People and units (accounts, roles, units, and the import screens); Admin → Single sign-on
- [x] `tokens.css`, `palettes.css` (Wren, Slate, Garnet), `base.css`, `components.css`, `pages.css`; light, dark, and system modes; the score ramp; the disposition hues
- [x] The wren mark as SVG: mark, mark with wordmark, single color; the default favicon
- [x] Core modules: DOM helper, router with URL state, API client with CSRF and caching, session and permissions, preferences
- [x] Components: shell, sidebar, top bar, page header, tabs, drawer, dialog, table, record chip, score figure, disposition badge, flag, stat tile, toast, form fields with server errors on their fields, empty and error states, skeletons
- [x] Command palette (⌘K, Ctrl-K, or `/`) and Escape to close anything open
- [x] Branding: the `setting` table, `/theme.css` generated from it, logo and tab-icon upload with type sniffing and SVG sanitizing, Admin → Appearance with a live preview in both modes and contrast results before saving
- [x] Home: for a new installation's administrator, a setup checklist that ticks itself off
- [x] Tests: no inline script or style, no third-party origins, no parsing of data as HTML, every import and route resolves, every script parses, size budgets, and contrast for the token pairs in every palette and mode

**Acceptance (met):** an administrator changes the organization name, palette, and accent in the browser and sees them applied at once, with no file touched; every palette passes AA for text, signal, score, disposition, and control-border tokens in both modes; the shell is within its size budget. 229 tests pass on SQLite and 225 on PostgreSQL (four are about the SQLite file). Checked in the browser: sign-in, the shell, and the setup checklist.

## Slice 4: Inventory ☐

**Goal:** the portfolio's records, done properly.

- [ ] Models and services for applications, components, vendors, technologies with releases, and capabilities, with the shared header
- [ ] A registry that describes each record type as data, so that adding, editing, finding, links, visibility, and history are written once
- [ ] People in roles on an application, with exactly one accountable owner past Proposed; the support unit; the units that use it; orphaned applications shown
- [ ] Components with their technologies, releases, and versions; each release shows the components that use it
- [ ] Capabilities as a tree; applications mapped to them, with at most one primary provider per capability
- [ ] Links between applications (depends on, part of, replaces) with forward and reverse labels; tags; external references
- [ ] Vocabularies and the organization's own fields as settings, with defaults from the default program pack; a value in use can be relabelled or retired, never removed; the definition of an application
- [ ] Required fields by lifecycle stage, and what is missing shown on the record
- [ ] Sensitive fields withheld by one function, everywhere
- [ ] The default program pack as a file, written by `scripts/build-default-program.py`, including the starter capability map; `appwren program export | import` with a dry run, the whole pack checked before any of it is loaded
- [ ] List pages with search, filters, sort, and paging, all in the URL; detail pages with a shared header and tabs; the History tab as a readable timeline
- [ ] Visibility: the catalog open to everyone signed in; restricted applications
- [ ] Optimistic concurrency on edits

**Acceptance:** each record type can be created, edited, linked, and found; every edit is in its history under a named operation; a table of what each of the seven roles sees, including sensitive fields, is tested for single records and for lists, which must agree; a stale edit is refused and an invalid one leaves the record as it was; a second accountable owner is refused.

## Slice 5: Assessment and the engine ☐

**Goal:** scores that explain themselves, from data that says how complete it is.

- [ ] `questionnaire` and `scoring_model` with immutable versions; the default question bank with a definition for every level; the default profiles, rules, guardrails, flags, and cadences
- [ ] The condition evaluator, with its own tests
- [ ] The engine as pure functions: facts to factor levels (answer, choice, band, computed), dimensions with floors, coverage, confidence, profile selection, rules, guardrails, flags, and the working
- [ ] The computed factors: technology currency, capability uniqueness, dependents, data exposure, end-of-life exposure, continuity
- [ ] A model that cannot be used says everything wrong with it in one pass: weights that do not add up, bands that do not rise, an unknown fact in a condition
- [ ] Gathering facts for an application, and for the whole portfolio in one pass
- [ ] Assessments: answers with notes, never edited, superseded by the next; expiry by tier from the cadence table
- [ ] The assess screen: the level picker with definitions and *Don't know*; the preview beside it
- [ ] The scorecard strip and the working on the application page; what would raise confidence
- [ ] Score snapshots, with the whole working, reopening unchanged after the model changes

**Acceptance:** the worked example produces exactly the figures in [engine.md](../engine.md#a-worked-example); every rule, guardrail, and flag has a test that makes it fire and one that keeps it quiet; an expired answer counts as unknown; a not-applicable factor changes neither score nor confidence; a profile in use cannot be changed; the preview and the recorded scores agree.

## Slice 6: Decisions and the portfolio chart ☐

**Goal:** a named person behind every disposition, and the whole portfolio on one picture.

- [ ] Decisions with disposition, rationale, review date, target date, and successor; the authority check and the refusal for the accountable owner; superseding
- [ ] The snapshot taken with each decision; the current disposition and review date copied to the application for lists
- [ ] Mismatches, on the application and as a list
- [ ] Portfolio snapshots, taken by a manager, with a page for each
- [ ] The portfolio chart: value against health, bubbles sized by cost where the viewer may see it and colored by risk exposure, thresholds and quadrants, filters, the table of the same points, the second view of value against cost and burden, and the applications that cannot be placed
- [ ] The Decisions list

**Acceptance:** a decision by the accountable owner, or by a leader outside their unit, is refused in the API and the app; a decision differing from the recommendation shows a mismatch until a new decision or a change in the recommendation removes it; the chart's points equal the list for the same filters, for every role, and no bubble's size reveals a withheld cost.

## Slice 7: Home, dashboard, and data quality ☐

**Goal:** one place to see what you owe, and one to see where the portfolio stands.

- [ ] Home: one list of what the person owes, most urgent first: applications they answer for with no assessment or an expired one, low confidence, missing required fields, decisions due for review, flags; for stewards, their unit's applications nobody answers for; for managers and leaders, mismatches and decisions due in scope
- [ ] The dashboard: counts by recommendation, by decision, by lifecycle, and by sourcing; mismatches; flags; confidence; end-of-life exposure. Each figure carries the filters of the list that produces it
- [ ] Data quality by unit
- [ ] Spreadsheet import of applications, with column mapping, a dry run, and updates by reference; CSV and JSON export of every list, with sensitive fields withheld as they are on screen and formula-like values made safe
- [ ] Print styles

**Acceptance:** every figure on the dashboard and data-quality pages opens a list whose length equals the figure, for each of the seven roles, for the whole organization and for one division; the parts of each breakdown add up to the whole; an import with one bad row loads nothing and names the row.

## Slice 8: Demo organization ☐

**Goal:** a believable institute that exercises everything in the wave.

- [ ] The generator: units, people, capabilities, vendors, technologies, applications, components, assessments, snapshots, and decisions, built through the services under a simulated clock, deterministic by seed
- [ ] The storylines in [demo-organization.md](../demo-organization.md), written by hand
- [ ] The "Demo data" marker, one-click sign-in as each sample person, and the refusal to listen beyond the local machine unless told to
- [ ] The demo build as an end-to-end test, with its history verified

**Acceptance:** `appwren demo` builds in under a minute; the same seed gives the same organization; every wave 1 screen has data worth reading; `appwren verify` passes on the result.

## Slice 9: Release prep ☐

- [ ] Guides in `docs/`: getting started, configuration, the portfolio (applications, assessment, scores, decisions), running the program, the command-line reference, the API guide
- [ ] `README.md` with the quickstart; `CHANGELOG.md` for 0.1.0
- [ ] The automated accessibility audit over every wave 1 screen in every palette and mode
- [ ] Fresh-clone install and quickstart checked on both databases
- [ ] Version `0.1.0`; pull request from `wave-1`; tag and release

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **Single sign-on arrives with accounts.** Organizations that keep an application portfolio almost always have an identity provider, and the people who own applications should not need another password. It is optional and sits beside local accounts.
- **No limits on roles.** A leader records decisions for every application in their units; there is no ladder of what a leader may decide, because a disposition is advice to a budget process, not an acceptance of harm.
- **The architect role.** The shared records (capabilities, technologies, vendors) need keepers who are not portfolio managers. Architects keep them and may assess any application in scope; they do not record decisions.
- **Three signals, three looks.** Scores are on a plum ramp with a bar, dispositions have their own hue and icon (outlined when recommended, filled when decided), and flags use the signal colors with a sentence. A test keeps every disposition hue readable on every surface in every palette.
