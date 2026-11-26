# Data model

AppWren keeps everything in one relational database, SQLite by default and PostgreSQL in production, behind one SQLAlchemy model and one Alembic migration history. Files (attachments, logos) live on disk in the data home, addressed by their hash; the database holds their metadata.

This document describes the entities, how they relate, and the rules that apply to all of them. Column-level detail lives in the models and migrations; when they change, this document changes in the same commit. Entities are marked with the wave that introduces them; those of later waves are sketched and will be detailed when their wave is planned.

## Conventions

- **Two identifiers per record.** Every row has an integer primary key used for joins. Every record a person might cite also has a **reference**: a short, permanent, human-readable key with a type prefix and a sequence number (`APP-0142`). References never change and are never reused. They are what a review paper, a budget request, or an email cites.
- **Timestamps** are UTC, stored as timezone-aware values, shown in the viewer's time zone. Dates that are only dates (a go-live date, a grant end) are stored as dates.
- **Vocabularies are data.** Any field described below as "a vocabulary" (sourcing, purpose, lifecycle stage, data class, component kind, and so on) draws its values from a settings-backed list the organization can rename, extend, and retire. Rows keep the stable key of the value, never its label, so renaming a value never rewrites history.
- **JSON columns** hold structured values whose shape is defined by configuration (assessment answers, an application's own fields, a score snapshot's working). They are stored through SQLAlchemy's portable JSON type and never queried with database-specific operators; anything that needs filtering or sorting is a real column.
- **Soft deletion only.** Records are retired or archived, never deleted, so references and history stay valid.
- **Judgments are never edited.** Assessments, decisions, and attestations are statements by a person at a time. A correction is a new row that supersedes the old one.
- **Every write is an event.** No table is written except through the service layer, which records an event in the same transaction (see [History](#history)).
- **Optimistic concurrency.** Editable records carry a version number; a change made against an older version is refused.

| Prefix | Record | Wave | Prefix | Record | Wave |
|---|---|---|---|---|---|
| `APP` | Application | 1 | `DEP` | Deployment | 2 |
| `CMP` | Component | 1 | `INT` | Interface | 2 |
| `VEN` | Vendor | 1 | `CON` | Contract | 2 |
| `TEC` | Technology | 1 | `CMG` | Campaign | 3 |
| `CAP` | Capability | 1 | `SRC` | Connector source | 4 |
| `ASM` | Assessment | 1 | `INI` | Initiative | 5 |
| `DEC` | Decision | 1 | `REQ` | Request (intake) | 5 |
| `PSN` | Portfolio snapshot | 1 | `SCN` | Scenario | 6 |

## Overview

```text
                              ┌────────────┐
                              │  Org unit  │◀── parent
                              └─────┬──────┘
                  belongs to · used by  │   stewards, leaders
                                    ▼
 ┌────────────┐  supports  ┌──────────────────┐  depends on   ┌──────────────────┐
 │ Capability │◀───────────│   Application    │──────────────▶│   Application    │
 └─────┬──────┘  primary?  └──┬────┬────┬─────┘               └──────────────────┘
   parent ▲                   │    │    │ supplied by   ┌────────┐
                   people in  │    │    └──────────────▶│ Vendor │
                   roles      ▼    │                    └────────┘
                  ┌─────────────┐  │ built from   ┌───────────┐  uses   ┌────────────┐  releases
                  │   Account   │  └─────────────▶│ Component │────────▶│ Technology │──▶ support dates
                  └─────────────┘                 └───────────┘ version └────────────┘
   assessment (answers) ─▶ score snapshot ─▶ decision (disposition, rationale)
```

## Organization and people (wave 1)

### Org unit

The organization as a tree: `org_unit(id, parent_id, kind, name, code, status)`. `kind` is a vocabulary (by default: organization, division, department, center, core facility, lab, clinic, office, team). There is one root. A unit may be closed, which keeps its records and history but removes it from pickers.

Units are the backbone of scoping. Every application belongs to exactly one unit (the unit that answers for it), any number of units may be recorded as using it, and a role can be granted for a unit, which then covers every unit beneath it. Teams are units too, so a support team or a product team is a unit with its own members.

### Account

`account(id, email, display_name, title, status, time_zone)` is a person who can sign in or be named on a record. An account can exist before its person has ever signed in (created by an import or by being named as an owner), in which case it is *invited*.

- `credential` holds a local password hash for accounts that have one.
- `membership(account_id, org_unit_id, title, is_primary)` records which units a person works in. It drives defaults and what a member can see; it grants nothing else.
- `session_token` and `failed_sign_in` support sign-in and are not history.
- `identity(account_id, issuer, subject)` links an account to a single sign-on identity, and `provider_mapping` says which of the provider's groups or application roles gives which role here.

### Roles

`role_grant(account_id, role, org_unit_id?, source)`.

| Role | What it allows |
|---|---|
| `admin` | Accounts, sign-in settings, branding, and system configuration. Not, by itself, the right to edit applications or decide anything |
| `manager` | Run the portfolio: edit any record, record decisions, take snapshots, and manage the program (vocabularies, fields, questions, scoring profiles, rules) |
| `architect` | Keep the shared records: capabilities, technologies, and vendors; link any application to them; assess any application in scope. Reads everything in scope, including sensitive fields |
| `leader` | Read everything in their unit and beneath it, including sensitive fields; record decisions for applications in their units |
| `steward` | Keep their unit's records current: add and edit applications, assign people to roles, import, and answer for the unit's completeness |
| `auditor` | Read everything, including sensitive fields and the full history; change nothing |
| `member` | Read the catalog, see and do what is assigned to them, and keep the applications they are named on |

`manager`, `architect`, `leader`, and `steward` grants may be limited to a unit, which covers everything beneath it; without a unit they cover the organization. Being named on an application is not a role: it is a relationship on the record, and it carries the right to edit that record and the duty to keep it current. See [security.md](security.md).

## The inventory (wave 1)

Inventory record types share a header: `ref`, `name`, `summary`, `status`, `tags`, `restricted`, `version`, and timestamps. What differs between record types is described once, in a registry, so that adding, editing, listing, links, visibility, and history are written once for all of them.

### Application

The unit of the portfolio ([ADR-0013](decisions/0013-applications-components-deployments.md)).

`application(…, aliases, org_unit_id, lifecycle, lifecycle_since, sourcing, purpose, pace, domain, tier, vendor_id?, product, edition, hosting, users, maintainers, annual_cost, sign_in, monitoring, backup, last_restore_test, data_classes, sensitivity, funding, grant_ref, grant_end, research_continuity, regulated_record, records_retention, external_users, go_live, retire_planned, successor_id?, home_url, docs_url, fields)`.

- `lifecycle`, `sourcing`, `purpose`, `pace`, `domain`, `hosting`, `sign_in`, `monitoring`, `backup`, and `funding` are vocabularies; `tier` is the criticality vocabulary (ordered, 1 to 5); the engine reads them as facts ([engine.md](engine.md#facts)).
- `lifecycle_since` is the date the application entered its current stage. A change of stage is an event like any other, so the history holds every stage and its date.
- `data_classes` is a list of data-class keys; `sensitivity` is the highest of their sensitivities, kept as a column so it can be filtered.
- `annual_cost` is an estimate in the organization's currency, and is a **sensitive field** (see [security.md](security.md#sensitive-fields)). From wave 2 it is the sum of the application's cost lines.
- `fields` holds the values of the organization's own fields, defined in the program, keyed by field key.
- `successor_id` names the application that replaces this one.
- `status` is *active* until the lifecycle reaches Retired or Archived.

### People in roles

`application_role(application_id, account_id, role, note)`. `role` is a vocabulary: by default *accountable owner*, *business owner*, *technical owner*, *product manager*, *support contact*, *data steward*, *security contact*, and *executive sponsor*. There is exactly one accountable owner per application once it is past Proposed, enforced in the service and by a partial unique index. A person may hold several roles on one application; a role other than accountable may be held by several people.

The application's support team is a unit: `support_unit_id` on the application.

### Units that use it

`application_unit(application_id, org_unit_id)`: the units that use the application, which may be many and may differ from the unit that answers for it.

### Component

`component(…, application_id, kind, repo_url, hosting, lifecycle)`. A part of one application. `kind` is a vocabulary (service, web front end, database, batch job, integration, report, module, library, mobile app, infrastructure). `lifecycle` is active or retired.

`component_technology(component_id, technology_id, release_id?, version)`: the technologies a component uses, optionally pinned to a release (a version line such as `3.11`) whose support dates apply, and an exact version as text.

### Vendor

`vendor(…, kind, website)`. A company or project that supplies software or services. `kind` is a vocabulary (software vendor, service provider, open-source project, consortium, partner institution). From wave 2, contracts and agreements.

### Technology

`technology(…, kind, vendor_id?, radar, homepage, eol_key)`. A language, framework, runtime, database, operating system, platform, or product that components use. `kind` is a vocabulary. `radar` is the organization's view: Adopt, Trial, Assess, Hold, or unset. `eol_key` names the product in an end-of-life dataset, for import from wave 2.

`technology_release(technology_id, cycle, released_on, support_ends, extended_ends, latest)`: a version line and its support dates. *Past end of support* means `support_ends` is before today, unless `extended_ends` is recorded and still ahead, in which case the working says so.

### Capability

`capability(…, parent_id, domain, position)`. What the organization does, independent of how or with which system ("Biospecimen tracking", "Grant management"). A tree of any depth.

`application_capability(application_id, capability_id, is_primary, note)`: what an application does for the organization. At most one active application is the primary provider of a capability.

### Links

`record_link(from_type, from_id, relation, to_type, to_id, note)`. `relation` is a vocabulary of named relationships, each with a forward and a reverse label and the pairs of record types it may join. A link's changes appear in the history of the record it starts from.

| Kind (default) | From → to | Reads as |
|---|---|---|
| `depends_on` | Application → Application | depends on / is depended on by |
| `part_of` | Application → Application | is part of / includes |
| `replaces` | Application → Application | replaces / is replaced by |
| `depends_on` | Component → Component | depends on / is depended on by |

From wave 2, *interfaces* are records of their own, with direction, method, frequency, and the data classes they carry; a `depends_on` link is the lightweight version.

### Tags and external references

Free labels on any record, for whatever the vocabularies do not cover. `external_ref(record_type, record_id, system, value)` records what a record is called in another system (a configuration item, a ticket queue, a repository), with a URL pattern per system.

## Assessment and scoring (wave 1)

### Questionnaire

`questionnaire(id, version, status, definition, published_at, published_by)`. `definition` is the question bank: sections, questions with keys, the dimension each serves, help text, and a definition for every level. One version is *current*; earlier versions remain because assessments refer to them.

### Scoring model

`scoring_model(id, version, status, definition, published_at, published_by)`. `definition` holds the profiles with their factors, weights, bands, floors, and thresholds; the recommendation rules, guardrails, and flag rules; and the cadence table for how long answers stay current. One version is current; a version once used by a snapshot is never changed.

### Assessment

`assessment(ref, application_id, questionnaire_id, answers, note, assessed_by, assessed_by_name, assessed_on, superseded_by)`. `answers` maps question keys to a level (1 to 5) or *don't know*, each with an optional note. The latest assessment of an application supersedes the one before; neither is ever edited. The assessor's name is kept as it was.

### Score snapshot

`score_snapshot(id, application_id, portfolio_snapshot_id?, taken_at, reason, model_id, profile_key, bv, th, cb, re, confidence, recommendation, flags, working)`.

- `reason`: decision, portfolio, or manual.
- `bv`, `th`, `cb`, `re` (one decimal, or null when no factor was known), `confidence`, `recommendation`, and `flags` are columns so they can be filtered and charted.
- `working` is the whole explanation: every factor with its level, weight, value, source, and date; coverage; the rule that fired; and the guardrails and flags. It reopens unchanged after the program changes.

Scores between snapshots are computed when they are read, and are never stored except as snapshots.

`portfolio_snapshot(ref, name, taken_at, taken_by, model_id, count)`: a named snapshot of every scored application at once, for a review or the end of a period.

### Decision

`decision(ref, application_id, disposition, rationale, target_on, review_on, successor_id?, snapshot_id, recommendation, decided_by, decided_by_name, decided_on, superseded_by)`. `disposition` is a vocabulary (see [engine.md](engine.md#dispositions)). `snapshot_id` is the score snapshot taken at the moment of the decision, and `recommendation` its recommendation, so a mismatch at the time is on the record. Never edited; a new decision supersedes the last. The application keeps a copy of its current disposition and review date for lists and filters.

## Later waves (sketch)

| Wave | Entities |
|---|---|
| 2 | `deployment`, `hosting_platform`, `interface`, `interface_data_class`, `cost_line`, `contract`, `contract_application`, `funding_source` |
| 3 | `job`, `campaign`, `campaign_item`, `attestation`, `mail_outbox`, `saved_view`, `search_doc`, `notice`, `trigger_rule` |
| 4 | `connector`, `connector_run`, `fact_value` (a value with its source and time, and overrides), `maturity_check`, `maturity_result` |
| 5 | `review_cycle`, `review_item`, `initiative`, `initiative_application`, `retirement_plan`, `retirement_step`, `request`, `request_option` |
| 6 | `measure_snapshot`, `report`, `scenario`, `scenario_change` |
| 7 | `api_token`, `webhook`, `webhook_delivery` |

## Program settings

`setting(key, value, version, updated_by, updated_at)` holds everything the program team configures that is not a table of its own: vocabularies, the organization's own fields, cadences, visibility, and branding. Each change is an event. The whole program (settings, the questionnaire, the scoring model, the starter capability map) exports and imports as a **program pack** ([content-packs.md](content-packs.md)).

## History

`event(seq, at, actor_id, actor_label, action, subject_type, subject_id, subject_ref, changes, context, prev_hash, hash)`.

- Written by the session, not by hand: after each flush, every new, changed, and deleted row of an audited model becomes an event in the same transaction, with each changed field's value before and after.
- `action` names the operation in the service's own words (`application.update`, `decision.record`), so a history reads as what people did, not as row changes.
- `context` ties together the events of one operation and records what the change was part of.
- Append-only: the application never updates or deletes an event, and triggers on both databases refuse it. Each event's hash covers its content and the previous hash; `event_head` holds the tip under a lock so numbering has no gaps.
- A record as of a date is rebuilt by replaying its events (wave 6).

## Reference counters

`ref_counter(prefix, next)` hands out numbers per prefix under a lock. A number is never reused, even if the row that took it is rolled back.
