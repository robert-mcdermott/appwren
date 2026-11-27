# Wave 9: Toward 1.0 (v0.9.0)

**Goal:** the release that 1.0 is made from. The first changes an adopter asked for, starting with who uses an application. Upgrades from every earlier release are checked by a script on both databases. The compatibility promise 1.0 will make is written down. The threat table is walked again and the server is put under sustained load. The maintainer reviews 0.9.0, and 1.0.0 follows with what that review asks for and the promise in force.

**Branch:** `wave-9` · **Target version:** `0.9.0` · **Status:** ☑ done

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.8.0:

1. An application says who uses it: everyone in the organization; or particular units; or kinds of people across the organization, such as managers and supervisors, or hourly employees and contractors; or units and kinds together. It also says how many people use it, and whether people outside the organization do. The application list filters by kind of people, and *what breaks if this goes* says who would be affected (INV-08).
2. A server worker will not start on a database whose schema is behind its code, however it was started.
3. One script upgrades a demo built by every earlier release, from 0.1.0 on, to this one, on SQLite and PostgreSQL. It checks that every row and file is kept, that the history verifies, and that no decision's digest or application's score moves.
4. A compatibility statement covers the API, the configuration file, pack formats, the backup format, the command line, webhooks, and the data home, with rules for deprecation. It is a draft that takes effect at 1.0.0.
5. A second reviewer has walked the threat table against the code. A soak test keeps the server under concurrent load at 5,000 applications and reports errors, latency, and memory.
6. The role-by-route matrix covers every new route; the demo still holds; the accessibility audit and keyboard check pass; the suite passes on both databases; the API keeps the 0.8.0 contract.

Requirements delivered: INV-08 (extended).

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed at the review of 0.9.0:

- **Who uses it is a union, not an intersection** (slice 1). An application is used by everyone in the organization, or by everyone in the units named, together with the kinds of people named wherever they work. Applicant tracking is *everyone in Human Resources, and managers and supervisors across the organization*. A narrower group, such as *clinicians in the research clinic*, is recorded as the unit or as the kind of people, whichever says more.
- **The kinds of people are a list the program keeps** (slice 1), like any other: an administrator renames, adds, and retires them under Admin, Program. AppWren ships leadership, managers and supervisors, hourly employees, contractors and temporary staff, researchers, clinicians, students and trainees, administrative staff, and IT staff; each starter program keeps the ones that fit it and adds its own.
- **Several portfolios (PLT-21) is not in 0.9.0.** Delegated administration of a unit's own program waits for an adopter who needs it. The review of 0.9.0 decides whether 1.0 needs it.
- **The compatibility promise is a draft until 1.0.0** (slice 3). Until then, 0.9 may still change anything it covers, and the changelog says so when it does.

---

## Slice 1: Who uses it ☑

- [x] Everyone in the organization, units, and kinds of people across the organization, on one card with one dialog
- [x] The kinds of people as a program list, in the default program and the starters
- [x] The application list filters by kind of people and by what everyone in a unit uses; *what breaks if this goes* says who uses it; the assistant is told
- [x] The demo says who uses each application
- [x] A server worker refuses a database whose schema is behind

## Slice 2: Upgrades ☑

- [x] `scripts/upgrade-check.py`: every release since 0.1.0 upgraded to this one, on both databases, with every row, file, digest, and score kept. All 16 upgrades pass

## Slice 3: The 1.0 promise ☑

- [x] `docs/compatibility.md`: what 1.0 keeps stable, and how something is deprecated
- [x] The contract test compares with the newest release by version, not by name

## Slice 4: Hardened ☑

- [x] The threat table walked by a second reviewer, with what it finds fixed: two medium findings and seven low, each fixed with a test, and `security.md` brought up to date with the code
- [x] `scripts/soak.py`: sustained concurrent load at 5,000 applications, and what it found fixed

## Slice 5: Release prep ☑

- [x] Guides, changelog, upgrade from 0.8.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- The demo server ran `appwren serve --reload` through waves 6 to 8. It reloaded each wave's code but its database stayed at migration 0025, so every page that read a newer table failed with *The database is unavailable*. `serve` checked the schema once, before starting; a worker restarted by the reloader, or started by a process manager, never checked. Each worker now checks for itself.
- Who uses it is stored as two fields on the application (`org_wide`, `audiences`) beside the units already kept in `application_unit`, so imports, exports, suggestions, history, and the record as of a day take them up with no work of their own. Naming everyone clears the units and kinds, in the service, so the two cannot disagree.
- The demo had always recorded an application as used by the unit that keeps it and the unit above. With *used in a unit* counting the units above, that made a department's tool look used by its whole division, and a tool kept by a division look used by the whole institute. The demo now names only the unit that keeps an application, unless it says more.
- The two new demo applications are made at the very end of the build, so every other record keeps the reference the guides and the accessibility scenes use.
- The upgrade check found no upgrade that loses anything. It did find that the demo builders of some old releases are not quite the same from one build to the next (0.6.0 built 6,772 rows once and 6,778 another time), so it compares each installation with itself before and after, never with a fixed count.
- The second review found that two fixes from the wave 8 review were incomplete: sensitive marks were honoured on the record and its columns but not in other filters or derived places, and the limit on proposals counted by token, not by person. Both are fixed where they arise, with a helper that says which flags read a sensitive field, so a program's own marks are honoured without listing each place again.
- Marking the stage sensitive is now refused. The wave 8 review had withheld it from the checkpoint, but the dashboards, data quality, and every "in service" count depend on it; withholding it everywhere would leave the portfolio unreadable and still tell it by count. A maintainer decision to review.
- The first soak runs, at 5,000 applications with 20 people arriving over a minute, found the server did not leak memory and PostgreSQL never failed a request, but SQLite held up for a minute or two as people arrived. The causes: Home scored every application for every person (1.4 s each, more under contention, as the sqlite3 driver hands the interpreter lock back and forth for every row); every signed-in request took SQLite's write lock just to read its session; a server process ran forty requests at once with fifteen database connections, and the forty-first waited 30 s and failed with 500; and errors raised while checking the session became 500s that dropped the connection. All four are fixed, each with a test in `tests/test_load.py`.
- Left for 1.0, after the maintainer's review: the dashboard, data quality, overlap, and the portfolio list still score every application in service each time they are opened. They are pages for a few people, not everyone, and caching scores between changes is a design of its own. The scheduler's first run on a large installation, which raises every task it finds in one transaction, is a burst worth spreading.
- The schema check added to each server process's start opened a connection that the test suite's fixture, which started the app once per client, left open hundreds of times over on PostgreSQL. The fixture now starts the app once, as a server does, and the shipped migrations are read once.
