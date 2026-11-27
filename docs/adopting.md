# Adopting AppWren

This guide is for an organization deciding whether to take up AppWren, and for whoever will lead it there. It says what AppWren asks of you, what to settle before installing anything, and a path from nothing to a running program in about a quarter.

## Is it for you?

AppWren suits an organization that wants to know what applications it runs, who answers for each, and what to do with them, and wants the answers kept true by the people who know them rather than by a central team chasing. It is built for a few hundred to a few thousand applications; the [measurements](configuration.md#how-large-it-runs) go to five thousand.

It is open source under the Apache 2.0 license. It runs on one server, on SQLite for a small team or PostgreSQL for many people at once, and reaches out to nothing an administrator has not switched on.

It is not an asset database for every server and laptop, a ticketing system, or a project tracker. It holds applications and the parts of them worth deciding about, and links to the systems that hold the rest.

## Try it first

The demo organization shows every screen with two years of history, and needs nothing set up:

```bash
uv run appwren demo
uv run appwren --config demo/appwren.toml serve
```

Sign in as any of its sample people from the sign-in page. Spend an hour as the portfolio manager, then as an application owner: the second view is the one that decides whether a program will last. See [Explore the demo organization](getting-started.md#explore-the-demo-organization).

## Before you install anything

| Settle | Because |
|---|---|
| **Who owns the program** | One named person, usually in IT strategy, enterprise architecture, or the CIO's office, who will hold the quarterly reviews and make the leadership reports |
| **What the units are** | Every application belongs to a unit. Take them from the organization chart, two or three levels deep, not deeper |
| **Who decides** | Managers decide anywhere; leaders decide for their units. Nobody decides about an application they answer for |
| **Where it will run** | A server you look after, a container platform, or a virtual machine; PostgreSQL if more than a few dozen people will use it at once. See [Deploy](configuration.md#deploy) |
| **How people will sign in** | Single sign-on with your identity provider is better than passwords: leavers lose access with their account. See [Single sign-on](configuration.md#single-sign-on) |
| **What you already know** | The spreadsheet of applications that every organization has somewhere. It is the first import |

## Weeks 1 and 2: stand it up

1. Install it ([Getting started](getting-started.md)), or start the [container recipe](configuration.md#deploy). Begin from the [starter program](getting-started.md#start-from-a-program-shaped-like-yours) closest to your organization.
2. Connect single sign-on and email, and make it look like yours: your name, logo, colors, and, if you say *department* where AppWren says *unit*, your words ([Appearance](running-the-program.md#appearance)).
3. Add the units and the portfolio team. Give a second person the administrator role.
4. Run `uv run appwren doctor --production` and fix what it says. Set up `appwren backup` to run every night, and restore one backup somewhere else once, to know it works ([Back up and restore](configuration.md#back-up-and-restore)).

## Weeks 2 to 4: make the program yours

Read [Shape the program](running-the-program.md#shape-the-program), then change only what you are sure of: the definition's examples in your organization's words, the tiers' descriptions, the domains, and the fields you will really fill in. Leave the scoring model as it is until you have seen it score your own applications; every factor and weight is described in [the engine](../spec/engine.md), and a change is previewed before it is published.

## Weeks 4 to 6: a pilot with one or two units

Import their applications, name an accountable owner for each, and run a confirmation campaign. Sit with two or three owners while they confirm and assess, and change what confuses them. A pilot that ends with every record confirmed and assessed, and one portfolio review held, is ready to widen.

## Weeks 6 to 12: open the door

Import the rest, a few units at a time, each with its own campaign. Turn on the connectors your organization can use ([Facts from other systems](signals.md)), so that support dates, code activity, and sign-ins arrive without anyone typing them. Hold the first review in each unit that has finished its campaign.

At the end of the first quarter, make a [leadership report](insight.md#leadership-reports). From then on, the [program handbook](handbook.md) describes the rhythm.

## Connecting other systems

- **Reading the portfolio:** issue an [API token](api.md#sign-in-as-another-system) for the system that needs it, with the least role that will do and for reading only.
- **Being told when something happens:** register a [webhook](api.md#be-told-when-something-happens) for decisions, stage changes, and lapses.
- **Facts your own tools know:** a push key lets a script post incidents, tickets, and the like onto records ([Facts from other systems](signals.md)).

## What has been checked, and what has not

AppWren's code has been reviewed against the OWASP Application Security Verification Standard, level 1, and every screen is checked for accessibility on each release; the record is in [the review](../spec/reviews/2026-11-security-and-accessibility.md). The review was of the code, not a penetration test of a deployed installation, and no person has yet used it with a screen reader. An organization with its own security or accessibility team should have them look before relying on it for anything sensitive.

## What AppWren will not do

- It will not decide for you. It recommends, with its working shown; a named person decides, and the decision is kept.
- It will not count what nobody can open. Every figure is the length of a list someone may see.
- It will not send anything anywhere you have not set up: no telemetry, no calls home.
- It will not change its history. Every change is kept, hash-chained, and can be verified with `appwren verify`.
