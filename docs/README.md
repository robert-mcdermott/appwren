# AppWren documentation

These guides describe AppWren 0.10.1, and are published with pictures at <https://robert-mcdermott.github.io/appwren/>. Read them in this order if you are new, or go straight to the one for your part.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Adopting AppWren](adopting.md) | An organization deciding whether, and how, to take it up | Who it suits, trying the demo, what to settle first, a path from nothing to a running program in a quarter, connecting other systems, what has been checked |
| 2 | [Getting started](getting-started.md) | Whoever installs AppWren and sets it up | Choosing a starter program, installing, `init`, `doctor`, `serve`, first sign-in; then, in order: units, people and how they get in, roles, vendors, bringing in your applications from a spreadsheet and what each file must hold, what the scores need, telling people, the first decisions, and seeing that it works; starting with one team; putting it in front of other people; the demo organization |
| 3 | [The portfolio](the-portfolio.md) | Everyone who keeps, assesses, or reads an application | What counts as an application, the record and its stages, components and technologies, capabilities, assessment, the scores and their working, recommendations, flags, decisions, cost lines, funding, contracts, import and export |
| 4 | [The landscape](the-landscape.md) | Architects, the portfolio team, and anyone asking what an application touches | Interfaces and data flows, the picture of how a record is connected, what breaks if an application goes, hosting platforms and deployments, overlap, the capability map and its measures, the lifecycle timeline, the radar, support dates from a file, who handles a class of data |
| 5 | [Keeping current](keeping-current.md) | Everyone who keeps an application, and the portfolio team | Home and the bell, reminders, email, confirming a record and what a stale one costs, campaigns, tasks raised by what happens, passing on what someone holds, search and saved views, likely duplicates, contesting a score |
| 6 | [Planning change](planning-change.md) | The people who decide what happens to applications, and those who carry it out | Portfolio reviews and their agendas, initiatives and the roadmap, requests for something new, stage gates, the retirement playbook and savings |
| 7 | [Insight](insight.md) | The portfolio team, and leadership | Trends between portfolio snapshots, an application's scores over time, shares of the portfolio, leadership reports, the record as of a day, scenarios, the optional assistant |
| 8 | [The program handbook](handbook.md) | The portfolio team | The first decisions, the roles as a program uses them, the first ninety days, the yearly rhythm of reviews, campaigns, and reports, measures worth watching, and what goes wrong |
| 9 | [Facts from other systems](signals.md) | Administrators who connect other tools, and everyone who reads what they supply | Connectors (end-of-life data, source code hosting, the identity provider), values from other systems and overriding them, applications not on record, push keys and the facts API, catalog files, engineering maturity, signals in the scores |
| 10 | [Running the program](running-the-program.md) | The portfolio team, and administrators | Roles and scope, who sees what, sensitive fields and contracts, shaping the program in the app or with a pack, its versions, what an upgrade does, the dashboard, Home, data quality, portfolio snapshots, scheduled work and email, the history, appearance |
| 11 | [Configuration](configuration.md) | Whoever runs the server | `appwren.toml`, environment overrides, the data home, scheduled work, connector credentials, optional email and single sign-on, the `[branding]` section, PostgreSQL, backup and restore, moving between databases, how large it runs, deployment recipes, `doctor --production`, upgrading, reverse proxies, the demo guard |
| 12 | [API](api.md) | Anyone connecting another system | Sign-in, API tokens and tokens of your own, suggestions, the tool server for AI assistants, the checkpoint, webhooks and their signatures, the CSRF token, responses, errors, lists, and a table of routes |

## Reference

The first two are written from the code, so they always match the version they ship with.

| Reference | What it is |
|---|---|
| [Command reference](cli.md) | Every `appwren` command and option |
| [openapi.json](openapi.json) | The OpenAPI document for the API. A running server also serves it at `/api/openapi.json` |
| [Compatibility](compatibility.md) | What 1.x keeps the same from release to release, what it does not promise, and how something is deprecated. A draft until 1.0.0 |

## Find the answer to a question

| Question | Where |
|---|---|
| How do I try it without setting anything up? | [Explore the demo organization](getting-started.md#explore-the-demo-organization) |
| In what order do I set an organization up? | [Set up the organization](getting-started.md#set-up-the-organization) |
| What must my spreadsheet of units, people, or applications hold? | [Units](getting-started.md#1-units), [People and roles](getting-started.md#2-people-and-roles), [Bring in your applications](getting-started.md#5-bring-in-your-applications) |
| I have added people. How do they sign in? | [How people get in](getting-started.md#2-people-and-roles) |
| Why does every application say *Assess*? | [Fill in what the scores need](getting-started.md#6-fill-in-what-the-scores-need) |
| What do I do before other people sign in? | [Put it in front of other people](getting-started.md#put-it-in-front-of-other-people) |
| Can one team use it on its own, before the rest of the organization? | [Start with one team](getting-started.md#start-with-one-team) |
| Is this an application, or part of one? | [What counts as an application](the-portfolio.md#what-counts-as-an-application) |
| How do I bring in the applications I already have in a spreadsheet? | [Import applications](the-portfolio.md#import-applications) |
| Who answers for an application, and how do I hand it on? | [People named on it](the-portfolio.md#people-named-on-it) |
| What does this application still need before it can go live? | [What each stage requires](the-portfolio.md#what-each-stage-requires) |
| Where does this score come from? | [The working](the-portfolio.md#the-working) |
| Why does it say *Assess* when we know this application well? | [Unknown is not zero](the-portfolio.md#unknown-is-not-zero) |
| Why is research software judged differently? | [Profiles](the-portfolio.md#profiles) |
| Why was it recommended for this? | [Recommendations](the-portfolio.md#recommendations) |
| What does this flag mean? | [Flags](the-portfolio.md#flags) |
| Who may record a decision, and why can I not record this one? | [Decisions](the-portfolio.md#decisions) |
| The decision and the recommendation differ. Is that wrong? | [Mismatches](the-portfolio.md#mismatches) |
| What runs on a technology that is reaching end of support? | [Components and what they are built on](the-portfolio.md#components-and-what-they-are-built-on) |
| Which applications do the same job? | [Capabilities](the-portfolio.md#capabilities) |
| What does this application send, receive, and depend on? | [Interfaces](the-landscape.md#interfaces) |
| Where does this class of data go? | [Follow a class of data](the-landscape.md#follow-a-class-of-data) |
| What breaks if we turn this off? | [What breaks if this goes](the-landscape.md#what-breaks-if-this-goes) |
| What runs in this data center or cloud account? | [Where it runs](the-landscape.md#where-it-runs) |
| What are we paying for twice? | [Overlap](the-landscape.md#overlap) |
| Which capability rests on the weakest software? | [The capability map, measured](the-landscape.md#the-capability-map-measured) |
| What falls out of support next year, and what runs on it? | [Lifecycle](the-landscape.md#lifecycle) |
| Which applications run on a particular release, such as .NET 6? | [Which applications run on a release](the-landscape.md#which-applications-run-on-a-release) |
| How do I avoid typing support dates? | [End-of-life data](signals.md#end-of-life-data), or [support dates from a file](the-landscape.md#support-dates-from-a-file) |
| How do I prepare a portfolio review? | [Portfolio reviews](planning-change.md#portfolio-reviews) |
| What have our decisions committed us to, and when? | [Initiatives and the roadmap](planning-change.md#initiatives-and-the-roadmap) |
| Someone wants a new tool. Do we already have one? | [Requests for something new](planning-change.md#requests-for-something-new) |
| Why can I not move this application to Active? | [Stage gates](planning-change.md#stage-gates) |
| How do we retire an application, and what did it save? | [Retiring an application](planning-change.md#retiring-an-application) |
| Can AppWren read what our repositories, sign-ins, or service desk know? | [Facts from other systems](signals.md) |
| Where did this value come from, and how do I correct it? | [Values from other systems](signals.md#values-from-other-systems) |
| What do people sign in to that is not on record? | [Not on record](signals.md#not-on-record) |
| Which applications have tests and continuous integration? | [Engineering maturity](signals.md#engineering-maturity) |
| Which applications hold health data, and how well are they looked after? | [Who handles a class of data](the-landscape.md#who-handles-a-class-of-data) |
| How do I break an application's cost down? | [What it costs](the-portfolio.md#what-it-costs) |
| Which contracts are about to renew? | [Contracts](the-portfolio.md#contracts) |
| Who can see what an application costs, or its contract? | [Who sees what](running-the-program.md#who-sees-what) |
| The upgrade changed some scores. Why? | [What an upgrade does to the program](running-the-program.md#what-an-upgrade-does-to-the-program) |
| What is waiting on me, and how will I hear? | [What is waiting on you](keeping-current.md#what-is-waiting-on-you) |
| Why has this application's confidence dropped? | [Confirm the record](keeping-current.md#confirm-the-record) |
| How do I ask every owner in a unit to check their records? | [Campaigns](keeping-current.md#campaigns) |
| Where did this task come from? | [Tasks](keeping-current.md#tasks) |
| Someone is leaving. What do they hold? | [When someone leaves](keeping-current.md#when-someone-leaves) |
| How do I find a record, or keep a list as I filtered it? | [Find anything](keeping-current.md#find-anything) |
| This score is wrong. What can I do? | [Contest a score](keeping-current.md#contest-a-score) |
| How do I change the questions, the weights, or the cadence? | [Shape it in the app](running-the-program.md#shape-it-in-the-app) |
| What does a dashboard figure count? | [Read the dashboard](running-the-program.md#read-the-dashboard) |
| Which units' records need the most work? | [Data quality](running-the-program.md#data-quality) |
| How do I keep a record of the portfolio before a review? | [Portfolio snapshots](running-the-program.md#portfolio-snapshots) |
| Who changed this, and when? | [The history](running-the-program.md#the-history) |
| How do I make an identifier in another system a link? | [Links to other systems](running-the-program.md#links-to-other-systems) |
| How do I send notices by email? | [Email](configuration.md#email) |
| How do I let people sign in with Entra ID or another identity provider? | [Single sign-on](configuration.md#single-sign-on) |
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| Nobody can sign in. How do I get back in? | [`appwren users`](cli.md#appwren-users) |

## What this release does not do yet

Version 0.10.0 holds the portfolio, the landscape around it, keeping both current, facts from other systems, planning change, insight over time, the means of adopting and connecting it, and an optional assistant. 1.0.0 follows the maintainer's review, with the [compatibility promise](compatibility.md) in force. Some things are deliberately not scheduled until adopters ask for them: several portfolios run by units within one installation, several organizations in one installation, cloud cost and procurement imports, monitoring checks, and the interface in other languages. The [roadmap](../spec/roadmap.md) says what comes next, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on AppWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
