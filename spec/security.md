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
- Sign-in is throttled per account and per address, with the counters in the database so the limit holds across workers. The per-address limit applies to addresses off this machine, so behind a proxy whose forwarded address is not believed (`[server] trusted_proxies`) every sign-in looks local and only the per-account limits hold. A right password clears the account's count, and takes back only its own attempt from the address's, so someone with an account cannot clear their address between guesses at others. Unknown accounts take the same time as known ones.
- Changing one's own password needs the current one, and wrong guesses at it are limited as at sign-in. Someone with no password here (who signs in through the identity provider) cannot give themselves one; an administrator gives one where it is wanted.
- Sessions are opaque random tokens in an `HttpOnly`, `SameSite=Strict` cookie, marked `Secure` whenever the request arrived over https, directly or by `X-Forwarded-Proto`. Only a hash is stored. Sessions expire after a period idle and after a maximum age, and are revoked on sign-out, password change, and account disablement, which also revoke the person's own tokens.
- The last active administrator can never be removed or demoted, locally or through the identity provider.

### Single sign-on

- OpenID Connect authorization-code flow with PKCE, `state`, and `nonce`. Sign-in state is stored server-side, single-use, short-lived, and tied to the browser that began it.
- The ID token's signature, issuer, audience, expiry, and nonce are all verified before a session is created.
- The client secret is read from the environment and never written to the configuration file or the database.
- Roles mapped from the provider are replaced at each single sign-on, so removing someone from a group removes their access at their next sign-in. When the provider says the roles claim was too long to send, the roles are left as they were and the server logs it. A password sign-in does not consult the provider: an account an administrator has given a password keeps its provider roles until its next single sign-on, which is one reason to set `local_sign_in = false` once single sign-on is in use.

### Authorization

- **One policy table.** Every API route names the permission it requires. A route missing from the table is refused, and a test fails if any route lacks an entry.
- **Checked again in the service.** Service functions take the acting principal and check both the permission and the record: scope, the people named on it, and visibility. The API cannot reach data by skipping a check, because the check is where the data is. A record kept by whoever keeps its application (a component, a deployment, an interface) is checked against the application it is moved to as well as the one it was on, and a contract is said to cover only applications its editor keeps.
- **A role-by-route matrix test** signs in as each role and exercises every route, asserting the expected outcome.
- **Separation of duties.** Nobody records a decision about an application on which they are the accountable owner. The scores are worked out by the system, never typed in, so nobody can raise their own.
- **Administration is not judgment.** The admin role manages accounts and settings. It does not, by itself, allow editing applications or recording decisions; an administrator who also does that work holds a second role. The history records the person who acted, not the role they acted under.

### Sensitive fields

Some fields are useful to everyone who keeps the portfolio and should not be read by everyone who can see the catalog. A field is **sensitive** if the program says so. By default these are sensitive: annual cost (and, from wave 2, cost lines and contract values), and the security details of an application (its sign-in method, backup and restore state, and the data-exposure and end-of-life-exposure factors).

- A sensitive field is visible to the people named on the application, to stewards, leaders, and architects in scope, and to managers, auditors, and administrators. To everyone else it is **withheld**: it is left out of the record, its list column, its filters, its exports, and the working of any score that uses it, and the record says that something is withheld.
- Cost lines, and the figures worked out from cost (cost per user, license use), are withheld with annual cost. A contract is sensitive as a whole: it is visible to those who see every application's sensitive fields, to anyone who may see the sensitive fields of an application it covers, and to whoever made or owns it. Totals of cost across applications are shown only to those who see every application's cost, since a part would reveal the rest.
- Scores and recommendations are not sensitive, so a member can see that an application is recommended for *Modernize* without seeing what it costs. Where a figure would reveal a sensitive value (the bubble size on the portfolio chart is cost), it is drawn without it.
- A list may be narrowed by a sensitive field, whether by a column or by another filter that reads it (data classes, who uses it), only among the applications whose sensitive fields the person sees. The portfolio's rows, the data-handling report, *what breaks if this goes*, the checkpoint, and the assistant withhold a sensitive field as the record does.
- **Flags** are not sensitive in themselves, but a flag whose condition reads a sensitive field (*restricted data on unsupported technology* reads the data classes) is not named to someone who may not see that field, and neither are the two that tell a covering contract's terms (*no data agreement*, *notice date near*): not on the record, in lists, in the portfolio's rows, in a kept score, or in a scenario's risks. They are still counted in figures for the whole portfolio.
- The stage of an application is never sensitive: every list, gate, and figure is organized by it.
- One function decides whether a principal may see an application's sensitive fields. Single records, lists, charts, exports, and the working all call it.

### Cross-site requests and content

- Every state-changing request needs a per-session CSRF token in a header, and requests whose origin does not match the host are refused.
- The content security policy is `default-src 'self'` with no inline script or style and no third-party origins. Frames are denied.
- The front end inserts data only as text nodes. No user-supplied value is ever parsed as HTML.
- The generated theme stylesheet is built only from values that have passed strict validation.
- An imported spreadsheet is read as data, never as formulas. Values in an exported CSV that a spreadsheet program would treat as a formula are prefixed so that they are shown as text.

### Files

- Uploads have a size limit and an allowlist of types, checked by content, not by name.
- Files are stored by hash in the data home, outside any served directory, and returned only through a route. The brand's images and the theme stylesheet are public, since the sign-in page shows them; nothing else is.
- Exports and catalog files are sent as attachments, with sniffing off and no caching, under the app's own content security policy.
- Uploaded logos are sanitized to drawing by an allow-list and served from a route with its own policy, `default-src 'none'; sandbox`.

### The history

- Events are append-only in the application, and triggers in the database refuse updates and deletes on the event table. `appwren doctor` reports a missing trigger.
- Each event is hashed together with the previous event's hash. `appwren verify` recomputes the chain, reports the first break, and prints the latest hash. Kept somewhere else, by a scheduled task of the organization's own, that hash makes even a rewrite of the whole chain detectable; AppWren does not keep or compare it itself.
- Exports of lists that include sensitive fields are themselves events.
- The assistant's exchanges are events when they are made, answered, and removed, but the words (what was asked, what came back, and what a server said when it refused) are kept only in the exchange itself, never in an event. Removing an exchange after `keep_days` removes the words; that it happened, who asked, and for what stays.

### Connectors (wave 4)

- Off until an administrator enables each one ([ADR-0003](decisions/0003-quiet-by-default.md)). Their credentials come only from the environment.
- Read-only. Each connector's documentation states the least access it needs.
- What a connector reads is treated as untrusted input: validated against the field it fills, limited in size, and never interpreted as markup or instructions.
- A connector supplies facts, never judgments, and a person's override of a value always wins.
- A connector, or a standing elsewhere, may never be given one of the server's own variables as its credential: its configuration, database, sign-in, and mail secrets, the assistant's key, and any AWS credential. They are sent to the host an administrator names, which could be anywhere.

### Integrations (wave 7 and later)

- API tokens an administrator issues are scoped to a role, read-only unless made otherwise, shown once, stored as hashes, expire, and never administer.
- Webhooks are signed, sent only to https addresses on the public internet that an administrator registered, and carry references rather than record contents.
- **Tokens of one's own** (0.8.0) act as their owner and can read and propose, nothing else: the middleware lets them reach only the suggestion route to write. They never administer, and they end with a password change or a disabled account.
- **Suggestions** change nothing until someone who keeps the application accepts one, signed in, as their own edit. A person has at most ten waiting on an application, however many tokens they use, and a value is at most 4,000 characters. Nobody proposes a field withheld from them.
- **The checkpoint** answers about an application only to someone who may see it; a restricted one is answered as if there were none. It withholds what the record withholds.
- **The tool server** runs beside an assistant, on the person's machine, with their own token. It follows no redirect and quotes every reference it puts in an address.
- **The assistant** is off until configured. It is told only the applications the person asking may see, leaving out any that handle data above `max_data_class` and any field withheld from them; what it is told is sent to the configured model server.
  - **Its server** speaks one of three protocols (chat completions, messages, Bedrock's Converse API) over https, or plain http only on the same machine, and no redirect is followed. Its key comes only from the environment, from a variable that may not be one of the server's own secrets. On Bedrock it is an Amazon Bedrock API key, or the AWS access keys in the environment sign each request; the secret is never sent. Extra headers for a gateway are refused when they are named like a credential or are ones AppWren sends itself; that check is by name, so the configuration's author is trusted not to put a key in a value.
  - **Who may ask, and how often.** The configuration may open it to some roles only; administrators always may, and a token never may. Each person may ask `daily_limit` times a day, and may have one question waiting on the server at a time, so nobody can tie up the threads that answer everyone else: a place for each question is kept, and counted, before the server is asked.
  - **What it says back.** When the server refuses, the person is told only that it did, and its status. What the server gave as its reason (which may name an account, a role, or part of a key) is kept with the exchange for those who read everything, and shown by `appwren doctor --assistant`.
  - **How long.** Exchanges are kept for `keep_days` (a year unless set), whether or not the assistant is on now, and are readable only by those who read everything.
- **Standings** are read only from an address an administrator sets, with a key from an environment variable the server does not use for itself; an identifier that would climb the address's path is not used.

### Kept scores (0.10.0)

- Each server process keeps the day's scores between changes, for each database. What is kept never depends on who asked: scores are worked out without a person, and what a person may not see (a sensitive field in the working, a withheld flag, a primary provider they may not see) is taken out as each answer is made, from a copy, every time.
- They are good only as long as a counter stands still, which every write to a table a score could read bumps in the same transaction (`appwren.db.changes`), so a write that is rolled back takes its bump back. Only the history, references, and a restore into an empty database write around the session, and none of them writes a table scores read; any new code that did would be caught by the check the test suite runs under, which works every reused score out again. A new day and a new scoring model are part of the key.
- Scores are kept only from a session that reads. On PostgreSQL such a session sees one moment of the database throughout (repeatable read), as SQLite's do, so what is kept is never a mix of before and after a change.

### Operations

- Secrets come only from the environment.
- No request bodies, form answers, or tokens are written to logs; a database error is logged without its statement's parameters.
- `appwren doctor --production` (wave 7) checks the things that matter before going live: an https `base_url` (which is what puts `Secure` on the cookie), PostgreSQL, a current schema, a recent backup, two administrators, scheduled work running, the data home's permissions, mail and single sign-on set up, and that it is not the demo. There are no default accounts to check for.
- The demo organization is built only by an explicit command into its own data home, marks itself as a demo on every page, and its server refuses to listen on anything but the local machine unless told otherwise.

## Who can see and do what

### Visibility

**The catalog is open.** Applications, capabilities, technologies, and vendors are visible to everyone signed in, apart from their sensitive fields. A portfolio is useful in proportion to how many people can find what already exists: a researcher looking for an approved tool, an engineer checking who else uses a database, a team about to buy something another department already has. An application can be marked **restricted**, which limits even its existence to the people named on it, whoever added it, stewards and leaders of its unit, architects and managers in scope, auditors, and administrators. An import of applications looks only among those the importer may see.

A record that joins applications, such as an interface, is visible only to those who may see every application it joins: a restricted application's interfaces are hidden with it, even from someone who keeps the other end.

An application's scores name the primary provider it overlaps with only to someone who may see that provider; to anyone else it is *an application you may not see*.

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
| Change who is accountable | | ✓ (the accountable owner) | ✓ | | ✓ | ✓ | | |
| Record a decision | | | | ✓ (not as its accountable owner, unless the program allows it, when it is marked) | | ✓ (the same) | | |
| Read and set an application's cost lines | | ✓ | ✓ | read only | ✓ | ✓ | read only | read only |
| Read a contract that covers an application | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Add a contract | | | ✓ | | ✓ | ✓ | | |
| Edit a contract they made or own, or that covers an application they are named on or keep; say it covers only applications they keep | | ✓ | ✓ | | ✓ | ✓ | | |
| Add and edit funding sources | | | | | ✓ | ✓ | | |
| Add and edit an interface between two applications | | ✓ (named on either) | ✓ (either in scope) | | ✓ (either in scope) | ✓ | | |
| Add and edit capabilities, technologies and their releases, vendors, and hosting platforms | | | | | ✓ | ✓ | | |
| Import applications from a spreadsheet, each row as if added by hand | | | ✓ | | ✓ | ✓ | | |
| Export a list they can see, as CSV or JSON | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Confirm an application's record | | ✓ | ✓ | | | ✓ | | |
| Contest a factor of an application's scores | | ✓ | ✓ | | ✓ | ✓ | | |
| Answer a contest | | | | | ✓ | ✓ | | |
| Run a campaign over a unit | | | ✓ | | | ✓ | | |
| Close a task they are given, or one in their scope | ✓ (their own) | ✓ (their own) | ✓ | | | ✓ | | |
| Pass on everything a person holds | | | | | | ✓ (whole organization) | | ✓ |
| Take a portfolio snapshot | | | | | | ✓ | | |
| Read the full history | | | | | | ✓ | ✓ | ✓ |
| Edit vocabularies, fields, the questionnaire, the scoring model, and cadences | | | | | | ✓ | | ✓ |
| Manage accounts, roles, units, branding, scheduled work, email, connectors, and system settings | | | | | | | | ✓ |

## Review

- **Each wave:** the role-by-route matrix, the sensitive-field tests, the web safety tests (no inline script or style, no third-party origins, no HTML parsing of data), and dependency review are part of the definition of done.
- **Wave 7:** a full review against the OWASP Application Security Verification Standard, level 1, with findings and their resolution recorded in `spec/reviews/`.
- **Before 1.0:** the review is repeated, and a second reviewer who did not write the code walks the threat table above. Done for 0.9.0; recorded in `spec/reviews/`.
- **Wave 10:** the code added for 0.10.0 walked against this table by a reviewer who did not write it; recorded in `spec/reviews/`.

Vulnerabilities are reported privately as described in `SECURITY.md`.
