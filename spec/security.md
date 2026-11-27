# Security

AppWren holds a map of an organization's software: every application, what data it handles, what it runs on, which parts are past vendor support, which are kept by one person, how people sign in to them, and what they cost. Put together, that is a reading list for an attacker and confidential business information. So AppWren's own security is a first-order requirement, not a feature. This document sets out what is protected, from whom, the controls for each threat, and who may do what.

## What is being protected

| Asset | Why it matters |
|---|---|
| **The history** | Its value is that it cannot be quietly changed. A decision or assessment that can be edited is worth nothing to a review board |
| **The inventory taken together** | Where restricted data lives, on which unsupported technology, behind which sign-in method: individually ordinary, together a map of weak points |
| **Sensitive fields** | Costs and contract values, which are often confidential by agreement; security details |
| **Restricted records** | Applications whose existence is itself sensitive |
| **Accounts and sessions** | Whoever holds a manager's session can change the scoring model or record decisions |
| **Program configuration** | Changing a weight, a band, or a rule changes what the portfolio recommends |
| **Connector credentials** (wave 4) | Read access to the organization's code hosting, identity provider, or other sources |
| **Availability** | A portfolio that is down sends people back to spreadsheets |

AppWren is designed **not** to hold the data it describes. Records describe applications and the classes of data they handle; they never contain patient, participant, or other protected data. Forms say so where free text is requested.

## Who might attack, and how they get in

| Actor | Route |
|---|---|
| Someone outside, without an account | The sign-in page and the single sign-on callback |
| A signed-in member | Trying to read sensitive fields or restricted records, or use admin functions |
| An owner of an application | Editing records they are not named on; recording a decision on their own application |
| A steward or leader | Reaching beyond their unit |
| Another website open in a user's browser | Cross-site requests riding the user's session |
| Content a user submitted | Script or markup in a description, a note, a file name, an import, or an uploaded SVG |
| Someone with access to the database or disk | Editing history or reading files directly |
| A compromised source or integration (wave 4 and later) | A connector reading crafted data; a leaked API token or webhook secret |

## Controls, by threat

### Sign-in and sessions

- Sign-in is always required; there is no anonymous mode.
- Passwords are hashed with scrypt from the standard library, with parameters stored beside each hash so the cost can be raised later. Rules follow current guidance: a minimum length of 12, no composition rules, no forced rotation.
- Sign-in is throttled per account and per address, with the counters in the database so the limit holds across workers. Unknown accounts take the same time as known ones.
- Sessions are opaque random tokens in an `HttpOnly`, `SameSite=Strict`, `Secure` cookie. Only a hash is stored. Sessions expire after a period idle and after a maximum age, and are revoked on sign-out, password change, and account disablement.
- The last active administrator can never be removed or demoted, locally or through the identity provider.

### Single sign-on

- OpenID Connect authorization-code flow with PKCE, `state`, and `nonce`. Sign-in state is stored server-side, single-use, short-lived, and tied to the browser that began it.
- The ID token's signature, issuer, audience, expiry, and nonce are all verified before a session is created.
- The client secret is read from the environment and never written to the configuration file or the database.
- Roles mapped from the provider are replaced at each sign-in, so removing someone from a group removes their access at their next sign-in.

### Authorization

- **One policy table.** Every API route names the permission it requires. A route missing from the table is refused, and a test fails if any route lacks an entry.
- **Checked again in the service.** Service functions take the acting principal and check both the permission and the record: scope, the people named on it, and visibility. The API cannot reach data by skipping a check, because the check is where the data is.
- **A role-by-route matrix test** signs in as each role and exercises every route, asserting the expected outcome.
- **Separation of duties.** Nobody records a decision about an application on which they are the accountable owner. The scores are worked out by the system, never typed in, so nobody can raise their own.
- **Administration is not judgment.** The admin role manages accounts and settings. It does not, by itself, allow editing applications or recording decisions; an administrator who also does that work holds a second role, and the history shows which they acted under.

### Sensitive fields

Some fields are useful to everyone who keeps the portfolio and should not be read by everyone who can see the catalog. A field is **sensitive** if the program says so. By default these are sensitive: annual cost (and, from wave 2, cost lines and contract values), and the security details of an application (its sign-in method, backup and restore state, and the data-exposure and end-of-life-exposure factors).

- A sensitive field is visible to the people named on the application, to stewards, leaders, and architects in scope, and to managers, auditors, and administrators. To everyone else it is **withheld**: it is left out of the record, its list column, its filters, its exports, and the working of any score that uses it, and the record says that something is withheld.
- Scores and recommendations are not sensitive, so a member can see that an application is recommended for *Modernize* without seeing what it costs. Where a figure would reveal a sensitive value (the bubble size on the portfolio chart is cost), it is drawn without it.
- One function decides whether a principal may see an application's sensitive fields. Single records, lists, charts, exports, and the working all call it.

### Cross-site requests and content

- Every state-changing request needs a per-session CSRF token in a header, and requests whose origin does not match the host are refused.
- The content security policy is `default-src 'self'` with no inline script or style and no third-party origins. Frames are denied.
- The front end inserts data only as text nodes. No user-supplied value is ever parsed as HTML.
- The generated theme stylesheet is built only from values that have passed strict validation.
- An imported spreadsheet is read as data, never as formulas. Values in an exported CSV that a spreadsheet program would treat as a formula are prefixed so that they are shown as text.

### Files

- Uploads have a size limit and an allowlist of types, checked by content, not by name.
- Files are stored by hash outside any served directory and are only ever returned through a route that checks access.
- Downloads are always sent as attachments with a policy of `default-src 'none'; sandbox` and sniffing off.
- Uploaded logos are sanitized and served from a route with its own locked-down policy.

### The history

- Events are append-only in the application, and triggers in the database refuse updates and deletes on the event table. `appwren doctor` reports a missing trigger.
- Each event is hashed together with the previous event's hash. `appwren verify` recomputes the chain and reports the first break. The latest hash can be exported on a schedule and kept elsewhere, so that even rewriting the whole chain is detectable.
- Exports of lists that include sensitive fields are themselves events.

### Connectors (wave 4)

- Off until an administrator enables each one ([ADR-0003](decisions/0003-quiet-by-default.md)). Their credentials come only from the environment.
- Read-only. Each connector's documentation states the least access it needs.
- What a connector reads is treated as untrusted input: validated against the field it fills, limited in size, and never interpreted as markup or instructions.
- A connector supplies facts, never judgments, and a person's override of a value always wins.

### Integrations (wave 7 and later)

- API tokens are scoped to a role and optionally to read-only, shown once, stored as hashes, and expire.
- Webhooks are signed, sent only to addresses an administrator registered, and carry references rather than record contents by default.

### Operations

- Secrets come only from the environment.
- No request bodies, form answers, or tokens are written to logs.
- `appwren doctor --production` (wave 7) checks the things that matter before going live: TLS in front, secure cookies in effect, a current schema, a recent backup, mail and single sign-on reachable, and no default or demo accounts present.
- The demo organization is built only by an explicit command into its own data home, marks itself as a demo on every page, and its server refuses to listen on anything but the local machine unless told otherwise.

## Who can see and do what

### Visibility

**The catalog is open.** Applications, capabilities, technologies, and vendors are visible to everyone signed in, apart from their sensitive fields. A portfolio is useful in proportion to how many people can find what already exists: a researcher looking for an approved tool, an engineer checking who else uses a database, a team about to buy something another department already has. An application can be marked **restricted**, which limits even its existence to the people named on it, stewards and leaders of its unit, architects and managers in scope, auditors, and administrators.

A record that joins applications, such as an interface, is visible only to those who may see every application it joins: a restricted application's interfaces are hidden with it, even from someone who keeps the other end.

One function per record type decides what a principal may see. Single records, lists, counts, charts, searches, and exports all call it, so they always agree.

### Permissions

"Named" means named on the application in any role. "In scope" means the application's unit is the grant's unit or beneath it.

| Capability | Member | Named on the application | Steward (in scope) | Leader (in scope) | Architect (in scope) | Manager | Auditor | Admin |
|---|---|---|---|---|---|---|---|---|
| Read the catalog (unless restricted) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read scores, recommendations, and decisions | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Read sensitive fields | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Add an application in a unit | | | ✓ | | ✓ | ✓ | | |
| Edit an application; its components and deployments; its links, capabilities, and people in roles | | ✓ | ✓ | | ✓ | ✓ | | |
| Assess an application | | ✓ | ✓ | | ✓ | ✓ | | |
| Change who is accountable | | ✓ (the accountable owner) | ✓ | ✓ | | ✓ | | |
| Record a decision | | | | ✓ (not as its accountable owner) | | ✓ (not as its accountable owner) | | |
| Add and edit an interface between two applications | | ✓ (named on either) | ✓ (either in scope) | | ✓ (either in scope) | ✓ | | |
| Add and edit capabilities, technologies and their releases, vendors, and hosting platforms | | | | | ✓ | ✓ | | |
| Import applications from a spreadsheet, each row as if added by hand | | | ✓ | | ✓ | ✓ | | |
| Export a list they can see, as CSV or JSON | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Take a portfolio snapshot | | | | | | ✓ | | |
| Read the full history | | | | | | ✓ | ✓ | ✓ |
| Edit vocabularies, fields, the questionnaire, the scoring model, and cadences | | | | | | ✓ | | ✓ |
| Manage accounts, roles, units, branding, connectors, and system settings | | | | | | | | ✓ |

## Review

- **Each wave:** the role-by-route matrix, the sensitive-field tests, the web safety tests (no inline script or style, no third-party origins, no HTML parsing of data), and dependency review are part of the definition of done.
- **Wave 7:** a full review against the OWASP Application Security Verification Standard, level 1, with findings and their resolution recorded in `spec/reviews/`.
- **Before 1.0:** the review is repeated, and a second person who did not write the code walks the threat table above.

Vulnerabilities are reported privately as described in `SECURITY.md`.
