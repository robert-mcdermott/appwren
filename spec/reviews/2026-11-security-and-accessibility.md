# Security and accessibility review, November 2026

Done in wave 7, before version 0.7.0, against the code on the `wave-7` branch; for the code wave 8 added, before 0.8.0; and in wave 9, before 0.9.0, when a second reviewer walked the threat table in [security.md](../security.md) against the whole of the code.

This is a record of what was looked at, how, what was found, and what was done about it. It also says plainly what was not done, so that nobody reads more into it than is there.

## Security

### How it was done

A reviewer who had taken no part in writing the code read it against the areas of the OWASP Application Security Verification Standard 4.0, level 1, with one brief: find concrete weaknesses, confirm each by tracing the code path, and report nothing speculative. Each finding was confirmed with a test run against the application's own fixtures. The areas:

- Authentication, password storage, and limits on sign-in attempts
- Session management, cookies, and request forgery
- Single sign-on, and the redirect after sign-in
- Access control: the policy table, restricted applications, sensitive fields, and reaching a record by a side route
- API tokens, push keys, and webhooks, which are new or recent
- Injection: SQL, markup and script, and formulas in CSV exports
- Uploads and the configuration file's branding: images, SVG, colors, fonts, links
- Requests the server makes: webhooks, connectors, the identity provider
- Backup, restore, and moving between databases
- Secrets, and what the history and the log keep
- Security headers, the content security policy, static files, and the size of requests
- The newest reports: trends, shares, leadership reports, as of a day, and scenarios

### What was found, and what was done

| # | Finding | Severity | Since | Fix |
|---|---|---|---|---|
| 1 | An API token, which has no account, was taken for the maker of every record made at the command line, and the owner of every contract with none. A member's token could list restricted applications in other units, export them, and read contract values | Medium | this wave | A token matches no one's records by its missing account. Lists, exports, and contracts apply the same rules to a token as to its role |
| 2 | A restricted application's name and reference could be read through another record: as the successor of one in view, by trying references one by one in a reference field and reading the answer or the history, in the message refusing a second primary provider of a capability, and as the application a scenario consolidates into | Medium | 0.1.0 to this wave | A reference to an application the person may not see is answered as if there were none. Chips, messages, the history, and as of a day say *an application you may not see* instead of naming it |
| 3 | An administrator could give a connector one of the server's own variables as its credential, such as the single sign-on secret, the mail password, or the database's password, and send it to a host of their choosing | Low | 0.4.0 | A connector may never use a variable the server reads for itself, nor any the configuration names for its secrets; this is checked when it is saved and again when it runs |
| 4 | A request that did not declare its length was read in full before the 32 MB limit applied | Low | 0.1.0 | Bytes are counted as they arrive, and the request is refused at the limit |
| 5 | Wrong passwords for one account, spread over enough addresses, locked its owner out everywhere for fifteen minutes | Low | 0.1.0 | When an account is past its limit, an address that has not failed for it still gets one try, so the owner can sign in; addresses that have failed get none |
| 6 | A webhook could be pointed at this machine by name or by address | Low | this wave | Only an https address on the public internet is accepted, and this machine is refused by name and by address when the webhook is added and when a delivery is made |

Each fix has a test that fails without it.

### Looked at and found sound

The policy table, which refuses any route it does not list. Sessions: random tokens kept as hashes, `HttpOnly`, `SameSite=Strict`, and `Secure` over https, with idle and absolute expiry, and other sessions ended when a password changes. The forgery token, compared in constant time, with the origin checks. Passwords: scrypt, a dummy hash for unknown accounts, twelve characters at least, the current one needed to change your own. Single sign-on: PKCE, a single-use state bound to the browser, a nonce, RS256 only, and the issuer, audience, and time checks. The redirect after sign-in, on the server and in the page. The demo's sign-in, which needs the demo marker and a local client. API tokens kept as hashes, never for an administrator, reading enforced for every change. Push keys, kept as hashes and taken only at their one route. Webhook signatures, and payloads that leave restricted names out. What the history redacts: password and token hashes, webhook secrets, push key digests. Backup files written for their owner only, restore only into an empty database, with paths kept inside the data home and the history verified. Branding: SVG cleaned to drawing by an allow-list, images judged by content and served sandboxed, the theme built only from checked colors, links limited to https, http, and mail. Headers: a strict content security policy with no inline script, no framing, no sniffing. Static files kept inside the web root. Imports and exports: CSV formulas guarded, YAML read safely, rights checked. Trends, shares, as of a day, and reports filter by visibility and withhold cost; leadership reports are for those who may see everything. The pages never write markup from data.

### Left as it is, on purpose

- **A webhook's address is resolved just before it is used.** A name whose answer changes between the check and the connection (DNS rebinding) could still reach an internal address. Only an administrator registers webhooks, and the shipped recipes run AppWren unprivileged.
- **A connector may reach a host inside the network.** A code host or identity provider run inside the organization is a reason to turn a connector on. The credential it sends is one given to it alone (finding 3).
- **Behind a proxy whose forwarded address is not believed, every sign-in comes from one address**, and the per-address limits become per-account limits. Set `[server] trusted_proxies` to the proxy, as the deployment guide says.
- **The API description is public.** `/api/openapi.json` describes the routes and holds nothing about an installation.

### What this was not

It was a review of the code by one reviewer. It was not a penetration test of a deployed installation, and no outside firm has examined AppWren. An organization with its own security team should have that team look before it relies on AppWren for anything sensitive.

### Wave 8: the code added for 0.8.0

The same reviewer's brief, applied to everything added between 0.7.0 and 0.8.0: the checkpoint, tokens of one's own, suggestions, the tool server, the assistant, and standings elsewhere. Each finding was confirmed with a test.

| # | Finding | Severity | Fix |
|---|---|---|---|
| A | A token of one's own outlived a password change, so one made with a stolen session kept working after the owner changed their password | Medium | A new password, or a disabled account, revokes the account's own tokens along with its sessions |
| B | The checkpoint and the assistant told fields the program had marked sensitive (the data an application handles, its stage, its tier) to people who may not see them | Low | Both leave out, and do not answer from, what the person may not see |
| C | A proposed value had no size limit, and one person could take every waiting slot on an application | Low | A value is at most 4,000 characters, and one person may have ten proposals waiting on an application |
| D | An identifier of `..` in another system could climb the standing address's path, carrying its key elsewhere on that host | Low | Such an identifier is not put into an address |
| E | An administrator's own token could read the administration pages | Informational | A token never administers, whoever's it is |

Found sound: the checkpoint's hiding of restricted applications, the limit on what a token of one's own may change, who may accept a proposal, what the assistant is told and who may read its exchanges, who may say where a standing is read, and the pages that show all of it.

### Wave 9: the threat table walked again

A second reviewer, who had taken no part in writing the code or the first review, took every control `spec/security.md` claims and traced it to the code that implements it, then looked for concrete weaknesses the table's threats point at, with the newest code (who uses an application, and everything 0.8.0 added) first. Each finding was confirmed with a test, and each test is now in `tests/test_review_wave9.py`, where it failed before its fix.

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | Someone who signs in through the identity provider, and so has no password here, could give themselves one without any current password, and then sign in around the provider, past its second factor and its offboarding, keeping the roles it had given them | Medium | Nobody gives themselves a first password; an administrator gives one where it is wanted |
| 2 | An edit was checked against the application a record belonged to before the edit, never the one it was moved to. Whoever kept one application could move a component or deployment onto another unit's application, point an interface between two applications they did not keep, or say their own contract covered another unit's application, changing its flags and scores under their own name | Medium | A component, deployment, or interface is checked against the application it is moved to as well; a contract is said to cover, or to stop covering, only applications its editor keeps |
| 3 | A field the program marks sensitive (one it does not ship marked) was withheld on the record and its list column, but could still be narrowed by in the other filters (data class, who uses it), and was still told in the portfolio's rows, the data-handling report, *what breaks if this goes*, and by flags whose condition reads it. Finding B of the wave 8 review was incomplete | Low | Narrowing by a sensitive field matches only applications whose sensitive fields the person sees; those places withhold it; a flag that reads it is not named. The stage can no longer be marked sensitive: every list, gate, and figure is organized by it |
| 4 | Two flags, *no data agreement* and *notice date near*, told everyone who could see an application the terms of a contract they could not see | Low | Named only to those who see the application's sensitive fields; still counted in figures for the whole portfolio |
| 5 | A right password cleared the count of failed sign-ins for the address it came from, so someone with an account of their own could guess at everyone else's from one address without end | Low | A right password takes back only its own attempt from the address's count |
| 6 | Whoever held a session could guess the current password at *change your password* without limit, and then change it | Low | Wrong guesses there are limited as at sign-in |
| 7 | A dry-run import told a steward that a restricted application they may not see had a given name, and its reference | Low | An import looks only among the applications the importer may see |
| 8 | A database error was logged with its statement's parameters: what someone had typed, or a new password's hash | Low | Errors are logged without parameters |
| 9 | One person with several tokens of their own could take every slot for proposals on an application. Finding C of the wave 8 review was incomplete | Low | Proposals are counted by the person, whatever token they came by |

Left as it is, on purpose:

- **An import with an explicit reference** answers differently for a reference that is on record, hidden or not, than for one that is free. References are numbers given in order, so that one is taken says nothing about what holds it.
- **A password sign-in leaves provider roles as they are** for an account an administrator has given a password, until its next single sign-on. Set `[sso] local_sign_in = false` once single sign-on is in use.
- **Flags are counted** in figures for the whole portfolio (how many applications carry each) even where they are not named.

The walk also found places where `security.md` no longer said what the code does: when the session cookie is `Secure`, how the identity provider's roles behave, that the history records the person and not the role, which files are public, what `doctor --production` checks, who sees a restricted application, two rows of the permissions table, and nothing at all about what 0.8.0 and 0.9.0 added. The document now says what the code does, including those additions.

### Wave 10: the code added for 0.10.0

A reviewer who had taken no part in writing it walked everything added between 0.9.0 and 0.10.0 against `spec/security.md`: the assistant's three protocols and the Bedrock signer, who may ask and how often, how long exchanges are kept, the gateway headers, `doctor --assistant`, kept scores and the counter they stand on, the column-only reads, and the batched tasks. Each finding was confirmed by running it, and each test is now in `tests/test_review_wave10.py`, where it failed before its fix. Finding 3 is about PostgreSQL alone, and was confirmed there.

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | The AWS variables the Bedrock signer reads were not kept from connectors and standings: an administrator's session could send the server's AWS secret to a host of its choosing as a connector's credential | Low | Any `AWS_` variable is one of the server's own, refused as a connector's or a standing's credential |
| 2 | The daily limit was counted from exchanges kept after the server answered, so questions asked at once all passed it, and one person could tie up every thread that answers requests while a slow model worked | Low | A place for each question is kept, and counted, before the server is asked, one person at a time; each person has one question waiting at once |
| 3 | On PostgreSQL, a page that had read an application before someone changed it could keep its score under the counter after the change, and every later page would show it until the next change | Low | A session that reads sees one moment of the database throughout (repeatable read) |
| 4 | A refusal's reason was read outside the time allowed, so a server sending it a byte at a time held the request, or `doctor`, without end. The same way of reading meant that, for every answer AppWren reads from another server, the deadline was not looked at while a slow answer trickled in, and only the outer bound on the whole call held | Low | The reason is read within the time allowed, and every answer is read as it arrives, with the deadline looked at between reads |
| 5 | Exchanges stopped being removed after `keep_days` once the assistant was turned off, and stayed readable | Low | They are removed whether or not it is on |
| 6 | What the server gave as its reason for refusing (a masked key, an AWS account and role) was told to the person who asked, and kept in the history for ever | Informational | The person is told that it refused, and its status; the reason is kept with the exchange, never in an event |
| 7 | A server that did not speak HTTP, or sent JSON nested deeply enough, made the request fail with a 500, and nothing was kept or counted | Informational | Every such failure is a failed exchange |
| 8 | `key_env` could name one of the server's own variables, such as the database's address, which would then be sent to the model server as its key | Informational | It may not; nor may it be an AWS credential, except an Amazon Bedrock API key for `bedrock` |

Two more were found while tracing what kept scores carry, in code older than this wave:

| # | Finding | Severity | Fix |
|---|---|---|---|
| A | An application's scores named the primary provider it overlaps with, its reference, name, and value, even to someone who may not see that provider because it is restricted. Present since 0.1.0 | Medium | Named only to someone who may see it; to anyone else, *an application you may not see*, in the scores and in kept snapshots |
| B | A scenario's risks named the flags withheld everywhere else, such as *no data agreement*, to someone who may not see the contract behind them. Finding 4 of the wave 9 review was incomplete | Low | A scenario names only the flags the reader may be told of. A kept snapshot's working withholds them too |

Left as it is, on purpose:

- **Gateway headers are checked by name.** A value is never read, so an administrator could put a key in one; the guide says not to. The configuration's author is trusted, as with every other setting.
- **What the assistant is told is sent to the model server.** That is what it is for; `max_data_class` and what the person may see limit it.

Found sound: the signer (the secret is never sent, the host is signed, the session token goes only where it belongs, no redirect is followed); keys only from the environment and never in a prompt or the exchange log; `doctor` naming variables, not values; `roles` on both routes, a token never asking; the day counted from midnight UTC on both routes; deleting exchanges through the history, the words left out; kept scores never depending on who asks, with every reader's withholding made afresh from a copy; every bulk statement on a table no score reads; `fact_value`, outside the history, written only through the session; a rolled-back write taking its bump back; write sessions neither keeping nor reusing; the column-only reads keeping the same rows, values, and checks; and the batched tasks, which a unique key keeps from being raised twice however a run stops.

The walk also found that `security.md` said nothing of what 0.10.0 added (the three protocols and their credentials, who may ask and how often, the server's reason, how long exchanges are kept, and kept scores) and that it said every exchange is kept. It now says what the code does.

## Accessibility

### How it was done

Two scripts, each run over every screen of the demo organization, as the people who use them:

| Check | What it does | Result |
|---|---|---|
| `scripts/a11y-audit.mjs` | Names on controls, labels on fields, headings, landmarks, duplicate ids, target sizes, and the contrast of every piece of text, in three palettes, by day and after dark: 142 screens and dialogs at 0.9.0 | No findings |
| `scripts/keyboard-check.mjs` | Tabs through every page from the top: the skip link first, every stop visible, every control reached; in a dialog, focus starts inside, stays inside, closes with Escape, and returns. It also reads each page as a screen reader is given it: one main landmark and heading, a role and a name on every control, headers on every table | No findings |

The brand kit's colors from the configuration file are checked for contrast when the server starts, by the same rules, so an organization's own palette cannot make text unreadable.

### What this was not

No person has yet listened to AppWren with a screen reader. The keyboard check reads what a screen reader is given, which catches missing names and structure, but not whether a page makes sense when heard. That session, with VoiceOver and NVDA on the main journeys (confirming a record, assessing an application, recording a decision, reading a leadership report), is still to be done by a person.
