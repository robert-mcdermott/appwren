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
| [`appwren users`](#appwren-users) | Manage accounts from the command line |
| [`appwren verify`](#appwren-verify) | Check that the history has not been altered |
| [`appwren doctor`](#appwren-doctor) | Check that this installation is healthy |

## `appwren init`

Write a configuration file if there is none, create the data home, create or upgrade the database, and create the first administrator if there is none. Safe to run again.

| Option | Meaning |
|---|---|
| `--force` | overwrite an existing configuration file |
| `--admin-email` `EMAIL` | create the first administrator with this address |
| `--admin-name` `NAME` | the first administrator's name |
| `--password-stdin` | read the password from standard input instead of asking |

## `appwren serve`

Run AppWren's web server. It refuses to start on a database whose schema is behind; run `appwren db upgrade` first.

| Option | Meaning |
|---|---|
| `--host` | address to listen on (default: from the configuration) |
| `--port` `PORT` | port to listen on (default: from the configuration) |
| `--workers` `WORKERS` | server processes (default: from the configuration) |
| `--reload` | restart when the code changes (development) |

## `appwren db`

Look after the database schema.

### `appwren db upgrade`

Apply any migrations the database has not had. Export first: an upgrade cannot be undone except by restoring.

### `appwren db current`

Show which migration the database is at, and which this version expects. Exits with 1 when they differ.

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

## `appwren doctor`

Check the configuration, the data home, the database and its schema, and the history. Exits with 1 if anything must be fixed.
