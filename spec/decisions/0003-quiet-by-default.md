# ADR-0003: Quiet by default, with connectors an administrator turns on

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

An application portfolio goes stale because the people who own it have other work. The record is only kept current if keeping it current is cheap. Much of what a portfolio needs to know already exists somewhere else, and is more accurate there than in anyone's memory: when code was last changed and by how many people, which version of a database a component runs on and when that version stops being supported, how many people signed in to an application last month, how many incidents it had, what it cost.

There are two ways to get that information. Other systems can **push** it: a script or pipeline the organization runs posts facts to the API. Or the portfolio can **pull** it: it holds a credential to another system and reads from it on a schedule.

Pulling gives the freshest data for the least effort, which matters more for a portfolio than for most records. It also means holding credentials to other systems, maintaining a connector for each one as those systems change, and a longer security review before the product can be deployed. A system that holds a map of every application, its owners, its data, and its weak points, *and* credentials to the systems around it, is an attractive target.

## Decision

AppWren is **quiet by default**: a fresh installation makes no outbound connection except to the mail server and identity provider an administrator configures. Everything it knows comes from people, from imported files, and from what other systems choose to push to it.

From wave 4, an administrator may also turn on **connectors**, one at a time. A connector is a small, named, read-only reader for one kind of source. It is held to these rules:

- **Off until turned on.** Each connector is enabled separately, for a named source, by an administrator. Nothing is enabled by default, and an installation that never enables one never makes the connection.
- **Read-only, least privilege.** A connector only reads. Its documentation says exactly what access it needs, and its credential comes from the environment, never the configuration file or the database.
- **Facts, not judgments.** A connector supplies facts (a date, a count, a version) for named fields. It never assesses, decides, or changes an owner, a lifecycle stage, or a disposition.
- **Sourced and labelled.** Every value a connector supplies is stored with its source and the time it was read, shown as such, and recorded in the history like any other change. A person can override a value with a reason; the override wins until they remove it.
- **Bounded.** Each run has a time limit and a record of what it read, changed, and failed to match. A connector that fails stops writing and says so on the operations page; it never leaves partial values without saying which.

The same facts can always be supplied by push, through the API or an import file, for organizations that prefer to run their own collection.

## Consequences

- AppWren can be deployed with no access to anything else, and approved quickly.
- An organization that wants fresher data can have it without writing code, and can see exactly what each connector does.
- Each connector is a maintenance commitment, so they are added only for sources that most adopters have and that feed a score: source code hosting, end-of-life data, the identity provider, and a generic push format for everything else.
- Connector-supplied fields still count toward data confidence only while fresh, by the same rule as anything else.

## Alternatives

- **Strictly push-only:** simplest and safest, but every adopter would have to write the same scripts, and the portfolio would go stale in exactly the organizations with the least time.
- **Discovery as a core feature,** scanning networks, cloud accounts, or devices to find applications: a different and much larger product, with standing credentials to the organization's most sensitive systems. Not done; see the roadmap's *Never* list.
