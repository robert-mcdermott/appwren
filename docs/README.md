# AppWren documentation

These guides describe AppWren 0.1.0. Read them in this order if you are new, or go straight to the one for your part.

## The guides

| | Guide | For | Covers |
|---|---|---|---|
| 1 | [Getting started](getting-started.md) | Whoever installs AppWren | Installing, `init`, `doctor`, `serve`, first sign-in, units and people, bringing in your applications, the demo organization |
| 2 | [The portfolio](the-portfolio.md) | Everyone who keeps, assesses, or reads an application | What counts as an application, the record and its stages, components and technologies, capabilities, assessment, the scores and their working, recommendations, flags, decisions, import and export |
| 3 | [Running the program](running-the-program.md) | The portfolio team, and administrators | Roles and scope, who sees what, sensitive fields, the program and its versions, the dashboard, Home, data quality, portfolio snapshots, the history, appearance |
| 4 | [Configuration](configuration.md) | Whoever runs the server | `appwren.toml`, environment overrides, the data home, optional single sign-on, PostgreSQL, upgrading, reverse proxies, the demo guard |
| 5 | [API](api.md) | Anyone connecting another system | Sign-in, the CSRF token, responses, errors, lists, and a table of routes |

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
| Who can see what an application costs? | [Who sees what](running-the-program.md#who-sees-what) |
| How do I change the questions, the weights, or the rules? | [Shape the program](running-the-program.md#shape-the-program) |
| What does a dashboard figure count? | [Read the dashboard](running-the-program.md#read-the-dashboard) |
| Which units' records need the most work? | [Data quality](running-the-program.md#data-quality) |
| How do I keep a record of the portfolio before a review? | [Portfolio snapshots](running-the-program.md#portfolio-snapshots) |
| Who changed this, and when? | [The history](running-the-program.md#the-history) |
| How do I let people sign in with Entra ID or another identity provider? | [Single sign-on](configuration.md#single-sign-on) |
| How do I move to PostgreSQL? | [Use PostgreSQL](configuration.md#use-postgresql) |
| How do I put it behind a proxy? | [Run behind a reverse proxy](configuration.md#run-behind-a-reverse-proxy) |
| Nobody can sign in. How do I get back in? | [`appwren users`](cli.md#appwren-users) |

## What this release does not do yet

Version 0.1.0 is the portfolio: applications, components, capabilities, technologies, and vendors; assessment, scores with their working, recommendations, flags, and decisions; the dashboard, data quality, import and export. Support dates and costs are entered as figures. Interfaces and data flows, a picture of how applications connect and what breaks if one goes, deployments, costs in lines with contracts and their renewal dates, and end-of-life dates imported from a file arrive in the next release. Notices, reminders, attestation, campaigns, and editing the program in the app follow it, and then read-only connectors to the tools that already know the facts. The [roadmap](../spec/roadmap.md) says what comes next and in what order, and the [changelog](../CHANGELOG.md) lists what is in each release.

## More

- The design behind the product is in [`spec/`](../spec/README.md).
- To work on AppWren itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).
- To report a security problem, see [SECURITY.md](../SECURITY.md).
