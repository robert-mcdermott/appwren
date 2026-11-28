# Changelog

AppWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

### Added

- **More model servers for the assistant.** `[assistant] provider` names the protocol the
  model's server speaks: `openai` (the chat completions interface, as before), `anthropic`
  (the messages interface, the official service by default), or `bedrock` (Amazon Bedrock's
  Converse API, with an Amazon Bedrock API key or signed with access keys from the
  environment). New settings: `region`, `max_tokens`, `temperature`, and
  `timeout_seconds`. A server's own reason for refusing a request is now shown, and an
  answer cut off at the limit, or declined by the model, says so.

- **Limits for paid models.** `[assistant] roles` opens the assistant to some roles only
  (administrators always may), `daily_limit` caps how often each person asks in a day (100
  unless set), and `keep_days` removes exchanges' words after a year unless set, while the
  history keeps that each happened. `headers` sends a gateway its own headers, never a key.
- **`appwren doctor` checks the assistant** where one is set up: what the provider still
  needs in the environment, and with `--assistant`, whether its server answers.

### Changed

- **No temperature is sent unless one is set.** The assistant used to send 0.2, which newer
  models refuse. Set `[assistant] temperature = 0.2` to keep a model of your own as steady
  as before.
- **Exchanges with the assistant are kept for a year**, not for ever, unless `[assistant]
  keep_days` says otherwise, and each person may ask a hundred times a day unless
  `daily_limit` says otherwise.
- The assistant waits up to two minutes for an answer, not one, for models that think
  before they answer (`timeout_seconds`).

## 0.9.0 (2026-11-27)

Wave 9, *Toward 1.0*: the release 1.0 is made from. An application says who uses it:
everyone in the organization, or the units and the kinds of people who do, such as managers
or hourly employees, wherever they work. Every earlier release is upgraded to this one by a
script, on both databases, with nothing lost. The compatibility promise 1.0 will make is
written down as a draft for review. A second reviewer walked the threat table against the code,
and a soak test kept a server of five thousand applications busy with twenty people for ten
minutes, and what each found is fixed. 1.0.0 follows the maintainer's review of this release.

### Added

- **Who uses it.** An application's *Who uses it* card, with one dialog, says whether
  everyone in the organization uses it, or which units do and which kinds of people do
  wherever they work: managers and supervisors for performance reviews, hourly employees and
  contractors for time tracking, or everyone in Human Resources and managers across the
  organization for applicant tracking. With it are about how many people use it and whether
  people outside the organization do. `PUT /api/v1/applications/{ref}/use` sets all of it in
  one change.
- **Kinds of people** are a list the program keeps (*Audiences*), renamed and extended under
  Admin → Program. The default program and each starter program come with their own.
- **Filters by who uses it.** The application list filters by who uses it (everyone, or a
  kind of people) and by what everyone in a unit uses, counting what the whole organization
  and the units above it use. *What breaks if this goes* says who would be without it, and
  the assistant is told who uses each application.
- **The compatibility statement**, in [docs/compatibility.md](docs/compatibility.md): what
  1.x will keep the same, what it does not promise, and how something is deprecated. It is a
  draft until 1.0.0.
- **An upgrade check** that builds a demo with every earlier release and upgrades it to this
  one, on SQLite and PostgreSQL, checking that every row and file is kept, the history
  verifies, and no decision's digest or application's score moves: `scripts/upgrade-check.py`.
- **A soak test** that keeps a server with five thousand applications under concurrent use
  and reports errors, latency, and memory: `scripts/soak.py`.

### Changed

- The units that use an application are no longer a card of their own beside the record;
  they are part of *Who uses it*, and the record's own **Edit** no longer holds that section.
- The demo says who uses each application, names only the unit that keeps an application
  where it says nothing else, and has two more: time and attendance, and performance reviews,
  registered by Human Resources in its last week.

### Fixed

- **Under load, found by the soak test.** Twenty people arriving at once on a SQLite
  installation of five thousand applications held the server up for a minute or two, with
  some requests failing. Home now scores only the applications a person is named on and,
  for those who keep or decide for units, their units' applications, so it no longer costs
  as much as the whole portfolio for everyone. Checking who is signed in only reads, and
  takes SQLite's write lock at most once a minute, to slide the session's expiry. A server
  process has a database connection for each request it runs at once. And a database too
  busy to answer is answered 503 with when to try again, including while checking who is
  signed in, where it had been a 500 that also dropped the connection.
- A server process restarted by `--reload`, or started by a process manager, answered on a
  database whose schema was behind its code, and every page that read a newer table failed
  with *The database is unavailable*. Each process now checks the schema as it starts, as
  `serve` always did, and refuses with what to run.
- The API contract test compared with the newest release by name, so 0.10.0 would have been
  taken for older than 0.9.0. It compares by version.

### Security

A second reviewer walked the threat table in `spec/security.md` against the whole of the
code; the record is in `spec/reviews/`. What it found is fixed, each with a test that failed
before:

- Someone who signs in through the identity provider can no longer give themselves a
  password, which would have let them sign in around the provider and keep roles it had
  taken away.
- An edit is checked against the application a component, deployment, or interface is moved
  to, not only the one it was on; and a contract is said to cover only applications its
  editor keeps.
- A field the program marks sensitive is withheld everywhere the record withholds it: in the
  filters beyond the list's columns, the portfolio's rows, the data-handling report, *what
  breaks if this goes*, and flags whose condition reads it. Flags that tell a covering
  contract's terms are named only to those who may see them.
- A right password no longer clears the count of failed sign-ins from its address, and wrong
  guesses at the current password, when changing it, are limited as at sign-in.
- A dry-run import no longer confirms a restricted application's name; a database error is
  logged without what was typed; and proposals are counted by the person, however many
  tokens of their own they use.

### Breaking

- **The stage cannot be marked sensitive.** Every list, gate, and figure is organized by it.
  An installation that had marked it finds it shown again; saving the program's fields with
  it marked is refused.

## 0.8.0 (2026-11-27)

Wave 8, *Connected*: AppWren fits into the systems around it, all of it optional. Another
process asks whether an application is approved for new use, or for a class of data, and
is told why. A person's own token lets an AI assistant read the portfolio as them and
propose changes, which wait on the record until someone who keeps it accepts them; a small
tool server lets an assistant that speaks the Model Context Protocol do so. An optional
assistant, off until configured, answers questions with links to the records behind the
answer and drafts an application from a document. And a record linked in another system of
record shows how it stands there.

### Added

- **The checkpoint.** `GET /api/v1/checkpoint/{ref}` tells another process whether an
  application is approved for new use, and for a class of data, with every reason: its
  stage, its decision, its support, and the data its record says it handles.
- **Tokens of your own, and suggestions.** Anyone may make a token under Your account that
  acts as them, reads, and proposes changes. A proposal waits on the application until
  someone who keeps it accepts it, as their own edit, or dismisses it.
- **An optional assistant.** Off and invisible until the configuration's `[assistant]`
  names a model server (any with the chat completions interface, including one on the same
  machine). It answers questions about the applications a person may see, with links to the
  records it cites, and drafts an application from a document for the person to correct
  and add. It is never told of applications that handle data more sensitive than the
  configuration allows, it changes nothing, and every exchange is kept.
- **Standings elsewhere.** A system in the program's list of other systems may name a
  `standing_url`; a job then reads how each linked record stands there (approved, open,
  closed) and shows it beside the link, with any change kept in the history.
- **A tool server for AI assistants.** `appwren tools serve` lets an assistant that speaks
  the Model Context Protocol search and read AppWren, ask the checkpoint, see what waits on
  the person, and propose changes, through the API as that person.

### Security

The code this release adds was reviewed before it shipped; the record is in
`spec/reviews/`. What it found is fixed, each with a test: a new password now revokes the
account's own tokens; the checkpoint and the assistant leave out fields the program marks
sensitive; a proposed value has a size limit; an identifier cannot climb a standing
address; and a token never administers.

## 0.7.0 (2026-11-27)

Wave 7, *Adoption*: an organization that has never seen AppWren installs it, makes it its
own, and runs it in production. An installation is backed up, restored, and moved between
SQLite and PostgreSQL by command, and is measured at five thousand applications. It wears
the organization's own colors, logo files, typefaces, and words; begins from a starter
program shaped like the organization; lets other systems in with tokens limited to a role
and tells them what happens with signed webhooks; and is deployed from recipes checked by
`doctor --production`. Its code has been reviewed against a published security standard,
and two new guides cover running a program and adopting AppWren.

### Added

- **Backup and restore.** `appwren backup` writes the whole installation (every table, the
  brand and attachment files, and a manifest) to one file, even while the server runs;
  `appwren restore` loads it into an empty installation and verifies the history. The file
  does not depend on the kind of database.
- **Moving between databases.** `appwren db move` copies an installation into another, empty
  database, from SQLite to PostgreSQL or back, and verifies the history there.
- **The brand kit.** Admin → Appearance adds an accent for dark mode, a message and a
  picture on the sign-in page, up to five links at the foot of the sidebar and the sign-in
  page, a last line for every email (which now opens with the product's name in the
  accent), and the organization's own words for application, component, capability,
  technology, vendor, and unit, used in the menu, page titles, and lists. A new `[branding]`
  section of the configuration file sets an exact palette by day and after dark, logo
  files, typefaces, and any of the above, shown in the app as locked.
- **Starter programs.** `appwren init --program` begins a new installation from the default
  program as a research institute, an academic medical center, a university, a nonprofit,
  or a company would first change it: its own capability map, domains, kinds of unit, data
  classes, funding, fields, and examples. `appwren program starters` lists them, and
  `appwren program import` loads one by its key.
- **API tokens.** An administrator issues a token under Admin → API tokens for one role
  (never administrator), for one unit if the role has one, for reading only unless told
  otherwise, and until a day at most a year away. It is shown once and kept as a hash;
  what it changes is recorded against its name.
- **Webhooks.** Admin → Webhooks registers addresses to be told, in small signed messages,
  when a decision is recorded, an application changes stage, or a confirmation or an
  assessment lapses. Failed deliveries are tried again, and every delivery is listed.
- **The API's contract.** A test holds the API to the last release's OpenAPI document:
  nothing it offered is taken away, and no request asks for more.
- **Deployment recipes.** `deploy/` holds a container image that runs read-only and
  unprivileged, a compose file with PostgreSQL, a sandboxed systemd unit, and nginx and
  Caddy examples. The image's first start can name the organization and the starter
  program. A new `[server] trusted_proxies` setting says whose forwarded headers to believe.
- **`appwren doctor --production`** checks what matters once people depend on an
  installation: an https address, not a demo, PostgreSQL, two administrators, single
  sign-on, email, scheduled work, a recent backup, and who can read the data home.
- **Two new guides.** *The program handbook* is for the portfolio team: the decisions to
  make first, the first ninety days, the yearly rhythm of reviews, campaigns, and reports,
  measures worth watching, and what goes wrong. *Adopting AppWren* is for an organization
  deciding whether, and how, to take it up.
- **Measured at size.** `scripts/perf.py` times the common pages at 5,000 applications and
  50,000 components; the figures are in the configuration guide.

### Security

A review against the OWASP Application Security Verification Standard, level 1, is recorded
in `spec/reviews/`. What it found is fixed, each with a test:

- An API token was taken for the maker of records made at the command line, so a member's
  token could list restricted applications and read contract values.
- A restricted application could be named through a reference to it: as another's
  successor, by trying references one by one, in a message about a capability's primary
  provider, in a scenario, or in the history. It is now *an application you may not see*.
- A connector could be given one of the server's own secret variables, and send it to a
  host of an administrator's choosing.
- A request with no declared length was read in full before the size limit applied.
- Wrong passwords from many addresses could lock an account's owner out; a clean address
  now gets one try.
- A webhook could be pointed at the server's own machine.

### Fixed

- Pages that read every application failed on SQLite past about 32,000 components, from the
  database's limit on query parameters.
- The dashboard, data quality, overlap, the portfolio list, Home, and shares of the
  portfolio are two to twenty times faster on a large portfolio.

## 0.6.0 (2026-11-27)

Wave 6, *Insight*: the record read back as a whole, for leadership. Two portfolio snapshots
side by side say what moved between them, and an application's scores are shown over time;
shares of the portfolio name the costliest and least used applications without feeding any
score; a leadership report for a period is worked out once and kept whole, with a digest
that shows it is unchanged; the portfolio, and any application, can be seen as it stood at
the end of a chosen day, from the history; and a scenario shows what a set of changes would
save, whom it would affect, and what would stop, before anyone commits to it.

### Added

- **Trends.** Reports → Trends puts two portfolio snapshots side by side, or one and today:
  the figures each held, the applications whose recommendation changed, whose scores rose or
  fell by half a point or more, and whose flags came or went, applications added or gone,
  and the decisions recorded between them. An application's Scores part shows its scores
  over time.
- **Shares of the portfolio.** Reports → Shares of the portfolio lists the costliest tenth,
  the dearest tenth per user, the least used fifth, and the oldest fifth of the
  applications in service. A share never feeds a score.
- **Leadership reports.** A manager makes a report for a period under Reports → Leadership
  reports: where the portfolio stood, how the scores moved between the period's snapshots,
  the decisions taken, the reviews closed, initiatives, requests, and retirements with their
  savings. It is worked out once and kept whole, with its SHA-256 digest checked whenever it
  is opened, and prints cleanly. A new guide, *Insight*, covers these.
- **As of a day.** Reports → As of a day shows the applications in service at the end of a
  chosen day, with each one's stage and decision then beside now; an application's History
  part shows it as it stood on a day, value by value, with its decision and scores then.
  Both are read from the history: nothing is stored for them.
- **Scenarios.** Portfolio → Scenarios holds proposed sets of changes (retire this,
  consolidate that into this, replace) with what each would do: the cost saved a year, the
  people whose application would change, the interfaces that would stop, the capabilities
  left with nothing, and the risk that would go with them. A scenario changes nothing until
  it is made into a proposed initiative.

### Changed

- Three more rarely opened dialogs on a record's page (the people named on it, the
  capabilities it serves, and what it is called elsewhere) load when they are opened.

## 0.5.0 (2026-11-27)

Wave 5, *Planning change*: decisions become planned, tracked change. A portfolio review
draws its agenda from what needs deciding and keeps what it decided; a decision to change
something becomes an initiative with its applications and dates, on a roadmap; a request for
something new is checked against what already serves the need before anything is bought; an
application cannot move to a later stage without what that stage requires; and a retirement
is a plan with a checklist that ends with the application retired and its savings on record.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept, and no
score moves. Stage gates are on after the upgrade: see **Changed**.

### Added

- **Portfolio reviews.** Under Portfolio → Reviews, a manager or a unit's leader plans a
  review of a unit and everything beneath it, narrowed by tier if wished, with a date and a
  chair. Drawing the agenda adds the applications that need deciding: those whose decision
  differs from today's recommendation, whose decision is due for review by then, or that have
  none; more can be added by hand. Each item shows what was recommended and decided before,
  and a decision recorded while the review is open is shown on its item and kept there when
  it closes. A closed review changes no more. A review coming up is on Home for the people
  who run it.

- **Initiatives and the roadmap.** An initiative is a planned change (a modernization, a
  migration, a consolidation, a replacement, a retirement, or another) with an owner, a
  stage, dates, and the applications it changes, retires, or moves work onto, each shown
  with the decision on record for it. Portfolio → Roadmap puts initiatives on a timeline by
  unit, kind, and stage, each bar a link. An application's page lists the initiatives that
  change it, and a decision to modernize, replace, consolidate, or retire offers to start
  one with its applications filled in. Their kinds and stages are lists the program can
  rename.

- **Requests for something new.** Under Portfolio → Requests, anyone asks for something
  new: the need, the capability it serves, how many would use it, and when it is needed.
  The request shows every application that already serves that capability and any named
  like it. A steward of the unit, an architect, or a manager weighs options to build, buy,
  partner, or reuse what is on record, and ends it once, with a reason: approved, which
  adds an application in the proposed stage named for it; met by an application on record;
  or declined.

- **Stage gates.** An application cannot move to a later stage without what that stage, and
  those before it, require; the editor, the API, an import, and a catalog file are refused
  with what is missing. Moving back, and retiring, need nothing. The gates are on by
  default and can be switched off on Admin → Program → Decisions, where a record still shows
  what it lacks.
- **The retirement playbook.** On an application's new Retirement part, whoever keeps it
  starts a plan with a date (its planned retirement moves with it) and works through a
  checklist: its users told, its data archived and where, its interfaces removed, its
  licenses and contracts ended, access removed, and its infrastructure torn down, each step
  by a named person on a date with a note. With every step done, completing the plan
  retires the application and keeps its annual cost as the savings. Reports → Retirements
  lists those under way, those done, and the savings by year.
- **Planning change,** a new guide, and the API page's routes for it.

### Changed

- Home gives tasks, campaigns, and reviews icons of their own.
- Three rarely opened dialogs on a record's page (what a component is built on, a
  technology's releases, and what a contract covers) load when they are opened.
- **Breaking:** with the gates on by default, an import or an API call that moves an
  application to a later stage without what that stage requires is now refused. Switch the
  gates off to keep the old behaviour.

## 0.4.0 (2026-11-26)

Wave 4, *Signals*: the facts other tools already know arrive by themselves, marked with
where they came from, and never over a person. Connectors, each switched on by an
administrator for one named source, read support dates, what the repositories know, and who
signs in; the organization's own tools post the rest with a key that can do nothing else; a
catalog file kept beside the code describes an application and its components. Engineering
maturity is measured from checks rather than claims, and what sources supply joins the
scores only where they supply it. A new installation still makes no connection to anything.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept, no
connector is switched on, and no score moves until a source supplies something.

### Added

- **Connectors.** Admin → Connectors lists the tools AppWren can read facts from. Each
  connector is added switched off, for one named source; it only reads; its credential
  stays in an environment variable named on the connector and is never stored. It can be
  checked before it is switched on, runs daily on the scheduler or when asked, and every run
  is recorded: what it read, what it changed, what it could not match, and why it failed. A
  run reads everything first, under a time limit and a size limit, and writes only if all of
  that succeeded, so a failed run changes nothing.
- **Values from other systems.** A value a connector supplies is written to the record's own
  field, kept with its source and when it was read, marked as such on the record, and
  recorded in the history. A person who keeps the record can override it with a reason; the
  override wins until it is removed. Changing such a field by hand counts as an override.
- **End-of-life data.** The first connector reads support dates for technology releases from
  the public endoflife.date dataset, for each technology with an end-of-life key, by the same
  rules as the import from a file: releases are added and dates updated, and nothing is
  removed.
- **Source code hosting.** A connector for GitHub or a GitHub Enterprise server reads, for
  each component whose repository is in one organization: its languages, when its code last
  changed, how many people changed it over 90 days, its open dependency alerts by severity,
  and whether it has a README, tests, continuous integration, automated dependency updates,
  and a catalog file. An application whose every repository was read gets its maintainers
  from those people. The facts are shown on the component and on its application's
  Components part.
- **The identity provider.** A connector for Microsoft Entra ID, read through Microsoft
  Graph, matches each application registered there to a record, by the provider's
  identifier kept on the record or by name or alias, and gives it its active users: the
  people who signed in over the last 30 days.
- **Not on record.** Applications registered with the identity provider that match no
  record are listed once, on Portfolio → Not on record, for whoever adds applications: add
  one with its name filled in and its identifier kept, or dismiss it with a reason.
- **Push sources.** An administrator issues a push key for one of the organization's own
  tools, shown once and kept only as a hash. The tool posts facts to `POST /api/v1/facts` in
  one format (a record, a field, a value, when it was observed), and can do nothing else. A
  batch is checked whole first, so one bad fact writes nothing. Incidents and support tickets
  over 90 days are fields that pushes fill.
- **Catalog files.** An application and its components can be exported as a
  `catalog-info.yaml` to keep beside the code, and a file can be imported into an
  application, with a dry run first: it updates what it describes and adds any component it
  names, and removes nothing, so the same file twice changes nothing. Files are read with a
  safe loader; PyYAML is the sixth runtime dependency.
- **Engineering maturity.** Automated checks for each component (monitoring, backups,
  documentation, tests, continuous integration, automated dependency updates, and no open
  critical dependency alert) give it bronze, silver, or gold, and its application the level
  of its least mature component, with what is missing for the next. They are shown on the
  component and on its application's Components part, as a filter of the applications list,
  and on Reports → Engineering maturity, by unit. The levels and their checks are in the
  scoring model, beside the cadence. Only what is built here, or has a repository, is
  measured.
- **Signals as factors.** What sources supply joins the scores: incidents, open critical and
  high dependency alerts, code activity, and engineering maturity in technical health, and
  support tickets in cost and burden. Each counts only where a source supplies it, so an
  application without one scores as before, and the working names where each came from.
  An installation running an earlier default model unchanged gets them on upgrade.
- **Facts from other systems,** a new guide, and a section on connector credentials in
  Configuration.
- The history names the release whose dates changed, and shows the reason given for an
  override.

### Changed

- A scoring model's dimension adds up to 100 without its signals; a signal comes on top.
- The API fetches nothing an administrator has not switched on. A push key is the one
  credential besides a session, and it only posts facts.

### Fixed

- A component's and a deployment's page named their application twice.

## 0.3.0 (2026-11-26)

Wave 3, *Keeping current*: a portfolio that stays true without a central team chasing it.
The app knows what falls due and says so, in the app and by email; owners confirm their
records on a cadence, and a record nobody confirms lowers confidence where everyone can see
it; campaigns ask the owners in a unit, by a date; departures, renewals, end of support, and
grant ends raise tasks for whoever must act; anything on record can be found; and the
program is shaped in the app, with a preview of what a change would do.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept, and no
record is stale on the day of the upgrade.

### Added

- **The documentation site.** The guides, with their pictures of the demo organization, are
  published at <https://robert-mcdermott.github.io/appwren/>: a home page, one page for each
  guide, the changelog, an API reference written from the OpenAPI document, search, and light
  and dark themes. `node scripts/site/build.mjs` builds it from `docs/` with Node 22 and no
  packages, and fails on a broken link, anchor, or picture; `node scripts/site/audit.mjs`
  checks every page in both themes at desk and phone widths.
- **Scheduled work.** The server runs jobs by itself: triggers, reminders, email, a monthly
  snapshot, and housekeeping. A
  process claims a job before running it, so several servers, or `appwren jobs run` from a
  scheduled task, run each one once between them. Admin → Scheduled work shows each job,
  when it last ran and what it did, and can run or pause it. `[server] scheduler = false`
  leaves the work to `appwren jobs run`.
- **Notices and reminders.** A bell in the top bar counts what is new for you, and opens a
  page of it. Whoever something waits on is reminded two weeks before its date and the day
  after: an assessment about to expire, and a decision's review date and target date. An assessment or a target that stays late goes to the unit's
  steward after a week and its leader after three. Each is said once for a given date.
- **Email, optional.** Name an SMTP server under `[mail]` and notices go by email as well,
  each as it happens or in a daily summary, as each person chooses under Your account. The
  password comes from the environment. Until email is set up nothing is attempted, and
  nothing written before then is ever sent. `appwren mail test` sends a test message, and
  `appwren doctor` checks the server.
- **Confirming a record.** The people named on an application, its unit's stewards, and
  managers confirm that its record is right, in one step from its page: every 6 months for
  tiers 1 and 2, every 12 for the rest. A record past its confirmation is stale: its page
  says so, it is flagged, data quality and the portfolio list count it, its owner is
  reminded, and its data confidence is 15 points lower until someone confirms it. A record
  never confirmed is due one period after it was added or after the upgrade, whichever is
  later, so nothing is stale on the day of the upgrade.
- **Campaigns.** Managers and stewards ask the owners of the applications in a unit, narrowed
  by tier and stage if they wish, to confirm their records or to assess their applications by
  a date (`CMG-0002`). Before starting, it says how many people it would ask and which
  applications have nobody to ask. Each person is told once, with a count, and finds what is
  asked of them on Home. An item closes itself when the record is confirmed or the
  application assessed after the campaign began. The campaign's page shows its progress and
  its coverage by unit, least covered first, and can remind, excuse an application with a
  reason, close, or cancel.
- **Tasks, raised by what happens.** Each hour the triggers look at the dates and the people
  on record. A contract's notice date within 60 days, a release in use within 180 days of its
  end of support, a grant within 180 days of its end, and an accountable owner who has left
  each raise a task for the person who must act, with a date and the reason, and tell them.
  A cause raises one task, never two. A task closes by itself when its cause is settled (the
  contract renewed, nothing on the release, a decision recorded, someone named) or by a person
  with a note. Tasks are on Home, on a page of their own, and in the reminders; the reminder
  of a contract's notice date is now its task's.
- **Passing on what someone holds.** Every person has a page of what they hold: the records
  they are named on and in what role, the contracts and interfaces they own, their open
  tasks, and what campaigns still ask of them. An administrator or a manager passes all of it
  to someone else in one step. Assessments and decisions stay with whoever made them.
- **One search.** The command palette finds records as well as pages, and Search lists
  every kind of record that matches, the best answer first: by name, reference, summary, or
  what something is called elsewhere. It finds only what the searcher may open.
- **Saved views.** Any list's filters are kept under a name from its **Views** button,
  privately, or shared with everyone by stewards, architects, and managers. A view keeps the
  question, so each person who opens it sees only what they may.
- **Applications by what they are built on.** The applications and components lists, and
  their exports, narrow to a technology, one of its releases, or an exact version, such as
  every application on .NET 6, or on 6.0.25. A technology's page links each release to that
  list. An application counts when any of its components is on it.
- **Likely duplicates.** Adding or renaming an application shows those already on record
  whose name or alias is close, or that are the same product from the same vendor.
- **Contesting a score.** Whoever keeps an application says a factor is wrong, what it should
  be, and why, with a link to the evidence. A manager or an architect accepts or answers it,
  and the owner is told. Both stay on the record and in its history. A contest does not move
  a score; putting the record or the assessment right does.
- **The program, shaped in the app.** Admin → Program, for managers of the whole
  organization and administrators: rename, describe, reorder, add to, and retire the values
  of a list (those AppWren's rules read can be renamed and reordered only); add and edit the
  organization's own fields and say which are sensitive; reword the questions and their
  levels; and change the thresholds, every profile's weights, and the cadence. A changed
  scoring model is previewed first, listing every application whose scores, confidence,
  recommendation, or flags would differ, and publishing it changes exactly those. Each change
  publishes a new version or is kept in the history.
- **A portfolio snapshot each month,** kept by the scheduler on the first turn of the month.
- **Starting with one team.** `appwren init` asks for the organization's name and a first
  unit within it, such as the team starting with AppWren (`--organization` and
  `--first-unit` when unattended), so an application can be added at once. **Admin →
  Units → Put a unit above the top** puts a new top unit above the existing one, for a team
  that began at the top. *Getting started* has a section on starting with one team.
- **Owners deciding about their own applications, if switched on.** A program setting, off
  by default, on **Admin → Program → Decisions**: an application's accountable owner who is
  also a manager or a leader over it may record its decision, for a team too small for
  anyone else to. Each such decision is marked *Recorded by its own owner* on the decision,
  in the application's history, and on the Decisions page.
- **Guides:** a new guide, *Keeping current*; shaping the program in the app, scheduled work,
  and email in *Running the program* and *Configuration*; what a stale record costs in *The
  portfolio*; the new routes in the API guide; and pictures of the new screens.

### Changed

- **The default scoring model gains the cadence of wave 3:** how often records are
  confirmed and what a stale one costs, when reminders go, and how far ahead tasks are
  raised. An upgrade brings it to a model that nobody has changed since 0.1.0 or 0.2.0; one
  the organization has shaped is left alone and uses the same values until it says otherwise.

### Fixed

- **A bubble on the portfolio chart opened a page that was not there.** Links inside a
  drawing were followed by the wrong address. Clicking a bubble now opens its application,
  and hovering one shows which application it is and where it stands. Present since 0.1.0.
- **The demo's research software engineer** was named on no application, though the guides
  sent people to see the applications they keep. They now keep the two pieces of research
  software in the demo's storylines.

## 0.2.0 (2026-11-26)

Wave 2, *The landscape*: each application in its surroundings. What it sends and receives
and what data passes, what depends on it and what breaks if it goes, where it runs, what it
costs and what pays, the contracts behind it, what else does the same job, and what it is
built on that is falling out of support.

Upgrade with `uv sync` and `uv run appwren db upgrade`. Every row and file is kept.

### Added

- **Interfaces.** Data passing from one application to another is a record of its own, with a
  reference (`INT-0007`), a method, how often, the classes of data it carries, and an owner.
  An application's new **Connections** part shows what it sends and receives. An interface
  is seen by whoever may see both of its applications and kept by whoever keeps either.
- **Data flows.** Landscape → Data flows follows a class of data between applications, and
  marks any interface that delivers a class the receiving application's record does not
  list.
- **How a record is connected.** Every application, component, capability, technology,
  vendor, and interface opens a picture of what it is joined to, with any neighbor opened a
  ring further. It works from the keyboard, and a list beside it says everything the
  picture does.
- **What breaks if this goes.** An application's Connections part lists what depends on it,
  directly and through those; the interfaces that would stop; the capabilities left with no
  provider, or without their primary; and the people and units affected.
- **Hosting platforms and deployments.** Landscape → Hosting holds the data centers, cloud
  accounts, clusters, and providers things run on. An application's Components part says
  where it, or any of its components, runs: which platform, in which environment, at what
  address. A platform's page lists everything on it, which is what would stop with it.
- **Cost lines and funding.** An application's new **Cost** part breaks its yearly cost into
  lines by what each is for and what pays for it. Once it has lines, its annual cost is
  their sum. Funding sources (budgets, grants, chargebacks, capital projects) are records of
  their own, each showing what it pays for.
- **Contracts.** Portfolio → Contracts holds agreements with vendors: the applications each
  covers and the licenses they use, the term, the date by which the vendor must be told, and
  whether a data agreement is in place. A contract is shown only to those who may see the
  cost of an application it covers.
- **Two cost factors and two flags.** Cost and burden now weighs cost per user, and the share
  of licenses bought that are in use. Flags are raised for a contract's notice date within
  90 days, and for confidential or restricted data under a contract with no data agreement.
- **Cost on the dashboard,** by category and by what pays, for those who see every
  application's cost.
- **Overlap.** Landscape → Overlap lists every capability served by more than one application
  in service, with those applications side by side: scores, recommendation, decision,
  people, and cost where the reader may see it.
- **The capability map, measured.** The map can show, for each capability, how many
  applications serve it, the average of any score, data confidence, or the technical health
  of the weakest application that serves it. Each figure opens the applications behind it.
- **Lifecycle.** Landscape → Lifecycle shows the technology releases applications run on,
  soonest end of support first, as a timeline with how many components and applications are
  on each; and the applications with a planned retirement.
- **Radar.** The technologies in use by ring (adopt, trial, assess, hold), with how much
  runs on each, and those in use that nobody has placed.
- **Support dates from a file.** `appwren technologies import-eol FILE`, or **Import support
  dates** on the Technologies page, adds releases and updates their dates from a file of
  end-of-life data, matched by each technology's end-of-life key. It says what it would
  change before it changes anything, and removes nothing. AppWren does not fetch the file.
- **Data handling.** Reports → Data handling lists the applications that handle a chosen class
  of data, with who answers for each, where it runs, how people sign in, what it is built on
  and whether that is supported, the interfaces that carry the class, and whether a data
  agreement covers it. The same rows export as CSV or JSON.
- **History, in one place.** Reports → History shows every change, newest first, to managers,
  auditors, and administrators: narrowed to a person, a record, a kind of record, or dates.
- **Links to other systems.** An identifier in another system is shown as a link where the
  program gives that system an address pattern, such as `https://code.example.org/{id}`.
- Lists of applications, the portfolio list, and their exports can be narrowed by capability
  and by class of data.
- **Guides.** A new guide, *The landscape*; cost and contracts in *The portfolio*; and what an
  upgrade does to the program in *Running the program*.

### Changed

- An application that receives data through an interface now counts among the dependents of
  the application that sends it, so recording interfaces can raise a source's business value.
- **The default scoring model has a new version.** Cost and burden is now annual cost 30,
  cost per user 15, license use 10, support effort 25, and change effort 20, so scores for
  cost and burden move. An installation still running the previous default gets the new
  one on upgrade; one that has shaped its model keeps it, and can take the new factors from
  the default program when it chooses.
- A record's history names the vendor, application, or person a change refers to, where it
  showed a number.

### Fixed

- A record's history told an assessment, a decision, a capability served, and a unit that
  uses an application each as "Added this application". Each is now told for what it is, and
  the copy of a decision onto its application is no longer told as a second change.

## 0.1.0 (2026-11-26)

Wave 1, *The portfolio*: install, sign in, and keep one record of every application, with
what it is built on and what it does for the organization; assess it, read four scores with
their working, see the recommendation and its rule, and record what people decided.

### Added

- **Foundation.** `appwren init`, `serve`, `db upgrade`, `db current`, `verify`, and `doctor`.
  Deployment settings in `appwren.toml` with environment overrides; secrets are refused in
  the file. SQLite by default and PostgreSQL by address, on one model and one set of
  migrations. Every change is written to an append-only, hash-chained history in the same
  transaction, and `appwren verify` finds the first event that has been altered.
- **Accounts and roles.** Local accounts with scrypt-hashed passwords, server-side sessions,
  CSRF protection, and throttled sign-in. Seven roles: admin, manager, architect, auditor,
  leader, steward, and member, some limited to a unit and everything beneath it. Every API
  route is checked against one policy table.
- **Single sign-on.** Optional OpenID Connect beside local accounts, with the provider's
  application roles or groups mapped to roles, unit scopes, and memberships under Admin.
- **Units.** The organization as a hierarchy of any depth, with CSV import of units and
  people that can be run dry first and reports every problem by row.
- **The web app.** Sign-in, the app shell with a command palette (⌘K), your account, and
  admin screens for people, units, single sign-on, and appearance. Light, dark, and system
  modes and three palettes, each checked for contrast. Branding with a live preview.
- **Applications.** Each with a permanent reference (`APP-0042`), the unit that answers for
  it, a lifecycle stage and its date, sourcing, purpose, pace, domain, criticality tier,
  vendor and product, hosting, users, maintainers, sign-in, data handled, monitoring,
  backup, cost and funding, research facts, and the organization's own fields. Exactly one
  accountable owner, and people in other roles. The units that use it. What its stage still
  requires, shown on the record.
- **Components, technologies, vendors, and capabilities.** Components with the technologies
  and releases they are built on; technologies with releases and their support dates, and
  whether each is supported, ending, or past its end; vendors; a capability map, loaded
  with a starter map, with at most one primary provider per capability. Applications
  depend on, are part of, and replace one another.
- **Sensitive fields.** Cost and security details are withheld from people with no role
  over an application, in records, lists, filters, sorting, and history.
- **Program packs.** `appwren program export` and `appwren program import` move the whole
  program between installations, checked whole before anything is loaded, with a dry run.
- **Assessment.** A short question bank, each question with a definition for every level and
  *Don't know* always allowed. Assessments are never edited; the next supersedes the last,
  and answers expire after 12 to 24 months depending on the tier.
- **Scores with their working.** Business value, technical health, cost and burden, and risk
  exposure, each a weighted average of defined factors from answers, recorded facts, and
  what the records around the application say (technology support, capabilities,
  dependents). Data confidence says how much is known. Every score opens to its factors,
  levels, weights, and the sum.
- **Recommendations and flags.** Ordered rules recommend invest, maintain, tolerate,
  modernize, replace, consolidate, retire, incubate, or assess, with guardrails; flags such
  as restricted data on unsupported technology, a grant ending, or one person keeping it.
  Profiles for shared platforms and research software. The scoring model and question bank
  are versioned, and a snapshot keeps a score as it was.
- **Decisions.** A manager, or a leader of the application's unit, records a disposition with
  a rationale, a review date, a target date, and a successor; never the application's own
  accountable owner. Each decision keeps the scores it was made against, and is never
  edited. Where today's recommendation differs, both are shown as a mismatch.
- **The portfolio chart.** Business value against technical health, or against cost and
  burden; bubbles sized by cost where the reader may see it and colored by risk exposure;
  thresholds and quadrants; a table of the same points; and the applications too little is
  known about to place.
- **Portfolio snapshots.** A manager keeps every application's scores together for a review;
  each snapshot reopens unchanged.
- **Home.** One list of what each person owes, most urgent first: applications to assess,
  flags, and records missing what their stage requires; for stewards, applications nobody
  answers for; for managers and leaders, decisions waiting.
- **The dashboard and data quality.** Where the portfolio stands by recommendation, decision,
  lifecycle, sourcing, flags, confidence, and technology support; and what is missing, by
  unit. Every figure opens exactly the list it counts.
- **Import and export.** Applications come in from CSV with a dry run that names every problem
  by row, and update by reference; nothing is loaded unless every row is good. Every list
  exports as CSV or JSON, withholding what the reader may not see, and each export is
  recorded.
- **The demo organization.** `appwren demo` builds the fictional Bramblewood Institute for
  Health Research, with two years of history made by the real services under a simulated
  clock: units, people, applications and their parts, assessments, quarterly snapshots, and
  decisions, with storylines for every screen. It marks itself as a demo, offers one-click
  sign-in as its sample people from the machine it runs on, and refuses to listen beyond it
  unless started with `--demo-on-network`.
- **Guides.** Getting started, the portfolio, running the program, configuration, and the
  API, with screenshots of the demo organization taken by `scripts/capture.mjs`; the
  command reference and the OpenAPI document are written from the code, and a test keeps
  them current.
- **Accessibility checks.** `scripts/a11y-audit.mjs` builds a fresh demo and checks 38
  screens in three palettes, light and dark, for names, labels, headings, landmarks, target
  sizes, and the contrast of every piece of text. `scripts/keyboard-check.mjs` checks the
  skip link, a record's parts, the working behind a score, and the portfolio chart from the
  keyboard. Neither needs anything installed beyond Node and Chrome.
