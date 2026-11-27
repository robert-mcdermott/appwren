# Getting started

This guide takes you from nothing to a running AppWren that your organization can sign in to. It is for whoever installs it and sets it up. Allow about fifteen minutes.

If you only want to look around first, skip to [Explore the demo organization](#explore-the-demo-organization).

## What you need

- [uv](https://docs.astral.sh/uv/), which provides the right Python (3.12 or later).
- A copy of this repository.

Every command in these guides is run through `uv run appwren …` from the repository directory. The full list is in the [command reference](cli.md).

## Install

```bash
uv sync
```

## Set up the installation

```bash
uv run appwren init
```

`init` does five things:

1. Writes `appwren.toml`, the deployment settings, in the current directory.
2. Creates the data home, `./var`, which holds everything that is not in the database.
3. Creates the database. With no other setting, this is a SQLite file inside the data home.
4. Loads the default program: the vocabularies (lifecycle stages, sourcing, tiers, data classes, and the rest), what each lifecycle stage requires of a record, which fields are sensitive, a starter capability map of 43 capabilities, a question bank of nine questions, and the scoring model with its three profiles, rules, guardrails, and flags.
5. Asks for your email address, your name, and a password, and creates the first administrator.

The password needs at least 12 characters. Length matters more than symbols: a few unrelated words make a good one.

`init` is safe to run again. It leaves an existing configuration file alone, adds only what is missing from the program, and creates an administrator only if there is none.

To set up without being asked anything, name the administrator and pipe the password in:

```bash
printf '%s' "$ADMIN_PASSWORD" | uv run appwren init \
  --admin-email you@example.org --admin-name "Your Name" --password-stdin
```

## Check it

```bash
uv run appwren doctor
```

`doctor` checks the configuration, the data home, that the database answers, that its schema is the one this version expects, that the database still refuses changes to the history, and that the history verifies. It exits with 1 if anything must be fixed.

## Run it

```bash
uv run appwren serve
```

The server prints its address, by default `http://127.0.0.1:8000`. Use `--port` to pick another port.

`serve` refuses to start in three cases, and says what to do in each:

| It says | Do this |
|---|---|
| The database schema is behind | `uv run appwren db upgrade` |
| There is no administrator yet | `uv run appwren users add you@example.org --name "Your Name" --role admin` |
| The port is already in use | Stop what is using it, or pass `--port` |

As installed, AppWren listens only on the machine it runs on. To put it in front of other people, read [Configuration](configuration.md) first.

## Sign in for the first time

Open the address in a browser and sign in with the email address and password you gave `init`.

AppWren signs in with local accounts: an email address and a password that it keeps. Nothing else has to be installed or connected. Signing in with your organization's identity provider, such as Microsoft Entra ID, is optional and can be added at any time: see [Single sign-on](configuration.md#single-sign-on).

- Five failed attempts within fifteen minutes stop sign-in for that account from that address for a few minutes.
- A sign-in ends after 12 hours without activity, and after 7 days in any case. Both are [settings](configuration.md#server).
- To change your password, open the account menu at the top right and choose **Your account**. Changing it signs out your other sessions.
- If you cannot sign in at all, reset the password from the command line: `uv run appwren users reset-password you@example.org`.

## Set up the organization

The administrator account sets the installation up. It does not keep applications or record decisions: that belongs to the roles below, and an administrator who also does that work is given a second role.

### Units

**Admin → Units** holds the organization as a hierarchy of any depth: divisions, departments, centers, core facilities, labs, clinics, offices, and teams. Every application belongs to a unit, roles can be limited to a unit and everything beneath it, and figures roll up the tree. Give each unit a short code; imports refer to units by it.

### People and roles

**Admin → People** adds accounts and gives them roles. A person with no role is a member: they can read the catalog, and they keep the applications they are named on.

| Role | What it is for |
|---|---|
| **Manager** | The portfolio team. Edits any application, records decisions, takes snapshots, and shapes the program. Can be limited to a unit |
| **Architect** | Keeps the records the whole organization shares (capabilities, technologies, and vendors) and assesses applications. Can be limited to a unit |
| **Leader** | Leads a unit. Sees it and everything beneath it, and records decisions for its applications |
| **Steward** | Keeps a unit's applications complete and current: adds, edits, imports, and assesses them |
| **Auditor** | Reads everything, including the full history, and changes nothing |
| **Admin** | Accounts, units, sign-in, appearance, and system settings |

[Running the program](running-the-program.md#roles-and-scope) says exactly what each role may do.

### Import units and people

Both screens take a CSV file, which is the quick way to load an organization. Each import can be run dry first and reports every problem by row, so nothing is half-loaded. The import dialog shows the columns it expects.

### Appearance

**Admin → Appearance** sets the product's name, your organization's name, a logo, an accent color, and the default palette. See [Running the program](running-the-program.md#appearance).

## Bring in your applications

Most organizations start from a spreadsheet. **Applications → Import** reads a CSV file, matches its columns to AppWren's fields, and runs dry first, reporting every problem by row. A row with a reference already on record updates that application; any other row adds one. See [Import and export](the-portfolio.md#import-and-export).

Then give the stewards of each unit a week to fill the gaps. **Reports → Data quality** shows, unit by unit, what is missing.

## Explore the demo organization

To see AppWren with data in it before you set anything up, build the demo:

```bash
uv run appwren demo                                 # builds ./demo
uv run appwren --config demo/appwren.toml serve     # runs it at http://127.0.0.1:8020
```

The demo is the Bramblewood Institute for Health Research, a fictional research institute with a clinic and two years of history: 57 units, about 180 people, 107 applications (about forty of them research tools kept by labs), about 120 components, 24 technologies, about 125 assessments, 70 decisions, and four quarterly portfolio snapshots. There is an application to modernize with three flags, three survey tools doing one job, a grant about to end, software kept by one person, a pilot, a decision that differs from its recommendation, four applications whose owner left, a dozen never assessed, and a database release reaching end of support next quarter. Nothing in it is real, and every record was made by the same code the app uses, so its history verifies like any other.

![Home for the demo's portfolio manager: what is waiting on them, most urgent first, beside their roles](img/home-manager-light.webp)

Its sign-in page offers eight sample people and asks for no password:

| Sign in as | To see |
|---|---|
| The portfolio manager | The dashboard, the portfolio chart, mismatches to review, and snapshots |
| The enterprise architect | The capability map, technologies and their support dates, and vendors |
| The chief information officer | Decisions for Information Technology's applications, and the reviews coming due |
| The clinical research leader | A decision that keeps an application the scores would replace, and why |
| The research applications steward | Specimen Tracker, its scores and their working, and the gaps in a unit's records |
| The research software engineer | A member's view: the applications they keep, and costs they may not see elsewhere |
| The auditor | Everything, read-only, with the full history |
| The administrator | People, units, sign-in, and appearance, and no part in the portfolio's judgments |

`appwren demo --seed 2` builds a different Bramblewood with the same shape, and `--force` rebuilds one that is already there.

A demo listens only on the machine it runs on. See [Configuration](configuration.md#the-demo-and-the-network) before changing that.

## Next

- To record applications, assess them, and read their scores, read [The portfolio](the-portfolio.md).
- To decide who sees what, and to shape the questions and the scoring model, read [Running the program](running-the-program.md).
