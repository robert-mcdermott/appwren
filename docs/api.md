# API

Everything the web app does, it does through a JSON API under `/api/v1`. This guide covers how to sign in, how answers and errors are shaped, how lists page, and what routes there are. The exact shape of every request and answer is in the OpenAPI document: [openapi.json](openapi.json) in this directory, or `/api/openapi.json` on a running server.

A program reaches the API in one of four ways:

- **As an account, with a session.** It signs in with the account's email address and password and holds the session cookie, as a browser does. See [Sign in](#sign-in).
- **With an API token** an administrator issued for one role, sent with each request and no session. See [Sign in as another system](#sign-in-as-another-system).
- **With a token of a person's own**, which acts as that person, reads, and proposes changes. See [A token of your own](#a-token-of-your-own).
- **With a push key**, which only posts facts to `POST /api/v1/facts` and can do nothing else (see [Facts from other systems](signals.md#push-sources)).

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

Without it the answer is 403. A change is also refused with 403, whether or not anyone is signed in, when the request comes from another site: when it carries `Sec-Fetch-Site: cross-site`, or an `Origin` header that does not match the host.

## Sign in as another system

A script or another system signs in with an **API token** instead of a session. An administrator issues one under **Admin → API tokens**, or with `POST /admin/tokens`: for one role (any but administrator), for one unit and those beneath it if the role has a unit, for reading only unless they say otherwise, and until a day at most a year away, 90 days from now if no day is given. At most 50 issued tokens are live at once. The answer, `201 Created`, holds the token itself, `token`, shown this once, and its `prefix`, the first ten characters, by which lists and the history name it; only its SHA-256 is kept. Send it with each request:

```bash
curl -s -H 'Authorization: Bearer awt_…' http://127.0.0.1:8000/api/v1/applications
```

A token sees and may do what its role may, and nothing more. A reading token is refused any change with 403. A change made with a token is recorded in the history against the token's name and prefix, such as `Nightly sync (token awt_x7Kp2q)`. A token stands for a role, not a person, so `mine` means nothing to it: a list given `mine=true` is not narrowed. A token needs no CSRF token, since no browser is involved, and never signs in to the web app. One that is revoked or has expired is refused with 401 at once.

### A token of your own

Anyone may make a token of their own under **Your account → Your API tokens**, or with `POST /tokens` while signed in: at most ten live at once, each for 90 days unless they give another day up to a year away, its `token` and `prefix` in the answer this once. It acts as them, so it sees exactly what they see; it reads, and it proposes changes, and it changes nothing itself. A proposal is a **suggestion** on an application: a value for one field, with a note saying why. It waits on the application's page until someone who keeps the application accepts it, which is their own edit, checked by the usual rules and kept in the history under their name, or dismisses it.

```bash
curl -s -H 'Authorization: Bearer awt_…' -H 'Content-Type: application/json' \
  -d '{"field": "users", "value": 95, "note": "The sign-in log says so"}' \
  http://127.0.0.1:8000/api/v1/applications/APP-0024/suggestions
```

A personal token is revoked when its owner's password changes or their account is disabled. Whatever its owner's roles, it never administers. What it proposes is recorded under its owner's name and its prefix, such as `Your Name (token awt_x7Kp2q)`.

## Let an AI assistant read AppWren

An assistant that speaks the Model Context Protocol can read AppWren, and propose changes, through a small tool server that comes with it. The assistant's host program starts it; give it the address of your AppWren and a token of the person's own:

```json
{"mcpServers": {"appwren": {
  "command": "uv", "args": ["run", "--directory", "/opt/appwren", "appwren", "tools", "serve"],
  "env": {"APPWREN_URL": "https://apps.example.org", "APPWREN_TOKEN": "awt_…"}}}}
```

Its tools: `search`, `get_record`, `list_applications`, `check_application` (the checkpoint), `my_work` (what is waiting on the person), and `suggest_change`. It cannot change a record, decide, or accept its own proposal; every call goes through the API as the person, so it sees nothing they may not.

## Ask whether an application is approved

A purchasing form, a data access request, or a project intake can cite an application's reference and ask AppWren whether it is approved, with any token or session:

```bash
curl -s -H 'Authorization: Bearer awt_…' \
  'http://127.0.0.1:8000/api/v1/checkpoint/APP-0024?data_class=identifiable_research'
```

```json
{"data": {"ref": "APP-0024", "name": "Specimen Tracker", "checked_on": "2026-11-27",
          "stage": "active", "decision": "modernize", "approved": true,
          "asked_data_class": "identifiable_research", "allowed": true,
          "data_classes": ["identifiable_research", "personal"], "flags": [],
          "reasons": [
            {"check": "stage", "ok": true, "text": "Its lifecycle stage is Active"},
            {"check": "decision", "ok": true, "text": "The decision on record is to modernize it"},
            {"check": "support", "ok": true, "text": "Nothing it is known to run on is past its end of support"},
            {"check": "data_class", "ok": true, "text": "Its record says it handles identifiable research data"}]}}
```

`approved` is true when the application is in service and open to new use (phase in or active), its decision on record does not take it away (retire, replace, or consolidate), and nothing it is known to run on is past its end of support. With `data_class`, `allowed` is true only when the application is `approved` and its record says it handles that class; it is `null` when what data the application handles is not shown to the asker. Every reason is given, so the process asking can weigh them itself. A restricted application the asker may not see is answered 404, as if there were none.

## Be told when something happens

An administrator registers **webhooks** under **Admin → Webhooks**: an `https://` address on the public internet, and what it is to be told of.

| Topic | Sent when |
|---|---|
| `decision.recorded` | A decision is recorded for an application |
| `application.stage_changed` | An application moves to another lifecycle stage |
| `confirmation.lapsed` | An application's record goes past the date it was to be confirmed by |
| `assessment.lapsed` | An application's assessment goes past the date it was due again |

Each message is a small JSON document that says what changed, never what a record holds; ask the API for more. A restricted application's `name` is sent as `null`.

```json
{"topic": "decision.recorded", "event": 4127, "at": "2026-11-27T10:15:02Z",
 "data": {"ref": "APP-0024", "name": "Specimen Tracker", "tier": "2", "decision": "DEC-0031",
          "disposition": "modernize", "recommendation": "modernize",
          "decided_on": "2026-11-27", "review_on": "2027-11-27"}}
```

The message about a lapse comes from a reminder, not from the history, so its `event` is `null`, and its `data` holds the application's `ref`, `name`, and `tier` and the `due_on` date that passed. **Send test** sends a made-up message with the topic `test`, once and not tried again.

Each request carries these headers:

| Header | Holds |
|---|---|
| `X-AppWren-Topic` | The topic, as in the body |
| `X-AppWren-Delivery` | The delivery's id. A delivery that is tried again keeps its id |
| `X-AppWren-Timestamp` | When this attempt was signed, in seconds since 1970 (Unix time) |
| `X-AppWren-Signature` | `sha256=` and the signature, in hex |

**A message may arrive more than once.** Delivery is at least once: a receiver that took a message but whose answer was lost is sent it again. Keep the delivery ids you have handled, and do nothing for one you have seen.

Every message is signed with the webhook's secret, shown once when it is added. To check one, compute HMAC-SHA256 over the `X-AppWren-Timestamp` header, a dot, and the body exactly as received, and compare it with `X-AppWren-Signature`:

```python
import hashlib, hmac


def genuine(secret: str, headers: dict, body: bytes) -> bool:
    mac = hmac.new(
        secret.encode(), headers["X-AppWren-Timestamp"].encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={mac}", headers["X-AppWren-Signature"])
```

Reject a message whose timestamp is more than a few minutes old. Answer with any 2xx status; anything else, or no answer within ten seconds, is tried again after 2, 4, 8, 16, and 32 minutes. A webhook that fails twenty times in a row is paused until an administrator switches it on again. Redirects are never followed. Before each delivery, the receiver's name is looked up on the machine AppWren runs on, and the message goes only if every address it resolves to is on the public internet; that holds when `HTTPS_PROXY` sends it through a proxy as well.

### Editing a record someone else is editing

Records carry a `version`. Send the version you read with every `PATCH` of a record, and with `PUT /applications/{ref}/use`, and if someone else has changed the record since, the answer is 409 and nothing is saved. Read it again and decide what to do. The OpenAPI document marks `version` as optional, but a change sent without it is always answered 409: no version matches none.

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
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "The decision was not recorded.",
  "errors": [
    {"location": ["rationale"], "message": "Say why. The next person to look at it will want to know."}
  ],
  "instance": "/api/v1/applications/APP-0042/decisions"
}
```

Read `status`, and `errors` where there are any. `title` is the standard phrase for the status, taken from the Python AppWren runs on, and differs between versions (422 is "Unprocessable Entity" before Python 3.13 and "Unprocessable Content" from it), so do not compare it. `detail` is written for a person and may change.

A 422 comes in two shapes. The one above is AppWren's own: a value was read and refused, `detail` says what was not done, and each `location` is the field's name alone. When the request itself does not fit the route, such as a value of the wrong type or a number out of range, `detail` is "The request is not valid." and each `location` starts with where the value was, `body`, `query`, or `path`:

```json
{"type": "about:blank", "title": "Unprocessable Content", "status": 422,
 "detail": "The request is not valid.",
 "errors": [{"location": ["query", "limit"], "message": "Input should be greater than or equal to 1"}],
 "instance": "/api/v1/applications"}
```

| Status | Meaning |
|---|---|
| 400 | The request could not be carried out as asked |
| 401 | Nobody is signed in, the email address and password do not match, or the token is not valid, has expired, or was revoked |
| 403 | You may not do this: your role does not allow it, the CSRF token is missing, the request came from another site (`Sec-Fetch-Site: cross-site`, or an `Origin` that is not this host), the token may only read, or password sign-in is kept for administrators (`[sso] local_sign_in = false`). `detail` says which |
| 404 | No such thing, or none that you may see. The two are not told apart |
| 409 | A conflict: the record changed since you read it, or the thing is already so |
| 413 | The request is larger than 32 MB |
| 422 | A value is missing or not allowed. `errors` names each field |
| 429 | Too many failed sign-ins, or too many wrong current passwords at `POST /session/password`: wait a few minutes. From the assistant: the day's limit of questions is used up, or your last question is still being answered |
| 500 | Something went wrong in AppWren itself. `detail` says only that; the server's log has the rest |
| 503 | The database is busy, with `Retry-After: 5`, so try again in a few seconds; or it is unavailable |

## Lists

The lists of records (`GET /{records}`, and the reviews, initiatives, and requests of [planning change](#planning-change)) take these parameters. Not every list takes every one:

| Parameter | Taken by | Meaning |
|---|---|---|
| `q` | Every list | Words to look for in the name, reference, or summary, or in what the record is called in another system |
| `sort` | Every list | A field name. Start with `-` for descending. The default is `-updated_at` |
| `limit` | Every list | How many to return: 50 by default, 200 at most |
| `cursor` | Every list | Where to continue from: `next_cursor` or `prev_cursor` from the last answer |
| `unit` | Applications, components, reviews, initiatives, requests | A unit's id. Includes every unit beneath it |
| `owner` | Applications | An account's id: only the records that person is named on |
| `mine` | Applications | `true` for only the records you are named on |
| `technology`, `release`, `version` | Applications, components | Those built on a technology's reference; with `release`, one of its releases by cycle (`none` for those that name none); with `version`, an exact version or its start. An application counts when any of its components does |

**A parameter a route does not take is ignored, not refused.** `GET /vendors?unit=4` lists every vendor, and so does a misspelled parameter on any route, so check a filter against the OpenAPI document, which lists each route's parameters.

Each kind of record adds its own filters, such as `lifecycle`, `sourcing`, `tier`, `domain`, `data_class`, and `capability` for applications; `application` and `data_class` for interfaces; `platform_id` and `environment` for deployments; and `ending_within` (days) for contracts. The OpenAPI document lists them.

A list's `meta` says where the page sits:

```json
{"total": 109, "offset": 0, "next_cursor": "eyJvZmZzZXQiOjUwfQ", "prev_cursor": null}
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
| `PUT /applications/{ref}/use` | Who uses it, in one change: `org_wide`, or the `units` where everyone uses it and the `audiences` (kinds of people) who use it wherever they work; `users`, about how many; `external_users`. Naming everyone clears the units and kinds. Send the `version` you read |
| `PUT /applications/{ref}/units` | The units that use it, alone |
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
| `GET` · `POST /applications/{ref}/decisions` | Its decisions; record a new one (a manager, or a leader of its unit, who is not its accountable owner, unless the program lets owners decide: see `PUT /program/decision-rules`) |
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
| `GET` · `POST /tokens` · `DELETE /tokens/{id}` | Your own tokens; make one with a `name` and `expires_on`, its `token` in the answer this once; revoke one |
| `GET` · `POST /applications/{ref}/suggestions` | The changes proposed to an application, pending and recently decided; propose a `value` for one `field`, with a `note` |
| `POST /suggestions/{id}/accept` · `POST /suggestions/{id}/dismiss` | Accept a proposal, making the change as yours, or dismiss it. Someone who keeps the application, signed in |
| `POST /assistant/ask` · `POST /assistant/draft` · `GET /assistant/exchanges` | Where an assistant is set up: an `answer` to a `question` with the `records` it cites; `values` drafted from a document's `text`, and what was `dropped`; every exchange (for those who see everything). 404 when there is no assistant |
| `GET /checkpoint/{ref}` | Whether an application is approved for new use, and for a `data_class` if given, with every reason. See [Ask whether an application is approved](#ask-whether-an-application-is-approved) |
| `GET` · `POST /admin/tokens` · `DELETE /admin/tokens/{id}` | API tokens and when each was last used; issue one with a `name`, `role`, `org_unit_id`, `read_only`, and `expires_on`, its `token` in the answer this once; revoke one (admin) |
| `GET` · `POST /admin/webhooks` · `PATCH` · `DELETE /admin/webhooks/{id}` · `POST /admin/webhooks/{id}/test` | Webhooks and their recent deliveries; add one with a `name`, `url`, and `topics`, its `secret` in the answer this once; change, switch off, or remove one; send a test now (admin) |

## What the API will not do

- It never returns a record you may not see, and never counts one.
- It never returns a sensitive field, a cost line, or a contract you may not see, and refuses to filter or sort by a sensitive field, or to take a value for one.
- It never gives a total of cost that includes a part you may not see.
- It never reaches out to anything an administrator has not switched on: until a connector is on, support dates arrive only in a file someone sends. A connector only reads. A webhook is sent only to an address an administrator registered, on the public internet.
- It never takes a token as an administrator. Tokens are for other systems, with a role.
- It never takes away within 0.x what a release offered: every route of the last release is still there, and no request asks for more than it did. A test holds it to the last release's OpenAPI document.
- It never edits an assessment or a decision. Each is superseded by a new one.
- It never lets a person record a decision about an application they are accountable for, unless the program lets owners decide (`owners_may_decide` under `PUT /program/decision-rules`), and then the decision says so.
- It never takes a score. Scores are worked out from the record and the answers; a contest says one is wrong, and moves nothing.
- It never changes the history. There is no route that does.
