# AppWren documentation

These guides describe AppWren 0.5.0, and are published with pictures at <https://robert-mcdermott.github.io/appwren/>. Read them in this order if you are new, or go straight to the one for your part.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Getting started](getting-started.md) | Whoever installs AppWren | Installing, `init`, `doctor`, `serve`, first sign-in, units and people, starting with one team, bringing in your applications, the demo organization |
| 2 | [The portfolio](the-portfolio.md) | Everyone who keeps, assesses, or reads an application | What counts as an application, the record and its stages, components and technologies, capabilities, assessment, the scores and their working, recommendations, flags, decisions, cost lines, funding, contracts, import and export |
| 3 | [The landscape](the-landscape.md) | Architects, the portfolio team, and anyone asking what an application touches | Interfaces and data flows, the picture of how a record is connected, what breaks if an application goes, hosting platforms and deployments, overlap, the capability map and its measures, the lifecycle timeline, the radar, support dates from a file, who handles a class of data |
| 4 | [Keeping current](keeping-current.md) | Everyone who keeps an application, and the portfolio team | Home and the bell, reminders, email, confirming a record and what a stale one costs, campaigns, tasks raised by what happens, passing on what someone holds, search and saved views, likely duplicates, contesting a score |
| 5 | [Planning change](planning-change.md) | The people who decide what happens to applications, and those who carry it out | Portfolio reviews and their agendas, initiatives and the roadmap, requests for something new, stage gates, the retirement playbook and savings |
| 6 | [Insight](insight.md) | The portfolio team, and leadership | Trends between portfolio snapshots, an application's scores over time, shares of the portfolio, leadership reports |
| 7 | [Facts from other systems](signals.md) | Administrators who connect other tools, and everyone who reads what they supply | Connectors (end-of-life data, source code hosting, the identity provider), values from other systems and overriding them, applications not on record, push keys and the facts API, catalog files, engineering maturity, signals in the scores |
| 8 | [Running the program](running-the-program.md) | The portfolio team, and administrators | Roles and scope, who sees what, sensitive fields and contracts, shaping the program in the app or with a pack, its versions, what an upgrade does, the dashboard, Home, data quality, portfolio snapshots, scheduled work and email, the history, appearance |
| 9 | [Configuration](configuration.md) | Whoever runs the server | `appwren.toml`, environment overrides, the data home, scheduled work, connector credentials, optional email and single sign-on, PostgreSQL, upgrading, reverse proxies, the demo guard |
| 10 | [API](api.md) | Anyone connecting another system | Sign-in, the CSRF token, responses, errors, lists, and a table of routes |

## Reference

These two are written from the code, so they always match the version they ship with.

| Reference | What it is |
|---|---|
| [Command reference](cli.md) | Every `appwren` command and option |
| [openapi.json](openapi.json) | The OpenAPI document for the API. A running server also serves it at `/api/openapi.json` |

## Find the answer to a question

| Question | Where |
|---|---|
| How do I try it without setting anything up? | [Explore the demo organization](getting-started.md#explore-the-demo-organization) |
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

Version 0.3.0 is the portfolio, the landscape around it, and the means of keeping both current. Every fact in it is still typed or imported by a person. Read-only connectors to the tools that already know the facts (code hosting, public end-of-life data, the identity provider, and catalog files kept in repositories) come next, each turned on by an administrator, with each fact's source shown beside it, so that fewer are typed. After that come review cycles, initiatives, intake of new requests, and the retirement playbook. The [roadmap](../spec/roadmap.md) says what comes next and in what order, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on AppWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
