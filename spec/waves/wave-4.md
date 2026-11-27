# Wave 4: Signals (v0.4.0)

**Goal:** most technical facts arrive by themselves from the tools that already know them, labelled with their source, and never override a person ([ADR-0003](../decisions/0003-quiet-by-default.md)). Waves 1 to 3 made a record people can keep current. This wave lets the facts that are already known somewhere else (when code last changed and by how many people, when a release stops being supported, how many people signed in) arrive without anyone typing them, while a fresh installation still makes no connection to anything.

**Branch:** `wave-4` · **Target version:** `0.4.0` · **Status:** ◐ in progress

Engineers come first here ([roadmap](../roadmap.md)): the code-hosting and end-of-life connectors are the ones built and polished first, because they answer the questions engineers are asked most (what is this built on, is it still supported, who keeps it).

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.3.0:

1. A new installation makes no outbound connection. An administrator enables each connector separately, for a named source; its credential comes from an environment variable and is never written to the configuration file or the database; it only reads (SIG-01).
2. Every run of a connector is recorded: when, how long, what it read, what it changed, what it could not match, and why it failed. A run has a time limit and a size limit on what it reads. A connector that fails changes nothing in that run and says so on Admin → Connectors (SIG-01).
3. Every value a connector supplies is kept with its source and the time it was read, shown beside the field as such, and recorded in the history like any other change. A person can override it with a reason; the override wins until they remove it (SIG-02).
4. Source code hosting gives each component with a repository its languages, last change, active contributors, and open dependency alerts; an application's maintainers follow from its components' contributors (SIG-03).
5. End-of-life data gives technology releases their support dates from a public dataset, matched by each technology's key, with the same rules as the import from a file (SIG-04).
6. The identity provider lists the applications registered with it that are not on record, for a person to add or dismiss, and gives each matched application its active users from sign-ins (SIG-05).
7. Any fact can be posted to the API in one generic format by a script holding a push key an administrator issued; a key only posts facts (SIG-06).
8. A catalog file kept in a repository describes an application and its components in the common descriptor format, and is imported with a dry run and exported (INV-17).
9. Facts from sources join the factors they inform, with their source in the working; a signal is a factor only where a source supplies it, so an application without one scores as before (SCR-11).
10. Automated checks per component (monitoring, backups, documentation, tests, continuous integration, dependency updates) roll up to bronze, silver, or gold, for a component and for its application (SCR-12).
11. The role-by-route matrix covers every new route; no test reaches the network; the demo shows every new screen with convincing data; the accessibility audit and keyboard check pass; the suite passes on both databases.

Requirements delivered: SIG-01 to SIG-06; INV-17; SCR-11, SCR-12.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Connectors are set up in the app, credentials in the environment.** An administrator adds a connector on Admin → Connectors with what is not secret (an address, an organization, a tenant) and the name of the environment variable that holds its credential. The credential is read when the connector runs and never stored (slice 1).
- **A sourced value is written to the record's own field, and remembered with its source.** Everything that reads the field (lists, filters, exports, the engine) goes on reading one place. An override is the same: the field holds the person's value, and the connector's latest reading waits beside it (slice 1).
- **Each connector runs daily** by default, on the scheduler of wave 3, and can be run now from its page (slice 1).
- **The first sources:** GitHub and GitHub Enterprise for code hosting; the public endoflife.date dataset for support dates; Microsoft Entra ID, through Microsoft Graph, for the identity provider. Each is behind one small interface, so others can follow (slices 2 to 4).
- **Discovery is a list, not records.** Applications registered with the identity provider and not on record are listed for a person to add or dismiss. A connector never creates a record (slice 4).
- **A push key** is a secret an administrator issues for one push source, shown once and kept only as a hash. It may post facts and nothing else (slice 5).
- **Catalog files are YAML,** read with a safe loader. That adds PyYAML, the sixth runtime dependency (slice 5).
- **Maturity levels:** bronze is monitoring, backups, and documentation; silver adds tests and continuous integration; gold adds automated dependency updates and no open critical dependency alert. An application is at the level of its least mature component. The checks and levels are in the program, beside the cadence (slice 6).

---

## Slice 1: Connector framework ☑

**Goal:** the means of every connector: switched on one at a time, run on a schedule, recorded, and their values kept with their source.

- [x] `connector` (a kind, a name, its settings, the environment variable its credential is in, whether it is on, how often it runs) and `connector_run` (when, how long, status, counts, what it could not match, the reason it failed)
- [x] `fact_value`: a field of a record, the value a source last read and when, and a person's override with a reason
- [x] The runner: one job on the scheduler runs each connector that is on and due, with a time limit, a size limit on responses, and every run recorded; a run that fails changes nothing
- [x] Admin → Connectors: the kinds there are, adding and switching one on, its settings, checking it reaches its source, running it now, its runs and what each did
- [x] On a record: a sourced value marked with its source and when it was read; override with a reason, and remove the override
- [x] A fake source inside the tests, so no test reaches the network

**Acceptance:** with no connector switched on, no outbound connection is made; a connector reading a value writes it with its source, an override wins until removed, and a failed run leaves every value as it was.

## Slice 2: Source code hosting ☐

**Goal:** what the repositories know about each component.

- [ ] A GitHub connector: a host (github.com or an enterprise address), an organization, a token with read access
- [ ] For each component whose repository is on that host: its languages, its last change, its active contributors over 90 days, its open dependency alerts by severity, and whether it has a README, tests, continuous integration, dependency updates, and a catalog file
- [ ] An application's maintainers from its components' contributors, sourced
- [ ] Shown on the component's page and its application's Components part

**Acceptance:** against a fake host inside the tests, each fact lands on the right component with its source; a repository the token cannot read is reported unmatched, and nothing else changes.

## Slice 3: End-of-life data ☑

**Goal:** support dates nobody types.

- [x] An end-of-life connector reading the public dataset for each technology with a key, by the rules of the import from a file: it adds releases, updates dates, removes nothing
- [x] Each date it sets is sourced; a date a person set by hand is an override

**Acceptance:** a run adds the releases and dates the dataset has; a second run changes nothing; a date a person overrode stays theirs.

Built with slice 1, as the framework's first connector: it needs no credential, so it shows the whole path from switching on to an override without anything to set up.

## Slice 4: Identity provider ☐

**Goal:** who signs in, and what is registered that the portfolio does not know.

- [ ] An identity provider connector for Microsoft Entra ID: a tenant, a client, and its secret
- [ ] Applications registered there are matched to records by their identifier in the provider, kept as an external reference, or by name
- [ ] Those not on record are listed on Admin → Connectors for a person to add (with the name filled in) or dismiss
- [ ] Each matched application's active users over 30 days from sign-ins, sourced, into its users

**Acceptance:** against a fake provider inside the tests, matched applications get their users with the source; an unmatched one is listed once, and adding it makes a record named for it.

## Slice 5: Push and catalog files ☐

**Goal:** everything else, from the tools the organization runs itself.

- [ ] Push sources: an administrator issues a push key, shown once; `POST /api/v1/facts` takes facts in one format (a record's reference, a field, a value, when it was observed) from a script holding the key, and nothing else
- [ ] Incidents and tickets over 90 days as fields that pushes fill, joining reliability and support effort
- [ ] Catalog files: import a repository's catalog file into an application and its components, with a dry run; export an application as one; the code-hosting connector reports where a repository has one

**Acceptance:** a pushed fact lands with its source; a key cannot read anything or post to any other route; a catalog file imported twice changes nothing the second time.

## Slice 6: Engineering maturity ☐

**Goal:** what engineering practice each component has, measured.

- [ ] The checks, each from a record's field or a sourced fact: monitoring, backups, documentation, tests, continuous integration, dependency updates, no open critical alert
- [ ] Bronze, silver, and gold for each component, and for its application at the level of its least mature component; what is missing for the next level
- [ ] Shown on the component and application pages, as a list filter, and as a report by unit
- [ ] Signals as factors: the facts from sources join the factors they inform, where a source supplies them

**Acceptance:** a component's level is exactly what its checks give, and the report's counts are the length of the lists behind them.

## Slice 7: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.3.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **CI tests each commit's files once.** The workflow ran every test on the push and again for the pull request, though spec/process.md said otherwise from wave 1. It now does what the process says: a pushed branch is tested, its pull request shows that result, a merge holding already-tested files and a tag start nothing, and a newer push stops the older run.
- **A run reads first and writes after.** Reading a source takes as long as the source does, so the reading holds no lock on the database; only once all of it has succeeded is it written, in one transaction. A record removed in between is passed over.
- **The demo's connector is switched off.** The demo has the end-of-life connector with three weeks of runs, one failed, and one date overridden, then switched off, so that a demo never reaches out to anything.
