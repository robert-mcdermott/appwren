# Changelog

AppWren follows semantic versioning. Each wave of the [roadmap](spec/roadmap.md) is a
release. Before 1.0, a release may contain breaking changes; they are listed under
**Breaking**.

## Unreleased

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

