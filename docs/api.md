# API

Everything the web app does, it does through a JSON API under `/api/v1`. This guide covers how to sign in, how answers and errors are shaped, how lists page, and what routes there are. The exact shape of every request and answer is in the OpenAPI document: [openapi.json](openapi.json) in this directory, or `/api/openapi.json` on a running server.

This release has no API tokens. A program signs in as an account, with that account's password, and holds a session as a browser does. Tokens scoped to a role arrive with integrations in a later release; see the [roadmap](../spec/roadmap.md).

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
| `mine` | `true` for only the records you are named on |

Each kind of record adds its own filters, such as `lifecycle`, `sourcing`, `tier`, and `domain` for applications. The OpenAPI document lists them.

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

`{records}` is one of `applications`, `components`, `vendors`, `technologies`, or `capabilities`. A record is addressed by its reference, such as `APP-0042`.

| Route | What it does |
|---|---|
| `GET /{records}` · `POST /{records}` | List; add one (applications: a steward, architect, or manager in scope; vendors, technologies, capabilities: an architect or manager) |
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

### Reports, import, and export

| Route | What it does |
|---|---|
| `GET /portfolio` | Every application you may see, with its scores, recommendation, decision, flags, and what its record lacks. Takes the dashboard's filters, such as `recommendation`, `decision`, `flag`, `quality`, `mismatch`, and `review_due` |
| `GET /home` | What is waiting on the signed-in person |
| `GET /dashboard` · `GET /data-quality` | The figures, each with the filters that give its list from `/portfolio`. Take `unit`, and the dashboard `domain` |
| `GET /exports/{kind}` | `applications`, `components`, `vendors`, `technologies`, `capabilities`, or `portfolio`, as `format=csv` or `format=json`, with the same filters as the list |
| `GET /imports/applications/fields` | The fields a file of applications may hold, and the headings each is known by |
| `POST /imports/applications` | A CSV file as the body (`text/csv`). `dry_run` is `true` unless you say otherwise; `mapping` says which column holds each field where the headings differ |

## What the API will not do

- It never returns a record you may not see, and never counts one.
- It never returns a sensitive field you may not see, and refuses to filter or sort by one, or to take a value for one.
- It never edits an assessment or a decision. Each is superseded by a new one.
- It never lets a person record a decision about an application they are accountable for.
- It never takes a score. Scores are worked out from the record and the answers.
- It never changes the history. There is no route that does.
