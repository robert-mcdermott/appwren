# Compatibility

This page says what AppWren keeps the same from one release to the next, so an organization can build on it. That covers the systems that call its API, the scripts that run its commands, its configuration file, and the files it reads and writes. It also says how something is retired when it has to go, and what is not promised at all.

> **A draft until 1.0.0.** This is the promise 1.0 will make, written down in 0.9 so that it can be reviewed before it binds. Until 1.0.0 is released, anything here may still change, and the [changelog](../CHANGELOG.md) says so when it does.

## Version numbers

A version is three numbers, *major.minor.patch*.

- A **patch** release, such as 1.0.1, fixes something and changes nothing this page covers.
- A **minor** release, such as 1.1.0, adds things: routes, fields, settings, commands, and options. Anything written against an earlier 1.x keeps working.
- A **major** release, such as 2.0.0, is the only one that may take away or change what this page covers. Its changelog says what changed and how to move.

Security fixes are the one exception. If keeping something the same would leave installations open to attack, it changes in the release that fixes it, and the changelog says so first.

## What 1.x keeps

| Part | What stays the same |
|---|---|
| **The API**, under `/api/v1` | Every route keeps its path and its methods. A request never has to send something it did not have to send before. An answer may carry more fields, and every field it already carries keeps its name and meaning, so a client should ignore fields it does not know. Errors keep their shape: `application/problem+json`, with `errors` naming each field's problem. A list's cursor is opaque and may change form. The API description, served at `/api/openapi.json` and kept in [openapi.json](openapi.json), is the record. Every release is checked against the one before by a test that fails if a route goes or a request asks for more |
| **Webhooks** | Topics keep their names, payloads keep their fields, and the signature keeps its scheme: HMAC-SHA256 over the `X-AppWren-Timestamp` header, a dot, and the body, sent in `X-AppWren-Signature`. Topics and fields may be added |
| **Tokens and keys** | An API token, a token of one's own, or a push key issued by one release keeps working after an upgrade, until it is revoked or it expires |
| **The configuration file** | Every section and key that 1.0 reads is still read, with the same meaning and default, and so is its environment variable, `APPWREN_<SECTION>_<KEY>`. A key that is replaced keeps working, and `appwren doctor` says what replaced it |
| **The command line** | Every command and option keeps working, and exits 0 when it succeeded and 1 when it did not. What a command prints for a person to read may change, so nothing should parse it |
| **Program packs** | A pack exported by any 1.x imports into any later 1.x. AppWren never changes or removes the key of a value in a list it ships, only its label, and a value an organization retires stays retired |
| **Catalog files and pushes** | A catalog file, or a push from another system, that one 1.x accepts, every later 1.x accepts |
| **Backups** | A backup made by any 1.x restores into the same release or any later 1.x, on either database |
| **The data home** | No upgrade needs files in it moved or renamed by hand |
| **Upgrades** | Any 1.x upgrades to any later 1.x in one step with `appwren db upgrade`, keeping every row and file, and 0.9 upgrades to 1.0 the same way. Migrations only go forward; to go back, restore the backup taken before the upgrade. Every release is checked by upgrading a demo organization built by each release before it, on SQLite and on PostgreSQL |
| **The history** | Every event an earlier release recorded still verifies after an upgrade, and a decision's digest never changes |
| **Links to records** | A record's address, such as `/applications/APP-0042`, keeps working, so links in email, tickets, and documents stay good |
| **Scores** | An upgrade moves no application's scores unless its changelog says the default scoring model changed, and why. A program that has shaped its own model keeps it |

## What is not promised

- **The database's tables.** The schema changes in minor releases, through migrations. Read the portfolio through the API, an export, or a backup, never by querying its tables, and let nothing but AppWren write to them.
- **The pages.** Screens, their layout, and their wording change as they improve. Only the addresses of records are kept.
- **AppWren's Python code.** AppWren is an application, not a library, so importing its modules is not supported.
- **What the assistant says, and what it sends.** Its answers come from a model AppWren does not control, and the words AppWren puts to the model (what it is told, and how it is asked) may change in any release. The protocols it speaks (`openai`, `anthropic`, `bedrock`) and its settings are kept like any other part of the configuration file.
- **The demo organization.** Its people, records, and figures change from release to release.

## Deprecation

When something this page covers has to go:

1. A minor release **deprecates** it. The changelog lists it under *Deprecated*, with what replaces it. A route is marked deprecated in the API description. A setting draws a warning from `appwren doctor` and when the server starts.
2. It **keeps working** for the rest of 1.x.
3. A major release removes it, and its changelog says how to move off it.

## Supported platforms

| Platform | Supported | When support ends |
|---|---|---|
| Python | 3.12 and later | A Python version is dropped only in a minor release after that version's own end of life, announced in the minor release before |
| PostgreSQL | 16, the version every release is tested on | The same rule as Python |
| SQLite | The version that comes with a supported Python | With that Python |

## Fixes

Fixes go into the newest minor release. There are no long-lived branches for older ones, which is why any 1.x upgrades to the newest in one step.
