# Architecture

AppWren is a **modular monolith**: one Python package, one web process, one database, and a command-line tool that runs the same code. There are no message brokers, caches, search clusters, or worker fleets. A single machine is the reference deployment, and a laptop is enough to try it.

## System overview

```text
                              PEOPLE
        browser (vanilla JS app)          scripts and other systems
                 │                                   │
                 │ HTTPS / JSON                      │ API, tokens and webhooks (wave 7)
                 ▼                                   ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ Web API (FastAPI + uvicorn)                                     │
  │ /api/v1 · static web app · generated theme · access policy      │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  ┌───────────────────────────────▼────────────────────────────────┐
  │ Services  (the only code that writes)                           │
  │ inventory · capabilities · technology · assessment · engine ·   │
  │ decisions · oversight · connectors · reporting · program        │
  │        every write ──▶ permission check ──▶ event               │
  └──────┬───────────────────────┬───────────────────────┬─────────┘
         │ SQLAlchemy ORM        │ files by hash         │ queued mail
         ▼                       ▼                       ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ Database     │        │ Data home    │        │ SMTP         │
  │ SQLite, or   │        │ files/       │        │ (optional)   │
  │ PostgreSQL   │        │ exports/     │        └──────────────┘
  └──────▲───────┘        └──────────────┘
         │
  ┌──────┴───────────────────────────────────────────────────────┐
  │ Command line (appwren)                                       │
  │ init · serve · db · users · program · demo · verify · doctor │
  └──────────────────────────────────────────────────────────────┘
```

Nothing in this picture reaches out to the rest of the network unless an administrator says so. The only outbound connections AppWren ever makes are to the mail server and identity provider an administrator configures, from wave 4, to the sources of the connectors an administrator turns on, one by one, and from wave 7, to webhook addresses an administrator registers. See [ADR-0003](decisions/0003-quiet-by-default.md).

## Layers

| Layer | Package | Rule |
|---|---|---|
| **API** | `appwren.api` | Parses requests, calls one service function, shapes the response. No business rules, no queries |
| **Services** | `appwren.inventory`, `.assessment`, `.decisions`, … | All business rules. Every function that changes data takes the acting principal, checks permission, and writes through an audited session, which records an event for each change in the same transaction |
| **Model** | `appwren.db` | SQLAlchemy ORM models, portable column types, the engine and session, and migrations |
| **Core** | `appwren.core` | Shared, dependency-free pieces: the condition evaluator, clock, errors, colors, references |

The one rule that matters most: **only services write.** The API, the command line, the demo generator, imports, and scheduled jobs all go through the same service functions, so permission checks, validation, and history cannot be bypassed by taking a different door.

## Components

- **Program settings** (`appwren.program`). Everything the portfolio team configures: vocabularies, the organization's own fields, the questionnaire, the scoring model, cadences, and branding. Stored in the database, versioned, edited in the app, and exported or imported as a program pack. A built-in default pack is loaded by `appwren init`.
- **Condition evaluator** (`appwren.core.conditions`). One small interpreter for the declarative conditions used by profile selection, factor applicability, recommendation rules, guardrails, and flags. Data in, boolean out; no expression strings and no evaluation of code.
- **Engine** (`appwren.engine`). Pure functions from facts and a scoring model to factor levels, dimension scores, coverage, confidence, a recommendation, flags, and the working. No database: the facts are gathered by the assessment service and handed in, so the engine can be tested on its own and the worked example in [engine.md](engine.md) is a test.
- **Inventory** (`appwren.inventory`). Applications, components, vendors, technologies with their releases, and capabilities; people in roles; units that use an application; links, tags, and external references. A registry describes each record type as data, so that adding, editing, listing, links, visibility, and history are written once.
- **Assessment** (`appwren.assessment`). The questionnaire, assessments, gathering facts for the engine, previews, and score snapshots.
- **Decisions** (`appwren.decisions`). Dispositions with their rationale and review dates, and mismatches.
- **Oversight** (`appwren.oversight`, wave 3). Schedules, attestations, campaigns, triggers, and reminders.
- **Connectors** (`appwren.connectors`, wave 4). Opt-in, read-only readers for named sources, each run recorded, and the facts they supply kept with their source.
- **Planning** (`appwren.planning`, wave 5). Review cycles, initiatives, the roadmap, intake, and retirement plans.
- **Reporting** (`appwren.reporting`). The home page of what a person owes, the portfolio chart, the dashboard, exports, and later measures, trends, scenarios, and reports.
- **History** (`appwren.events`). The append-only event log, its hash chain, verification, and as-of reconstruction.
- **Access** (`appwren.auth`, `appwren.access`). Local accounts, sessions, single sign-on, role grants, sensitive fields, and the policy table that every route and service call is checked against.
- **Files** (`appwren.files`). Content-addressed storage in the data home for logos and, later, attachments, with size and type limits, and downloads that are always served as attachments.
- **Notifications and jobs** (wave 3). In-app notices, an email outbox, and a small scheduler whose jobs are rows with a lease, so exactly one process runs each.
- **Demo** (`appwren.demo`). Builds the fictional organization by calling the services in order with a simulated clock, so every record, assessment, decision, and event in the demo is real output of the real code. See [demo-organization.md](demo-organization.md).

## Request flow: assessing an application

1. The browser loads the application, the current questionnaire, and the application's latest scores and their working from `/api/v1`. As the owner answers, it asks `POST /api/v1/applications/{ref}/score-preview` with the draft answers, and shows the scores and recommendation that would result. The engine runs only on the server, so the preview and the record can never disagree.
2. On submit, `POST /api/v1/applications/{ref}/assessments` calls `assessment.record()`. In one transaction it checks that the principal may assess this application, validates the answers against the current questionnaire, writes the assessment, supersedes the previous one, and appends an event for each change.
3. The response carries the new scores, recommendation, and flags, which the owner sees at once, with the working one click away.

## Storage

- **Database.** SQLAlchemy 2 ORM with a synchronous engine and one session per request. SQLite is the default: a single file in the data home, in write-ahead-log mode, with foreign keys on. PostgreSQL is selected by a URL. The model uses only portable types (a JSON type that becomes `JSONB` on PostgreSQL, and a UTC date-time type that refuses naive values), a fixed naming convention for constraints, and no database-specific SQL in application code.
- **Migrations.** Alembic, driven from inside the package with no `alembic.ini`. Revisions are numbered in order and written to run on both databases (batch mode on SQLite). Migrations run when an administrator says so (`appwren init`, `appwren db upgrade`), never silently at startup; `appwren serve` refuses to start against a schema that is behind and says what to run.
- **Both databases from the first commit.** The whole test suite runs on SQLite and on PostgreSQL in continuous integration. Supporting a second database is cheap when it is never allowed to drift and expensive to retrofit.
- **Data home.** One directory holds everything that is not in the database: `files/` (evidence and attachments, stored by SHA-256), `brand/` (uploaded logos), `exports/`, and `logs/`. With SQLite the database file is here too, so backing up an installation is copying one directory.

## Web app

- **A static shell and a JSON API.** There are no server-side templates. `index.html` loads CSS and one ES module; the app fetches `/api/v1/meta` and `/api/v1/session`, then renders. Unknown paths return the shell so that the client-side router can handle them.
- **No build step, no frameworks.** Plain ES modules, a small DOM helper, a History API router in which the URL holds all view state, and one module per page. What is in the repository is what the browser runs.
- **Strict content security policy.** `default-src 'self'` with no inline script or style and no third-party origins. The DOM helper only ever inserts data as text.
- **Generated theme.** `/theme.css` is produced by the server from the branding settings and loaded after the built-in palettes, so an organization's colors apply without touching a file. See [ux.md](ux.md).
- **Charts, the portfolio chart, and graphs** are drawn as SVG by small modules in the app. No charting library.
- **Budgets.** The gzipped app shell stays under 100 KB and each lazily loaded part under 40 KB; tests enforce both, along with the rules above.

## API

- Everything the web app does, it does through `/api/v1`. There is no private back channel.
- Success responses are `{"data": …, "meta": …}`. Lists take `limit` and an opaque `cursor`. Errors are `application/problem+json`.
- Every route appears in one **policy table** that names the permission it requires. A route missing from the table is refused, and a test fails the build if one is added without a policy.
- The OpenAPI document is generated, committed as `docs/openapi.json`, and kept current by a test. The documentation site renders the API reference from it.
- Uploads are sent as the raw request body with the file name in a header, which avoids a multipart parser.

## Configuration

AppWren separates two kinds of configuration by one rule: **the deployment lives in a file; the program lives in the database.**

| | Deployment | Program |
|---|---|---|
| **What** | Server address and port, database URL, data home, sign-in providers, mail server, session lifetimes, connector credentials (by environment variable) | Vocabularies, fields, the questionnaire, the scoring model, cadences, the capability map, connectors enabled, branding |
| **Where** | `appwren.toml`, with environment overrides (`APPWREN_<SECTION>_<KEY>`) | The database |
| **Who** | The administrator who runs the server | The manager and admin roles, in the app |
| **Changes** | Take effect on restart | Take effect at once, on every worker, and are recorded as events |
| **Moves by** | Copying the file | Exporting and importing a program pack |

The file is read with the standard library's TOML parser into typed, frozen settings. Unknown sections and keys are errors, every problem is reported in one pass, and relative paths resolve against the file's own directory so an installation moves as a unit. **Secrets never go in the file**: a key that looks like a secret is rejected, and the file instead names the environment variable that holds it.

## Runtime and deployment

- `appwren serve` runs uvicorn with one or more workers. All state is in the database, so workers share nothing in memory that matters.
- Sign-in is always required. `appwren init` creates the first administrator, and the server refuses to start without one.
- Behind a reverse proxy that terminates TLS, AppWren reads `X-Forwarded-Proto` and `X-Forwarded-Host` to set secure cookies, check request origins, and build sign-in redirects.
- Health endpoints: `/api/v1/health/live` and `/api/v1/health/ready` (database reachable and schema current).
- Deployment recipes (a container image, a compose file with PostgreSQL, a hardened systemd unit, and proxy examples) arrive in wave 7 under `deploy/`.

## Directory layout

```text
appwren/
├── pyproject.toml · uv.lock · .python-version
├── README.md · CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE · NOTICE
├── appwren.example.toml
├── spec/                      this folder
├── docs/                      guides (the site's source), images, openapi.json
├── deploy/                    container, systemd, proxy (wave 7)
├── scripts/                   check_terms.py, dev-postgres.sh, test-both.sh, pack builders, site/
├── tests/                     pytest suite, js/ tests, fixtures
└── src/appwren/
    ├── __init__.py · __main__.py · config.py · home.py
    ├── core/                  conditions, clock, errors, colors, log
    ├── db/                    engine, session, types, refs, models/, migrations/
    ├── auth/                  passwords, sessions, oidc
    ├── access/                roles, principal, policy table
    ├── events/                event log, chain, actor
    ├── people/                accounts, units, imports
    ├── program/               settings, vocabularies, fields, packs, branding
    ├── engine/                factors, dimensions, rules, the working
    ├── inventory/ · assessment/ · decisions/
    ├── oversight/                      (wave 3)
    ├── connectors/                     (wave 4)
    ├── planning/                       (wave 5)
    ├── reporting/
    ├── demo/                  the fictional organization
    ├── api/                   app factory, routers/, problems, security headers, static
    ├── cli/                   argparse commands, doctor, generated reference
    ├── resources/             example config, default program pack
    └── web/static/            index.html, css/, js/core, js/components, js/pages, img/
```

## Cross-cutting concerns

| Concern | Approach |
|---|---|
| **Time** | UTC everywhere in storage; an injectable clock, so tests and the demo can run at any date |
| **Identifiers** | Integer keys inside; permanent prefixed references outside ([data-model.md](data-model.md#conventions)) |
| **Errors** | One exception hierarchy; the API maps it to problem documents and the command line to messages and exit codes |
| **Validation** | At the service boundary, so the API, imports, and the command line get the same answers |
| **Concurrency** | Optimistic: records carry a version, and a stale edit is refused with the current values, never silently overwritten |
| **Visibility** | One function per record type decides what a principal may see; single records, lists, counts, and exports all call it |
| **Logging** | Standard library logging to the console and the data home; no request bodies or answers are logged |
| **Security** | [security.md](security.md) |
| **Testing** | pytest, offline, on both databases; a role-by-route matrix test; JavaScript tests with Node's built-in runner; the demo build as an end-to-end test |
| **Private terms** | A script checks committed content against a local, untracked list of words that must not appear |

## Dependency budget

Every runtime dependency must justify itself, and adding one requires a decision record.

| Package | Why |
|---|---|
| `fastapi` | The web framework and OpenAPI generation (brings `pydantic` and `starlette`) |
| `uvicorn` | The server |
| `sqlalchemy` | The ORM, and one model for two databases |
| `alembic` | Migrations |
| `httpx` | Calls to the identity provider and, later, webhooks; also the test client |
| `psycopg` *(optional extra)* | The PostgreSQL driver, installed only when PostgreSQL is used |

Deliberately absent, with what is used instead:

| Not used | Instead |
|---|---|
| A template engine | A static shell and the JSON API |
| A password-hashing package | `hashlib.scrypt` from the standard library |
| A JOSE or OpenID Connect package | A few hundred lines over the standard library and `httpx` ([ADR-0008](decisions/0008-accounts-and-single-sign-on.md)) |
| A multipart parser | Raw-body uploads |
| A task queue or broker | Leased job rows in the database |
| A search engine | A search table in the same database |
| A PDF library | Print styles; the browser prints to PDF |
| A spreadsheet library | CSV, read and written with the standard library |
| A YAML parser | TOML for the deployment file and JSON for packs, both in the standard library |
| Any JavaScript package | Hand-written ES modules |

Development adds only `pytest` and `ruff`. The documentation site and screenshot capture need Node 22 and no packages ([ADR-0009](decisions/0009-documentation-toolchain.md)).
