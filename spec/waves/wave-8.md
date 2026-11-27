# Wave 8: Connected (v0.8.0)

**Goal:** fit into the systems around it, all of it optional. Waves 1 to 7 made AppWren a portfolio an organization can adopt and run. This wave lets the processes around it rely on it: a purchasing form or a data request asks whether an application is approved for what it is about to be used for; an AI assistant reads the portfolio under a person's own permissions and drafts changes that person confirms; an optional assistant inside AppWren drafts records and answers questions with links to the records behind each answer; and an application links to its records in other systems of record with their standing. None of it is on until someone turns it on.

**Branch:** `wave-8` · **Target version:** `0.8.0` · **Status:** ☑ done

The processes around the portfolio come first here ([roadmap](../roadmap.md)): each answer AppWren gives another system says why, and nothing another system says changes a record until a person accepts it.

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.7.0:

1. Another process asks whether an application is approved for new use, or for a class of data, and gets an answer with its reasons: its stage, its decision, its support, and the data it is recorded to handle. A restricted application is named to nobody who may not see it (INT-04).
2. A person makes a token of their own, which acts as them and can read and draft but not change. An optional tool server, run beside an AI assistant, reads the portfolio through the API with that token and drafts changes as suggestions, which the person accepts or dismisses on the record; nothing changes until they do (INT-05).
3. An optional assistant, off and invisible until an administrator configures a model server (any with the common chat API, including one on the same machine), drafts an application record from a document's text and answers questions about the portfolio with links to the records behind the answer. Every exchange is kept (INT-06).
4. An application links to its records in other systems of record by external reference, and where such a system offers a standing (approved, open, closed), AppWren reads it and shows it beside the link (INT-07).
5. The role-by-route matrix covers every new route; the demo still holds; the accessibility audit and keyboard check pass; the suite passes on both databases; the API keeps the 0.7.0 contract.

Requirements delivered: INT-04 to INT-07.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **"Approved" means in service, with a decision that keeps it, for the data it is recorded to handle** (slice 1). An application is approved for a class of data when it is in service (not proposed, retired, or archived), its decision on record does not take it away (retire, replace, or consolidate), nothing it runs on is past its end of support, and its record says it handles that class. The answer gives each reason, so the process asking can decide for itself.
- **Personal tokens read and draft; they never change a record** (slice 2). A person makes one under Your account. It acts as them, so an assistant sees exactly what they see. What it proposes waits on the record as a suggestion.
- **The assistant is off, and when on it is told only what the person asking may see** (slice 3). It is configured in the configuration file, never in the app, with the key in the environment.
- **A system's standing is read only where an administrator gives it an address that answers in JSON** (slice 4), by a scheduled job, like any connector.

---

## Slice 1: A reference others can check ☑

- [x] `GET /api/v1/checkpoint/{ref}`, with a data class: approved or not, and why
- [x] A restricted application is not named, or even confirmed, to someone who may not see it

## Slice 2: Tool server for assistants ☑

- [x] Personal tokens: read and draft, as the person
- [x] Suggestions on a record, accepted or dismissed by someone who keeps it
- [x] An optional tool server for AI assistants, through the API

## Slice 3: Optional assistant ☑

- [x] Drafts an application record from a document's text
- [x] Answers questions with links to the records behind the answer
- [x] Every exchange kept; off and invisible until configured

## Slice 4: Other governance records ☑

- [x] External references with their standing, where the other system offers it

## Slice 5: Release prep ☑

- [x] Guides, changelog, upgrade from 0.7.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.
- **A personal token is the person, cut down to reading and proposing.** It is built from their account's own roles, so an assistant sees exactly what they do; the middleware lets it make one kind of change, a proposal. A proposal of a sensitive field the person may not see is refused, since it would say what they think the value is. Accepting is a person's own edit, signed in, never a token's.
- **The assistant is told a list, not the database.** A question is answered from a compact list of the applications in service the person may see (reference, name, summary, unit, stage, tier, decision), leaving out any that handle data more sensitive than `max_data_class`; references in the answer are linked only if they were in that list. A draft is checked field by field against the form's own choices. The model server is asked with no database session open.
- **A standing is read like a connector reads, and kept like a change.** The program names the address per system, with the identifier as `{id}`, where to look in the JSON answer, and a key's variable, which may not be the server's own. The job writes the standing with a system actor, so a change appears in the record's history; when it was read and why it failed are bookkeeping, not history.
- **An independent review of the wave's code found five things.** The most serious, a personal token outliving its owner's password change, and four low or informational ones, are fixed with tests that fail without the fixes; see [the review](../reviews/2026-11-security-and-accessibility.md).
