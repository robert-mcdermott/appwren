# ADR-0013: Applications, components, and deployments are different records

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The most common mistake in an application inventory is not agreeing on what an application is. One team registers "the grants system". Another registers its database server, its reporting module, and its nightly export as three applications. A third registers the vendor's product name. Scores and dispositions then compare things of different kinds, duplicates hide behind different names, and nobody can say how many applications the organization has.

## Decision

AppWren keeps three levels apart:

- **Application:** the logical thing people name, own, use, and make decisions about ("Grant management"). It is the unit of the portfolio: it has the accountable owner, the users, the capabilities, the cost, the scores, and the disposition.
- **Component:** a part of an application that is built, bought, or maintained on its own: a service, a web front end, a database, a batch job, an integration, a report, or a module. Components carry the technical detail: technologies and versions, the repository, the hosting. A large application that serves very different purposes is decomposed into components so that each part's technology can be judged on its own.
- **Deployment** (wave 2): a running instance of an application or component in an environment (production, test, development, recovery), on a hosting platform.

The portfolio is counted, scored, and decided in applications. Technical health draws on the components: an application's technology currency is the worst of its components'.

A short definition of an application, with examples of what is and is not one, is part of the default program and shown wherever a new application is added.

## Consequences

- One definition across the organization, and comparable scores.
- Infrastructure detail stays out of the portfolio. Deployments describe where an application runs, not the servers' configuration, which belongs to whatever system the organization already uses for that, linked by reference.
- Small applications may have a single component, or none: a software-as-a-service product often has no components the organization maintains, and its technical health is judged on the vendor and its configuration instead.

## Alternatives

- **One flat record type:** simple, and the cause of the problem described above.
- **A full configuration-management model:** precise, and a different product. AppWren links to such a system by reference rather than duplicating it.
