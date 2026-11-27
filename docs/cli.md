# Command reference

Every `appwren` command. This page is written from the program itself, so it always matches
the version it ships with. Run commands with `uv run appwren …` from the project directory.

Options that come before the command apply to all of them:

```text
appwren [-h] [--version] [-c FILE] [-v | -q] COMMAND ...
```

## Commands

| Command | What it does |
|---|---|
| [`appwren init`](#appwren-init) | Set up a new installation |
| [`appwren serve`](#appwren-serve) | Run the web server |
| [`appwren db`](#appwren-db) | Look after the database schema |
| [`appwren backup`](#appwren-backup) | Write the whole installation to one file |
| [`appwren restore`](#appwren-restore) | Load a backup into an empty installation |
| [`appwren users`](#appwren-users) | Manage accounts from the command line |
| [`appwren verify`](#appwren-verify) | Check that the history has not been altered |
| [`appwren demo`](#appwren-demo) | Build a fictional organization to explore |
| [`appwren program`](#appwren-program) | Move the program between installations |
| [`appwren technologies`](#appwren-technologies) | Bring technology support dates in from a file |
| [`appwren jobs`](#appwren-jobs) | See scheduled work, or run it now |
| [`appwren mail`](#appwren-mail) | Send waiting email, or test the mail settings |
| [`appwren doctor`](#appwren-doctor) | Check that this installation is healthy |

## `appwren init`

Write a configuration file if there is none, create the data home, create or upgrade the database, create the organization's top unit if there are no units, and create the first administrator if there is none. Safe to run again.

| Option | Meaning |
|---|---|
| `--force` | overwrite an existing configuration file |
| `--admin-email` `EMAIL` | create the first administrator with this address |
| `--admin-name` `NAME` | the first administrator's name |
| `--program` `STARTER` | begin from a starter program, such as starter-university (see: appwren program starters) |
| `--organization` `NAME` | the organization's name, as its top unit, if there are no units yet |
| `--first-unit` `NAME` | a first unit within the organization, such as the team starting with AppWren |
| `--password-stdin` | read the password from standard input instead of asking |

## `appwren serve`

Run AppWren's web server. It refuses to start on a database whose schema is behind; run `appwren db upgrade` first.

| Option | Meaning |
|---|---|
| `--host` | address to listen on (default: from the configuration) |
| `--port` `PORT` | port to listen on (default: from the configuration) |
| `--workers` `WORKERS` | server processes (default: from the configuration) |
| `--reload` | restart when the code changes (development) |
| `--demo-on-network` | let a demo organization listen beyond this machine (anyone who reaches it can sign in as its sample people) |

## `appwren db`

Look after the database schema.

### `appwren db upgrade`

Apply any migrations the database has not had. Export first: an upgrade cannot be undone except by restoring.

### `appwren db current`

Show which migration the database is at, and which this version expects. Exits with 1 when they differ.

### `appwren db move`

Copy every table into another database that has not been set up, such as from SQLite to PostgreSQL or back, by way of a backup. The history is verified in the new database. The old one is left as it was.

| Option | Meaning |
|---|---|
| `--to` `URL` | the new database's address |
| `--to-env` `NAME` | the name of an environment variable holding the address, to keep a password off the command line |

## `appwren backup`

Write every table, every attachment and brand file, and a manifest to one gzipped tar. It can be made while the server is running. The file does not depend on the kind of database, so it restores into SQLite or PostgreSQL. It holds everything in the installation: keep it as carefully as the database itself.

| Option | Meaning |
|---|---|
| `--out` `FILE` | where to write it (default: appwren-backup-DATE.tar.gz) |

## `appwren restore`

Load a backup into the configured database and data home. The database must hold no accounts and no history: nothing is ever overwritten. The history is verified once it is loaded.

| Option | Meaning |
|---|---|
| `FILE` | the backup, a .tar.gz written by appwren backup |

## `appwren users`

Manage accounts from the command line: for setting up, and for getting back in when nobody can sign in. Everyday account management is in the app, under Admin. Changes made here are recorded in the history as made at the command line.

### `appwren users add`

Add an account. It asks for a password unless --password-stdin or --invite is given.

| Option | Meaning |
|---|---|
| `EMAIL` | the email address the person signs in with |
| `--name` | the person's name |
| `--title` | their job title |
| `--role` `ROLE` | a role: admin, manager, architect, auditor, steward=unit:CODE, or leader=unit:CODE; manager and architect may also take unit:CODE (may be repeated) |
| `--unit` `CODE` | a unit they work in, by code (may be repeated) |
| `--password-stdin` | read the password from standard input instead of asking |
| `--invite` | add them without a password: they can be named on records now, and sign in once they are given a password or use single sign-on |

### `appwren users list`

List every account with its status and roles.

### `appwren users disable`

Stop an account signing in and end its sessions. Its records and history are kept. The last active administrator cannot be disabled.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |

### `appwren users enable`

Let a disabled account sign in again.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |

### `appwren users reset-password`

Give an account a new password and end its sessions.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |
| `--password-stdin` | read the password from standard input instead of asking |

### `appwren users roles`

Show an account's roles, or with --set replace the roles granted in AppWren. Roles mapped from an identity provider are left alone. The last active administrator cannot lose that role.

| Option | Meaning |
|---|---|
| `EMAIL` | the account's email address |
| `--set` `ROLE` | a role: admin, manager, architect, auditor, steward=unit:CODE, or leader=unit:CODE; manager and architect may also take unit:CODE (may be repeated); with none, removes every role |

## `appwren verify`

Recompute the hash chain over every event in the history and report the first one that does not hold. Exits with 1 if the history is broken.

## `appwren demo`

Build the Bramblewood Institute for Health Research, a fictional organization with two years of history, in its own directory. Everything in it is made by the same code the app uses. Start it with the command it prints.

| Option | Meaning |
|---|---|
| `PATH` | where to build it (default: ./demo) |
| `--seed` `SEED` | a different number gives a different Bramblewood |
| `--port` `PORT` | the port its server will use (default: 8020) |
| `--force` | rebuild a demo that is already there |

## `appwren program`

The program is everything a portfolio team configures: vocabularies, the organization's own fields, what each lifecycle stage requires, sensitive fields, the capability map, the questions, and the scoring model. It lives in the database and moves as one file.

### `appwren program export`

Write the whole program as one JSON document, to a file or to standard output.

| Option | Meaning |
|---|---|
| `--output`, `-o` `FILE` | write to this file |

### `appwren program import`

Load a program pack. The whole pack is checked first, and nothing is loaded unless all of it can be. A vocabulary value in use is retired rather than removed, and capabilities are only ever added.

| Option | Meaning |
|---|---|
| `FILE` | the pack to load, or the key of a starter program |
| `--dry-run` | say what would change, and change nothing |

### `appwren program starters`

List the starter programs: the default program as a research institute, an academic medical center, a university, a nonprofit, or a company would first change it. Begin a new installation from one with init --program, or load one over a program with program import.

## `appwren technologies`

Technologies and their releases are kept in the app. Their support dates can also be brought in from a file, so that nobody types them. AppWren does not fetch the file: you bring it.

### `appwren technologies import-eol`

Read a JSON file of end-of-life data: one object whose keys are products and whose values are lists of releases, each with a cycle and any of releaseDate, eol, extendedSupport, and latest. A product is matched to the technology whose end-of-life key it is. Releases are added and dates updated; nothing is removed.

| Option | Meaning |
|---|---|
| `FILE` | the file to read |
| `--dry-run` | say what would change, and change nothing |

## `appwren jobs`

Scheduled work sends reminders, and sends email where that is set up. The server does this by itself while it runs. These commands are for seeing how it is going, and for running it from a scheduled task where the server's own scheduler is turned off.

### `appwren jobs run`

Run every job that is due. With a job's name, run that one now whether or not it is due. A job another process is running is left to it.

| Option | Meaning |
|---|---|
| `JOB` | one job to run now |

## `appwren mail`

Email is optional. Where it is set up, the server sends it by itself while it runs. These commands are for testing the settings and for sending by hand.

### `appwren mail run`

Queue notices and daily summaries, and send what is waiting. Exits with 1 if a message could not be sent.

### `appwren mail test`

Send one message now to the account with this address, and say whether the mail server accepted it.

| Option | Meaning |
|---|---|
| `EMAIL` | the account to send it to |

## `appwren doctor`

Check the configuration, the data home, the database and its schema, and the history. Exits with 1 if anything must be fixed.

| Option | Meaning |
|---|---|
| `--production` | also check what matters once people depend on it: an https address, the database, administrators, sign-in, email, scheduled work, backups, and who can read the data home; a demo organization fails |
