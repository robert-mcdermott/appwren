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

`init` does six things:

1. Writes `appwren.toml`, the deployment settings, in the current directory.
2. Creates the data home, `./var`, which holds everything that is not in the database.
3. Creates the database. With no other setting, this is a SQLite file inside the data home.
4. Asks for your organization's name, and a first unit within it if you wish, such as your team. Every application belongs to a unit, so this is the least you need to add one. Press Enter to skip it and add units later.
5. Loads the default program: the vocabularies (lifecycle stages, sourcing, tiers, data classes, interface methods, environments, cost categories, and the rest), what each lifecycle stage requires of a record, which fields are sensitive, a starter capability map of 43 capabilities, a question bank of nine questions, and the scoring model with its three profiles, rules, guardrails, and flags.
6. Asks for your email address, your name, and a password, and creates the first administrator.

The password needs at least 12 characters. Length matters more than symbols: a few unrelated words make a good one.

`init` is safe to run again. It leaves an existing configuration file alone, adds only what is missing from the program, creates units only if there are none, and creates an administrator only if there is none.

To set up without being asked anything, name the administrator and pipe the password in:

```bash
printf '%s' "$ADMIN_PASSWORD" | uv run appwren init \
  --organization "Your Organization" --first-unit "Your Team" \
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
| **Architect** | Keeps the records the whole organization shares (capabilities, technologies, vendors, hosting platforms, and funding sources) and assesses applications. Can be limited to a unit |
| **Leader** | Leads a unit. Sees it and everything beneath it, and records decisions for its applications |
| **Steward** | Keeps a unit's applications complete and current: adds, edits, imports, and assesses them |
| **Auditor** | Reads everything, including the full history, and changes nothing |
| **Admin** | Accounts, units, sign-in, appearance, and system settings |

[Running the program](running-the-program.md#roles-and-scope) says exactly what each role may do.

### Import units and people

Both screens take a CSV file, which is the quick way to load an organization. Each import can be run dry first and reports every problem by row, so nothing is half-loaded. The import dialog shows the columns it expects.

### Appearance

**Admin → Appearance** sets the product's name, your organization's name, a logo, an accent color, and the default palette. See [Running the program](running-the-program.md#appearance).

## Start with one team

AppWren does not need the whole organization to begin. A single team that keeps a few dozen applications can use it for its own, and the rest of the organization can join later without anything being redone.

1. **Make the organization the top unit, and the team a unit within it.** `init` asks for both (or pass `--organization` and `--first-unit`). The organization is only a name until others join. If you began with the team at the top, **Admin → Units → Put a unit above the top** adds the organization above it later, with everything beneath the team moving with it.
2. **Add the departments that use your applications** as units with nobody in them, so that each application can say who uses it, and the dashboard and data quality can be read by department later.
3. **Give the team's lead two roles** under **Admin → People**: *administrator*, and *manager* for the whole organization. A manager limited to a unit cannot take portfolio snapshots or shape the program.
4. **Name the rest of the team** on the applications they keep, or make them stewards of the team's unit to keep all of its applications.
5. **Bring in your applications** from a spreadsheet, as below.
6. **Retire what does not fit** of the starter capability map: open a capability, choose **Edit**, and set its status to retired. Add your own as you need them.

SQLite and the one server process `init` sets up are plenty for a team. Move to [PostgreSQL](configuration.md#use-postgresql) when more of the organization joins.

One rule needs a thought in a small team: **nobody records the decision about an application they are accountable for.** If the lead is both the owner of the team's applications and its only manager, either name another member accountable for the applications the lead will decide on, or turn on **Admin → Program → Decisions**, which lets an owner who is also a manager or leader decide about their own application. Each such decision is marked *Recorded by its own owner*, so anyone reading it later knows.

## Bring in your applications

Most organizations start from a spreadsheet. **Applications → Import** reads a CSV file, matches its columns to AppWren's fields, and runs dry first, reporting every problem by row. A row with a reference already on record updates that application; any other row adds one. See [Import and export](the-portfolio.md#import-and-export).

Then give the stewards of each unit a week to fill the gaps. **Reports → Data quality** shows, unit by unit, what is missing.

## Explore the demo organization

To see AppWren with data in it before you set anything up, build the demo:

```bash
uv run appwren demo                                 # builds ./demo
uv run appwren --config demo/appwren.toml serve     # runs it at http://127.0.0.1:8020
```

The demo is the Bramblewood Institute for Health Research, a fictional research institute with a clinic and two years of history: 57 units, about 180 people, 107 applications (about forty of them research tools kept by labs), about 120 components, 24 technologies, 24 interfaces, 88 deployments on six hosting platforms, 22 contracts, about 140 assessments, 65 decisions, and four quarterly portfolio snapshots. There is an application to modernize with three flags, three survey tools doing one job, a grant about to end, software kept by one person, a pilot, a decision that differs from its recommendation, four applications whose owner left, a dozen never assessed, a database release reaching end of support next quarter, research data flowing into dashboards whose record does not list it, a contract whose notice date is two weeks off, health data with no data agreement, and five thousand licenses of which fourteen hundred are used. And keeping it current: a score of records nobody has confirmed in time, a campaign under way in the shared resources and one closed in the clinic, tasks for a notice date, a release ending, grants ending, and the four applications left without an owner, and a score contested and answered. And planning change: two quarterly reviews closed with what they decided and the next one planned, ten initiatives on the roadmap, five requests for something new from approved to just in, and three retirements, one done with its savings and one past its date. Nothing in it is real, and every record was made by the same code the app uses, so its history verifies like any other.

![Home for the demo's portfolio manager: what is waiting on them, most urgent first, beside their roles](img/home-manager-light.webp)

Its sign-in page offers eight sample people and asks for no password:

| Sign in as | To see |
|---|---|
| The portfolio manager | The dashboard with what everything costs, the portfolio chart, mismatches to review, contracts and their notice dates, overlap, snapshots, campaigns and tasks, and the program to shape |
| The enterprise architect | The capability map and its measures, data flows, the lifecycle timeline and radar, hosting platforms, the picture of how anything is connected, and a contest waiting for an answer |
| The chief information officer | Decisions for Information Technology's applications, and the reviews coming due |
| The clinical research leader | A decision that keeps an application the scores would replace, and why |
| The research applications steward | Specimen Tracker: its scores and their working, what would break if it went, where it runs, and what it costs line by line; and what a campaign asks of them |
| The research software engineer | A member's view: the applications they keep, and the costs and contracts they may not see elsewhere |
| The auditor | Everything, read-only, with every change in one place under Reports, History |
| The administrator | People, units, sign-in, appearance, and scheduled work, and no part in the portfolio's judgments |

`appwren demo --seed 2` builds a different Bramblewood with the same shape, and `--force` rebuilds one that is already there.

A demo listens only on the machine it runs on. See [Configuration](configuration.md#the-demo-and-the-network) before changing that.

## Next

- To record applications, assess them, read their scores, and record what they cost, read [The portfolio](the-portfolio.md).
- To record what passes between them, where they run, and what falls out of support, read [The landscape](the-landscape.md).
- To keep the record current, with reminders, confirmations, campaigns, and tasks, read [Keeping current](keeping-current.md).
- To decide who sees what, and to shape the questions and the scoring model, read [Running the program](running-the-program.md).
