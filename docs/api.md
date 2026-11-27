# API

Everything the web app does, it does through a JSON API under `/api/v1`. This guide covers how to sign in, how answers and errors are shaped, how lists page, and what routes there are. The exact shape of every request and answer is in the OpenAPI document: [openapi.json](openapi.json) in this directory, or `/api/openapi.json` on a running server.

A program signs in as an account, with that account's password, and holds a session as a browser does. The one exception is posting facts: a tool holding a **push key** an administrator issued posts to `POST /api/v1/facts` with the key and no session, and can do nothing else with it (see [Facts from other systems](signals.md#push-sources)).

Until 1.0, routes may change between releases. Changes are listed in the [changelog](../CHANGELOG.md).

## Sign in

```bash
curl -s -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"email": "you@example.org", "password": "…"}' \
  http://127.0.0.1:8000/api/v1/session
```

The answer describes who you are, and sets a session cookie, `appwren_session`:

```json
{
  "data": {
    "account": {"id": 12, "name": "Your Name", "email": "you@example.org"},
    "roles": ["manager", "member"],
    "permissions": {"…": true},
    "units": {"manager": null},
    "member_units": [4],
    "has_password": true,
    "csrf_token": "…"
  },
  "meta": {}
}
```

Everyone holds `member`. In `units`, each scoped role lists the units it covers, or `null` for the whole organization. `permissions` says what the account may do somewhere, such as `manage` or `architect`; whether it may do it to a given record is decided by that record.

`GET /api/v1/session` returns the same for the session you hold, or 401 if you hold none. `DELETE /api/v1/session` signs out.

## Changing things

Every request that changes anything (`POST`, `PUT`, `PATCH`, `DELETE`) must carry the session's CSRF token in a header:

```bash
curl -s -b cookies.txt -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: …' \
  -d '{"name": "Freezer Watch", "sourcing": "built_here", "lifecycle": "active", "tier": "2", "org_unit_id": 4}' \
  http://127.0.0.1:8000/api/v1/applications
```

Without it the answer is 403. If the request carries an `Origin` header, it must match the host, or the request is refused.

### Editing a record someone else is editing

Records carry a `version`. Send the version you read with a `PATCH`, and if someone else has changed the record since, the answer is 409 and nothing is saved. Read it again and decide what to do.

## Answers

Every successful answer has the same envelope:

```json
{"data": …, "meta": {…}}
```

`data` is one object or a list. `meta` carries what is about the answer and not in it: paging for a list, or a count of what else changed.

Times are UTC in ISO 8601. Dates with no time, such as a review date, are `YYYY-MM-DD`.

## Errors

Errors are problem documents (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "The decision was not recorded.",
  "errors": [
    {"location": ["rationale"], "message": "Say why. The next person to look at it will want to know."}
  ],
  "instance": "/api/v1/applications/APP-0042/decisions"
}
```

| Status | Meaning |
|---|---|
| 400 | The request could not be carried out as asked |
| 401 | Nobody is signed in, or the email address and password do not match |
| 403 | You are signed in but may not do this, or the CSRF token is missing. `detail` says which |
| 404 | No such thing, or none that you may see. The two are not told apart |
| 409 | A conflict: the record changed since you read it, or the thing is already so |
| 413 | The request is larger than 32 MB |
| 422 | A value is missing or not allowed. `errors` names each field |
| 429 | Too many failed sign-ins. Wait a few minutes |
| 503 | The database is unavailable |

## Lists

Every list route takes the same parameters:

| Parameter | Meaning |
|---|---|
| `q` | Words to look for in the name, reference, or summary, or in what the record is called in another system |
| `unit` | A unit's id. Includes every unit beneath it |
| `sort` | A field name. Start with `-` for descending. The default is `-updated_at` |
| `limit` | How many to return: 50 by default, 200 at most |
| `cursor` | Where to continue from: `next_cursor` or `prev_cursor` from the last answer |
| `owner` | An account's id: only the records that person is named on |
| `technology`, `release`, `version` | Applications and components built on a technology's reference; with `release`, one of its releases by cycle (`none` for those that name none); with `version`, an exact version or its start. An application counts when any of its components does |
| `mine` | `true` for only the records you are named on |

Each kind of record adds its own filters, such as `lifecycle`, `sourcing`, `tier`, `domain`, `data_class`, and `capability` for applications; `application` and `data_class` for interfaces; `platform_id` and `environment` for deployments; and `ending_within` (days) for contracts. The OpenAPI document lists them.

A list's `meta` says where the page sits:

```json
{"total": 107, "offset": 0, "next_cursor": "eyJvZmZzZXQiOjUwfQ", "prev_cursor": null}
```

A list returns only what you may see, and `total` counts only that.

## Routes

Every route requires a signed-in account except those marked public. What a route allows beyond that depends on the record: its unit, the people named on it, and whether it is restricted. See [Running the program](running-the-program.md#roles-and-scope).

### System and session

| Route | What it does |
|---|---|
| `GET /health/live` · `GET /health/ready` | Whether the server is up, and whether it can serve (public) |
| `GET /meta` | Product name, version, branding, palettes, and, on a demo, its sample people (public) |
| `GET` · `POST` · `DELETE /session` | Who is signed in; sign in; sign out |
| `POST /session/demo` | Sign in as one of a demo's sample people (public; 404 unless this is a demo) |
| `POST /session/password` | Change your own password |
| `GET /sso/start` · `GET /sso/callback` | The single sign-on round trip, for a browser (public; 404 unless it is set up) |
| `GET /sso` · `POST /sso/check` · `PUT /sso/mappings` | How single sign-on is set up; check the connection; set which provider roles give which roles here (admin) |

### People and units

| Route | What it does |
|---|---|
| `GET /accounts` · `POST /accounts` | Find people; add an account (admin) |
| `GET` · `PATCH /accounts/{id}` | One account; change it |
| `PUT /accounts/{id}/roles` · `PUT /accounts/{id}/units` | Set its roles and units (admin) |
| `POST /accounts/{id}/password` | Set a password for someone (admin) |
| `GET /roles` | The roles and what each allows |
| `GET /units` · `POST /units` · `GET` · `PATCH /units/{id}` | The organization's units |
| `POST /imports/units` · `POST /imports/people` | Import from CSV, with `dry_run` (admin) |
| `GET` · `PUT /admin/branding` · `POST /admin/branding/check` | Names, palette, accent, and score colors; check them without saving (admin) |
| `POST` · `DELETE /admin/branding/images/{kind}` | Upload or remove a logo or the tab icon (admin) |

### Records

`{records}` is one of `applications`, `components`, `interfaces`, `deployments`, `contracts`, `funding-sources`, `vendors`, `technologies`, `hosting-platforms`, or `capabilities`. A record is addressed by its reference, such as `APP-0042`.

| Route | What it does |
|---|---|
| `GET /{records}` · `POST /{records}` | List; add one. Applications: a steward, architect, or manager in scope. Components, deployments, and interfaces: whoever keeps the application (for an interface, either of the two). Contracts: a steward, architect, or manager. Vendors, technologies, capabilities, hosting platforms, and funding sources: an architect or manager |
| `GET` · `PATCH /{records}/{ref}` | One record with everything about it; change it. Send the `version` you read. `external_refs` sets what it is called in other systems |
| `GET /{records}/{ref}/history` | Its history |
| `POST /{records}/{ref}/links` · `DELETE /{records}/{ref}/links/{id}` | Link two records (depends on, is part of, replaces); unlink them |
| `PUT /applications/{ref}/people` | Name the people in each role. Exactly one is accountable |
| `PUT /applications/{ref}/capabilities` | The capabilities it serves, and whether it is the primary provider of each |
| `PUT /applications/{ref}/units` | The other units that use it |
| `PUT /components/{ref}/technologies` | The technologies a component is built on, and which release of each |
| `PUT /technologies/{ref}/releases` | A technology's releases and their support dates (an architect or manager) |
| `GET /vocabularies` · `GET /catalog` | Every vocabulary; the fields of each kind of record, the definition, and what each stage requires |
| `GET /capability-map` | The capabilities in their areas, with how many applications serve each |
| `PUT /contracts/{ref}/applications` | The applications a contract covers, and the licenses each uses |

### Assessment, scores, and decisions

| Route | What it does |
|---|---|
| `GET /questionnaire` · `GET /scoring-model` | The current questions and scoring model |
| `GET /applications/{ref}/scores` | Its scores, coverage, confidence, recommendation, flags, and the working of each |
| `POST /applications/{ref}/score-preview` | The scores some answers would give, from the same engine. Nothing is saved |
| `GET` · `POST /applications/{ref}/assessments` | Its assessments; record a new one |
| `GET` · `POST /applications/{ref}/decisions` | Its decisions; record a new one (a manager, or a leader of its unit, who is not its accountable owner) |
| `GET /score-snapshots/{id}` | The scores a decision was made against, as they were |
| `GET` · `POST /portfolio-snapshots` · `GET /portfolio-snapshots/{ref}` | Portfolio snapshots; take one (manager); one with every application as it was |

An assessment's `answers` maps each question's key to a level from 1 to 5, to `null` for *don't know*, or to `{"level": 4, "note": "…"}`. The default keys are `strategic_fit`, `functional_fit`, `future_need`, `reliability`, `maintainability`, `vendor_viability`, `support_effort`, `change_effort`, and `compliance`.

```bash
curl -s -b cookies.txt -H 'Content-Type: application/json' -H 'X-CSRF-Token: …' \
  -d '{"disposition": "modernize", "rationale": "Move it off the old runtime before the grant ends.", "review_on": "2027-06-30"}' \
  http://127.0.0.1:8000/api/v1/applications/APP-0042/decisions
```

### The landscape, and cost

| Route | What it does |
|---|---|
| `GET /data-flows` | How many interfaces carry each class of data; with `data_class`, every interface that carries it and every application that holds it. `undeclared` on an interface lists the classes its receiver's record does not list |
| `GET /graph/{ref}` | Any record and what it is joined to, in groups; `hidden` counts what the reader may not see |
| `GET /applications/{ref}/impact` | What depends on it, directly and beyond; the interfaces that would stop; the capabilities left with nothing; the people and units affected |
| `GET /overlap` | Capabilities served by more than one application in service, with those applications side by side. Takes `unit` and `domain` |
| `GET /capability-heat` | The capability tree, each capability with how many serve it, their average scores and confidence, and the health of the weakest |
| `GET /lifecycle` · `GET /radar` | Technology releases to their end of support, with what runs on each; technologies in use by ring |
| `POST /imports/end-of-life` | Releases and support dates from a JSON body of end-of-life data. `dry_run` is `true` unless you say otherwise (an architect or manager) |
| `GET /applications/{ref}/costs` · `PUT /applications/{ref}/cost-lines` | Its cost lines, totals by category, cost per user, and the contracts that cover it, or `withheld`; replace the lines |
| `GET /data-handling` | How many applications handle each class of data; with `data_class`, each of them with its owner, hosting, sign-in, technology support, interfaces, and data agreement |
| `GET /history` | Every change, newest first: `actor`, `about` (a reference), `kind`, `since`, `until`, and `before` for the next page (managers for the whole organization, auditors, administrators) |

### Reports, import, and export

| Route | What it does |
|---|---|
| `GET /portfolio` | Every application you may see, with its scores, recommendation, decision, flags, and what its record lacks. Takes the dashboard's filters, such as `recommendation`, `decision`, `flag`, `quality`, `mismatch`, and `review_due` |
| `GET /home` | What is waiting on the signed-in person |
| `GET /dashboard` · `GET /data-quality` | The figures, each with the filters that give its list from `/portfolio`. Take `unit`, and the dashboard `domain` |
| `GET /exports/{kind}` | Any `{records}` above, `portfolio`, or `data-handling` (with `data_class`), as `format=csv` or `format=json`, with the same filters as the list |
| `GET /imports/applications/fields` | The fields a file of applications may hold, and the headings each is known by |
| `POST /imports/applications` | A CSV file as the body (`text/csv`). `dry_run` is `true` unless you say otherwise; `mapping` says which column holds each field where the headings differ |

### Keeping current

| Route | What it does |
|---|---|
| `GET /notices` · `GET /notices/count` · `POST /notices/read` | Your notices, newest first; how many are unread; mark some read (`ids`), or all |
| `GET` · `PUT /session/preferences` | How notices reach you by email: `immediate`, `digest`, or `none` |
| `GET` · `POST /applications/{ref}/confirmations` | When its record was last confirmed and is next due, and every confirmation; confirm it, with an optional `note` (whoever is named on it, its unit's stewards, managers) |
| `GET /campaigns` · `POST /campaigns` · `POST /campaigns/preview` | Campaigns with their progress; start one; what one would ask, and of whom, saving nothing (stewards and managers, for their units) |
| `GET /campaigns/{ref}` | A campaign, its coverage by unit, and its items. Takes `unit`, `status`, and `mine` |
| `POST /campaigns/{ref}/remind` · `/close` · `/cancel` · `/items/{id}/excuse` | Remind those still to do it; close it; cancel it; excuse one application with a `reason` |
| `GET /tasks` · `GET /tasks/{id}` · `POST /tasks/{id}/close` | Open tasks you may see (`mine`, `status`, `kind`, `unassigned`); one task; mark it `done` or `dismissed` with a `note` |
| `GET /accounts/{id}/holdings` · `POST /accounts/{id}/hand-over` | What a person holds; pass all of it `to` another (administrators and managers) |
| `GET /search` | One search across every kind of record: `q`, and `type` for one kind |
| `GET` · `POST /views` · `PATCH` · `DELETE /views/{id}` | Your saved views of a list (`path`), and the shared ones; save, change, or delete one |
| `GET /similar-applications` | Applications a new one may be already: `name`, `aliases`, `vendor`, `product`, and `except` for its own reference |
| `GET` · `POST /applications/{ref}/contests` · `GET /contests` · `POST /contests/{id}/answer` | Contests of its scores; contest a factor; those waiting for your answer; accept or answer one (a manager or architect) |

### Facts from other systems

See [Facts from other systems](signals.md).

| Route | What it does |
|---|---|
| `GET /connectors` · `POST /connectors` | The kinds of source and the connectors set up; add one, switched off, with its `kind`, `key`, `name`, `settings`, and the `credential_env` that holds its credential (admin) |
| `GET` · `PATCH /connectors/{key}` | A connector and its recent runs; change it, or switch it on or off with `enabled` (admin) |
| `POST /connectors/{key}/check` · `POST /connectors/{key}/run` | Whether it reaches its source, writing nothing; run it now (admin) |
| `GET /sourced/{ref}` | What sources supply for a record you may see, each value with its source, when it was read, and any override; for a technology, its releases' too; for an application, its components' |
| `POST` · `DELETE /sourced/{ref}/{field}/override` | Override a value with a `value` and a `reason`, and a technology's `release` where it is one of a release's; remove the override (whoever keeps the record) |
| `GET /discovered` · `POST /discovered/{id}/add` · `/dismiss` · `/restore` | Applications registered with the identity provider that are not on record (`show`: `new`, `dismissed`, `added`, `all`); add one in an `org_unit_id`; dismiss one with a `reason`; list it again (stewards, architects, managers) |
| `GET` · `POST /push-keys` · `DELETE /push-keys/{id}` | Push keys; issue one, shown in the answer this once; revoke one (admin) |
| `POST /facts` | Facts from a push source, with its key as `Authorization: Bearer <key>` and no session: `facts`, each with `record`, `field`, `value`, and optionally `observed_at` and `release`. Checked whole: one bad fact writes nothing |
| `GET` · `POST /applications/{ref}/catalog` | The application and its components as a catalog file (YAML); bring one in, sent as the body, with `dry_run` (the default) saying what would change |
| `GET /maturity` · `GET /maturity/{ref}` | How many applications are at each engineering maturity level under each unit below `unit`; an application's or a component's level, checks, and what it needs for the next |

### Planning change

See [Planning change](planning-change.md).

| Route | What it does |
|---|---|
| `GET` · `POST /reviews` · `GET` · `PATCH /reviews/{ref}` | Portfolio reviews, as records with a unit, `held_on`, a `chair_id`, and `tiers`; one review, with its agenda. Planned and changed by managers and the unit's leaders |
| `POST /reviews/{ref}/draw` | Add to the agenda what needs deciding in its scope now: a decision that differs from the recommendation, one due for review by its date, or none. `meta.added` says how many |
| `POST /reviews/{ref}/items` · `DELETE /reviews/{ref}/items/{id}` | Put an `application` on the agenda with a `note`; take one off |
| `POST /reviews/{ref}/open` · `POST /reviews/{ref}/close` | Open it, from when a decision recorded for an item is shown on it; close it, keeping each item's decision. A closed review changes no more |
| `GET` · `POST /initiatives` · `GET` · `PATCH /initiatives/{ref}` | Initiatives, as records with a `kind`, a `stage`, an `owner_id`, `starts_on`, `ends_on`, and a `budget`; filtered by `application` too |
| `PUT /initiatives/{ref}/applications` | The `applications` it changes, each with its `application`, its `action` (`changes`, `retires`, or `receives`), and a `note` |
| `GET /roadmap` | Initiatives with their dates, for a timeline: by `unit`, `kind`, or `stage`, and `closed` for those done or cancelled |
| `GET` · `POST /requests` · `GET` · `PATCH /requests/{ref}` | Requests for something new, as records with a `capability_id`, `requested_by_id`, `users_expected`, and `needed_by`; one request, with what already serves its capability and what is named like it. Anyone may ask |
| `PUT /requests/{ref}/options` | The ways to meet it: each with an `approach` (`build`, `buy`, `partner`, or `reuse`), a `name`, a `vendor` or an `application`, an `annual_cost`, a `fit` of 1 to 5, and `notes` |
| `POST /requests/{ref}/approve` · `/meet` · `/decline` | End it once, with a `reason`: approved, adding a proposed application (`name` if not the request's); met by an `application` on record; or declined |
| `GET` · `POST` · `DELETE /applications/{ref}/retirement` | Its retirement plan and checklist; start one with `planned_on` and a `note`; cancel an open one |
| `PUT /applications/{ref}/retirement/steps/{step}` · `POST /applications/{ref}/retirement/complete` | Mark a step `done`, or not, with a `note`; complete the plan, every step done, retiring the application and keeping its savings |
| `GET /retirements` | Retirements under way and done, with the savings by year |

### Insight

See [Insight](insight.md).

| Route | What it does |
|---|---|
| `GET /trends` | How the portfolio moved from the snapshot `before` to the snapshot `after`, or to today without one: the figures each held, what moved, and the decisions recorded between them |
| `GET /applications/{ref}/score-history` | Its scores at each portfolio snapshot and each decision, oldest first |
| `GET /shares` | The costliest tenth, the dearest tenth per user, the least used fifth, and the oldest fifth of the applications in service |
| `GET` · `POST /reports` · `GET /reports/{ref}` | Leadership reports, the latest period first; make one with a `title`, `period_from`, and `period_to` (a manager); one report as it was made, with its `digest` and whether it is `intact`. Read by those who may see every record |
| `GET /as-of` · `GET /applications/{ref}/as-of` | The portfolio `on` a day: the applications in service at its end, each with its stage, unit, tier, and decision then and now; one application on a day, each value then beside now, with its decision and scores then. Read from the history |
| `GET` · `POST /scenarios` · `GET` · `PATCH /scenarios/{ref}` | Scenarios, as records with a `name` and `summary`, kept by architects and managers; one scenario, with its `changes` and their `effect`: `cost_saved`, `people`, `interfaces`, `capabilities`, and `risk` |
| `PUT /scenarios/{ref}/changes` | The `changes` it would make: each an `application`, an `action` (`retire`, `consolidate`, or `replace`), the application it moves `into` or is replaced by, and a `note`. Changes no application |
| `POST /scenarios/{ref}/initiative` | Make a proposed initiative of it, with a `name` and `org_unit_id` if not its own; the scenario then changes no more |

### The program and the installation

| Route | What it does |
|---|---|
| `GET /program` | The program as it stands, and which lists may only be renamed (managers for the whole organization, administrators) |
| `PUT /program/vocabularies/{name}` · `PUT /program/fields` · `PUT /program/questionnaire` | Save a list, the organization's own fields, or new wording of the questions |
| `PUT /program/decision-rules` | `owners_may_decide`: whether an application's accountable owner, if also a manager or leader over it, may record its decision; `stage_gates`: whether an application may move to a later stage only with what that stage requires. Send either or both |
| `POST /program/scoring/preview` · `PUT /program/scoring` | Every application a changed scoring model would change; publish it as a new version |
| `GET /jobs` · `POST /jobs/{key}/run` · `PUT /jobs/{key}` | Scheduled work and its recent runs; run a job now; pause or resume one (admin) |
| `GET /mail` · `POST /mail/test` | How email is set up and doing; send yourself a test message (admin) |

## What the API will not do

- It never returns a record you may not see, and never counts one.
- It never returns a sensitive field, a cost line, or a contract you may not see, and refuses to filter or sort by a sensitive field, or to take a value for one.
- It never gives a total of cost that includes a part you may not see.
- It never reaches out to anything an administrator has not switched on: until a connector is on, support dates arrive only in a file someone sends. A connector only reads.
- It never edits an assessment or a decision. Each is superseded by a new one.
- It never lets a person record a decision about an application they are accountable for.
- It never takes a score. Scores are worked out from the record and the answers; a contest says one is wrong, and moves nothing.
- It never changes the history. There is no route that does.
