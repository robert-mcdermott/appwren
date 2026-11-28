# Roadmap

AppWren ships in **waves**. Each wave is a release (wave 1 → v0.1.0, wave 2 → v0.2.0, …) and is split into **slices**: coherent chunks of related work. The last slice of every wave prepares the release. See [process.md](process.md) for how this works day to day.

The order follows how a portfolio practice grows. Wave 1 proves the core loop: know what you run and who answers for it, assess it, see an explainable recommendation, and record a decision. Wave 2 adds the landscape around each application: what it connects to, where it runs, what it costs, and what breaks if it goes. Wave 3 keeps all of it current without a central team chasing. Wave 4 lets facts arrive from the tools that already know them. Wave 5 turns decisions into planned change. Wave 6 answers leadership's questions over time. Waves 7 and 8 make it something another organization can adopt and connect. Wave 9 is the release 1.0 is made from. Wave 10 makes the assistant ready for the models organizations pay for and the largest portfolios quick, and 1.0 follows the maintainer's review. Every wave ends with something that can be demonstrated on the demo organization.

**Whose work comes first.** The first adopters are product, application, and software engineering teams and the IT leaders they report to (see [vision.md](vision.md)). Within every wave, what an owner of a few applications and a portfolio manager use is built first and polished most: registering an application, the home page, the scorecard and its working, and the decision in wave 1; dependencies, technology lifecycle, and cost in wave 2; attestation and triggers in wave 3; the code-hosting and end-of-life connectors in wave 4. The order of the waves is unchanged.

| Wave | Version | Theme | The demo at the end |
|---|---|---|---|
| 1 | v0.1.0 | **The portfolio** | Install, sign in, import an application list, and hold a portfolio of applications with owners, components, technologies, and capabilities; each assessed, scored with its working, given a recommendation, and decided by a named person |
| 2 | v0.2.0 | **The landscape** | Interfaces and the data they carry, dependencies and what breaks, deployments and hosting, cost lines and contracts, overlap, and technology lifecycle |
| — | — | **Documentation site** | A product site with illustrated guides, screenshots of the demo organization, and an API reference |
| 3 | v0.3.0 | **Keeping current** | Attestations, campaigns, reminders and email, triggers, search, and the program edited in the app |
| 4 | v0.4.0 | **Signals** | Connectors an administrator turns on, facts with their source, engineering maturity, catalog files from repositories |
| 5 | v0.5.0 | **Planning change** | Review cycles, initiatives and the roadmap, intake of new requests, stage gates, and the retirement playbook |
| 6 | v0.6.0 | **Insight** | Trends between snapshots, a leadership report, the portfolio as of any date, and scenarios |
| 7 | v0.7.0 | **Adoption** | Another organization installs, brands, and runs AppWren in production, with starter programs, tokens and webhooks, deployment recipes, and a security review |
| 8 | v0.8.0 | **Connected** | Other processes check an application's standing; assistants read and draft; links to other governance records; all optional |
| 9 | v0.9.0 | **Toward 1.0** | Who uses each application, upgrades from every release checked by script, the compatibility promise written down, and the server hardened |
| 10 | v0.10.0 | **The assistant, ready** | The assistant speaks to the official services and to Amazon Bedrock as well as to a model of one's own, with limits on who uses it, how much, and how long exchanges are kept; the pages that score the whole portfolio answer quickly at 5,000 applications |
| — | v1.0.0 | **Stable** | After the maintainer's review of 0.9.0: its changes, and the promise in force |

Status key: ☐ planned · ◐ in progress · ☑ done

---

## Wave 1: The portfolio (v0.1.0) ☑

**Goal:** prove the core loop. The organization knows what applications it runs and who answers for each; owners describe them and answer a short assessment; the system works out four scores with their working, a confidence figure, flags, and a recommendation; and a named person records what to do, on a record that cannot be quietly changed.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Foundation | Project skeleton, configuration, data home, the ORM model and migrations on SQLite and PostgreSQL, the service layer with the event log and hash chain, command line and API skeletons, tooling and continuous integration | ☑ |
| 2 | Accounts, roles, and units | Local accounts and sessions, single sign-on, the seven roles with scopes, the route policy table, the unit hierarchy, import of units and people | ☑ |
| 3 | Web app and design system | Vanilla JS shell, tokens, three palettes in light and dark, the wren mark, branding settings with live preview, command palette, core components | ☑ |
| 4 | Inventory | Applications, components, vendors, technologies with releases, and capabilities; people in roles; units that use an application; links; the default program's vocabularies and fields; required fields by stage; sensitive fields; program packs | ☑ |
| 5 | Assessment and the engine | The question bank, assessments, facts, the engine with profiles, bands, rules, guardrails, and flags; the working; the preview; score snapshots | ☑ |
| 6 | Decisions and the portfolio chart | Decisions with their authority, mismatches, portfolio snapshots, the portfolio chart and its table | ☑ |
| 7 | Home, dashboard, and data quality | What each person owes; the dashboard and data quality pages with every figure linked to its records; spreadsheet import and export of applications | ☑ |
| 8 | Demo organization | The fictional institute, built through the services under a simulated clock, with storylines for every wave 1 screen | ☑ |
| 9 | Release prep | Guides, quickstart, changelog, accessibility check, version, release | ☑ |

Detail: [waves/wave-1.md](waves/wave-1.md)

## Wave 2: The landscape (v0.2.0) ☑

**Goal:** see each application in its surroundings: what it talks to and what data passes, where it runs, what it costs and who pays, what else does the same job, and what breaks if it goes.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Interfaces and data flows | Interfaces with direction, method, frequency, owner, and data classes; the flow view for a data class | ☑ |
| 2 | Dependency graph and impact | The focused graph around any record; *what breaks if this goes* | ☑ |
| 3 | Deployments and hosting | Environments, hosting platforms, deployments of applications and components | ☑ |
| 4 | Cost, funding, and contracts | Cost lines by category and funding source, contracts with renewal and notice dates, cost per user and license use as factors | ☑ |
| 5 | Overlap and the capability heat map | Capabilities served more than once, side by side; the tree colored by any score | ☑ |
| 6 | Technology lifecycle | The lifecycle timeline, the technology radar, end-of-life data imported from a file | ☑ |
| 7 | Exports for a risk analysis | Applications by data class with owners, versions, hosting, sign-in, and support status; external references; the organization-wide history | ☑ |
| 8 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-2.md](waves/wave-2.md)

## Documentation site (between v0.2.0 and v0.3.0) ☑

**Goal:** a product site that lets someone outside the project find AppWren, see it, and try it. It waits until the main screens have settled; screenshots taken during wave 1 would be stale within weeks. The Markdown in the repository stays the documentation, and the site is built from it unchanged ([ADR-0009](decisions/0009-documentation-toolchain.md)).

- **Site generator:** `scripts/site/build.mjs`, needing Node 22 and no packages: a home page and one page per guide, a menu in reading order, search, light and dark themes from AppWren's own tokens, the changelog, and an API reference from the OpenAPI document. The build fails on a broken link, anchor, or image.
- **Screenshots of the real app:** a capture script builds a fresh demo organization, starts AppWren on it, signs in as the right sample person for each scene, and saves each scene in both themes.
- **An accessibility audit** over the same scenes, and one for the site itself at desk and phone widths.
- **Publishing:** the site is whatever is committed on the `gh-pages` branch, written only when asked to publish. The site states the version it describes.

## Wave 3: Keeping current (v0.3.0) ☑

**Goal:** a portfolio that stays true without a central team chasing it.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Schedules and email | The job scheduler, the cadence table, reminders and escalation, SMTP delivery, digests, preferences, in-app notices | ☑ |
| 2 | Attestation | Owners confirm their records on a cadence by tier; stale records lower confidence | ☑ |
| 3 | Campaigns | Assessment and attestation campaigns to owners in a scope, with progress by unit | ☑ |
| 4 | Triggers and reassignment | An owner leaving, a renewal, an end of support, a grant ending; reassignment in one step | ☑ |
| 5 | Find and tidy | Search across all records, saved views, likely duplicates, contesting a score | ☑ |
| 6 | Program editors | Vocabularies, fields, the wording of questions, profiles, thresholds, and cadences edited in the app with an impact preview; monthly snapshots (rules stay with packs) | ☑ |
| 7 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-3.md](waves/wave-3.md)

## Wave 4: Signals (v0.4.0) ☑

**Goal:** most technical facts arrive by themselves from the tools that already know them, labelled with their source, and never override a person ([ADR-0003](decisions/0003-quiet-by-default.md)).

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Connector framework | Enabling, scheduling, run records, sourced values with overrides, Admin → Connectors | ☑ |
| 2 | Source code hosting | Languages, last change, contributors, and dependency alerts per repository | ☑ |
| 3 | End-of-life data | Support dates for technology releases from a public dataset | ☑ |
| 4 | Identity provider | Registered applications not on record, to add or dismiss; sign-ins as active users | ☑ |
| 5 | Push and catalog files | One generic push format for any fact; software catalog files from repositories | ☑ |
| 6 | Engineering maturity | Automated checks per component rolled up to bronze, silver, or gold | ☑ |
| 7 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-4.md](waves/wave-4.md)

## Wave 5: Planning change (v0.5.0) ☑

**Goal:** decisions become planned, tracked change.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Review cycles | A portfolio review with its scope, agenda, recommendations and mismatches, and the decisions taken | ☑ |
| 2 | Initiatives and roadmap | Initiatives linked to applications, on a roadmap with their dates | ☑ |
| 3 | Intake | A request for something new, a check for what already serves the need, a build, buy, or partner evaluation | ☑ |
| 4 | Stage gates | Required fields enforced at each lifecycle stage | ☑ |
| 5 | Retirement playbook | The plan, the checklist, archival of data, and savings realized | ☑ |
| 6 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-5.md](waves/wave-5.md)

## Wave 6: Insight (v0.6.0) ☑

**Goal:** answer leadership's questions from the record, with figures that explain themselves.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Measures and trends | Defined measures; movement between snapshots | ☑ |
| 2 | Leadership report | A periodic report frozen as a snapshot that reopens unchanged | ☑ |
| 3 | As of | Any record, and the portfolio, as it stood on a chosen date | ☑ |
| 4 | Scenarios | A proposed set of changes and their effect on cost, users, interfaces, capabilities, and risk | ☑ |
| 5 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-6.md](waves/wave-6.md)

## Wave 7: Adoption (v0.7.0) ☑

**Goal:** an organization that has never seen AppWren installs it, makes it its own, and runs it in production.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Production | Measured performance at 5,000 applications; several workers; backup, restore, and moving between databases | ☑ |
| 2 | Brand kit | A custom palette, sign-in page message, email header, footer links, the organization's own terms | ☑ |
| 3 | Starter programs | Program packs for a research institute, an academic medical center, a university, a general nonprofit, and a company | ☑ |
| 4 | API for others | Scoped tokens, signed webhooks, a recorded API contract | ☑ |
| 5 | Deployment | A container image, a compose file, a hardened systemd unit, proxy examples, `doctor --production` | ☑ |
| 6 | Security and accessibility review | The standard security verification review; the full accessibility audit. A screen-reader session by a person is still to do | ☑ |
| 7 | The program handbook | One guide for a portfolio team; the adopter's guide | ☑ |
| 8 | Release prep | Guides, changelog, release | ☑ |

## Wave 8: Connected (v0.8.0) ☑

**Goal:** fit into the systems around it, all of it optional.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | A reference others can check | Other processes ask whether an application is approved for a use or a data class | ☑ |
| 2 | Tool server for assistants | An optional server through which an AI assistant reads the portfolio under a person's permissions and drafts changes they confirm | ☑ |
| 3 | Optional assistant | Off by default; drafts records from documents and answers questions with links to their records, with any compatible provider including a local one | ☑ |
| 4 | Other governance records | Links to records in other systems of record, with their standing | ☑ |
| 5 | Release prep | Guides, changelog, release | ☑ |

## Wave 9: Toward 1.0 (v0.9.0) ☑

**Goal:** the release that 1.0 is made from: the first changes an adopter asked for, upgrades from every earlier release checked by script, the compatibility promise written down, and the threat table walked again.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | Who uses it | Everyone in the organization, units, or kinds of people across it, such as managers or hourly employees; a filter by kind of people; who would be affected if it went | ☑ |
| 2 | Upgrades | Every release since the first upgrades with every row and file kept, on both databases, checked by script | ☑ |
| 3 | The 1.0 promise | A compatibility statement for the API, configuration file, pack formats, and data home, and deprecation rules, in force from 1.0.0 | ☑ |
| 4 | Hardened | The threat table walked by a second reviewer; load and soak tests | ☑ |
| 5 | Release prep | Guides, changelog, release | ☑ |

Detail: [waves/wave-9.md](waves/wave-9.md)

## Wave 10: The assistant, ready (v0.10.0) ◐

**Goal:** the optional assistant ready for the models organizations pay for, and the pages that score the whole portfolio quick at its largest, with every result as before.

| Slice | Name | Delivers | Status |
|---|---|---|---|
| 1 | More model servers | Chat completions, the messages interface, and Amazon Bedrock; no temperature unless set; clearer refusals | ◐ |
| 2 | The assistant, for paid models | Who may use it, a daily limit per person, how long exchanges are kept, headers for a gateway, and checks in `appwren doctor` | ☑ |
| 3 | Quick at its largest | Facts read sooner, scores kept between changes and checked against fresh ones, the scheduler's first run in batches | ☐ |
| 4 | Reviewed | The wave's code walked against the threat table | ☐ |
| 5 | Release prep | Guides, changelog, upgrades, release | ☐ |

Detail: [waves/wave-10.md](waves/wave-10.md)

## Stable (v1.0.0) ☐

**Goal:** something an organization can build on. The maintainer reviews 0.9.0; 1.0.0 makes the changes that review asks for and puts the compatibility promise in force.

## Later

Ideas deliberately not scheduled. Each needs evidence from adopters before it earns a wave.

- **Cloud cost connectors** reading billing exports by tag, beyond the push format.
- **Monitoring checks** that confirm each production deployment has monitoring and alerting.
- **A configuration-database bridge** that keeps deployments in step with an infrastructure inventory by reference.
- **Procurement and accounts-payable import** for contracts and spend.
- **A standard technology cost taxonomy** for cost roll-ups.
- **Localization** of the interface.
- **Several portfolios (PLT-21).** Units run their own portfolio views with delegated administration, rolled up to the organization's. Parked at 0.10.0 by the maintainer: not to be started until they ask for it.
- **Several organizations in one installation**, for consortia and shared service centers.
- **A shared pack library** where organizations publish and reuse capability maps and programs.

## Never

Kept here so the question does not need to be asked again. These would change what AppWren is. See [ADR-0003](decisions/0003-quiet-by-default.md).

- Scanning networks, devices, or cloud accounts to discover applications; endpoint agents.
- Anything that changes, blocks, or decommissions another system.
- Holding the data that applications process.
- Deciding a disposition without a named person.
