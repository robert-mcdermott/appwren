# Wave 10: The assistant, ready (v0.10.0)

**Goal:** the optional assistant ready for the models organizations pay for, and the pages that score the whole portfolio quick at its largest. The assistant speaks to the official services and to Amazon Bedrock as well as to a model of one's own, with limits on who uses it, how much, and how long what it was told is kept. The dashboard, data quality, overlap, and the portfolio list answer quickly at 5,000 applications, with every figure, score, flag, and working exactly as before. 1.0.0 still follows the maintainer's review.

**Branch:** `wave-10` · **Target version:** `0.10.0` · **Status:** ◐ in progress

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.9.0:

1. `[assistant] provider` chooses the protocol its server speaks: chat completions, the messages interface, or Amazon Bedrock's Converse API, with an Amazon Bedrock API key or with access keys from the environment. No temperature is sent unless one is set. A server's own reason for refusing is shown, and an answer cut off or declined says so (INT-06).
2. An administrator can limit who may use the assistant and how many questions and drafts each person asks for in a day, and exchanges older than the configured number of days are removed. `appwren doctor` says what is missing for the configured provider, and can ask the server one small question. A gateway may be sent extra headers, never a key.
3. At 5,000 applications and 50,000 components, the dashboard, data quality, overlap, and the portfolio list each answer within a second when first opened after a change, and within half a second when opened again before the next change, on SQLite and PostgreSQL (PLT-22).
4. Every application's scores, recommendation, flags, confidence, and working are the same as 0.9.0 gives, checked on the demo grown to 5,000 applications, and the whole suite passes with every reused score checked against a fresh calculation.
5. The scheduler's first run on a large installation writes the tasks it raises in batches, so people saving at the same time are not held up, and raises the same tasks as before.
6. The code added in this wave has been reviewed against the threat table, with what is found fixed and `security.md` brought up to date.
7. The role-by-route matrix covers every new route; the demo still holds; the accessibility audit and keyboard check pass; the suite passes on both databases; the API keeps the 0.9.0 contract; every earlier release upgrades to this one.

Requirements delivered: INT-06 (extended), PLT-22 (extended).

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed at the review of 0.10.0:

- **The protocol is named, not the vendor** (slice 1): `openai`, `anthropic`, `bedrock`. Existing configurations keep working, since `openai` is the default.
- **No temperature by default** (slice 1). The 0.2 sent before is refused by newer models; a model of one's own can be given one.
- **A hundred requests to the model per person per day, and exchanges kept for a year** (slice 2), unless the configuration says otherwise; 0 means no limit, or kept for ever. Anyone who may read the portfolio may use the assistant unless the configuration names roles. Administrators always may.
- **Scores are reused between changes, per server process** (slice 3). Kept scores at 5,000 applications take tens of megabytes in each process. Any change recorded in the history, a new day, or a change to the scoring model makes the next page work them out again.
- **Several portfolios (PLT-21) is parked.** It is in the roadmap's Later list and is not to be started until the maintainer asks for it.

---

## Slice 1: More model servers ◐

- [x] `[assistant] provider`: chat completions, the messages interface (the official service unless a `url` is given, including Bedrock's `bedrock-mantle` endpoint), or Bedrock's Converse API
- [x] Bedrock with an Amazon Bedrock API key, or signed with Signature Version 4 from the standard library, checked against AWS's published test vectors
- [x] `region`, `max_tokens`, `temperature`, and `timeout_seconds`; no temperature unless set; the server's reason for a refusal shown; an answer cut off or declined says so
- [x] Chat completions and the messages interface checked against a model server on this machine
- [ ] Bedrock checked against a real account, with the maintainer's credentials

## Slice 2: The assistant, for paid models ☐

- [ ] `daily_limit`: requests to the model per person per day, counted from the exchanges kept, with a clear answer when it is reached
- [ ] `roles`: the roles that may use the assistant; the page, the menu entry, and the routes follow it
- [ ] `keep_days`: exchanges older than this removed by the scheduler's tidying job
- [ ] `headers`: extra `"Name: value"` headers for a gateway, never a key or an `Authorization` header
- [ ] `appwren doctor`: what is missing for the configured provider (a key, AWS credentials, a region), and `--assistant` to ask the server one small question

## Slice 3: Quick at its largest ☐

- [ ] The facts scores are worked out from are read with only the columns they use, giving the same facts sooner; a test compares every application's result before and after on the demo grown to 5,000
- [ ] Scores kept between changes, keyed by the head of the history, the day, and the scoring model, in each server process
- [ ] A setting the test suite turns on that works every reused score out again and fails on any difference; the whole suite passes with it on
- [ ] The scheduler's first run on a large installation writes the tasks it raises in batches
- [ ] `scripts/perf.py` budgets for the four pages, first open and again

## Slice 4: Reviewed ☐

- [ ] The code added in this wave walked against the threat table: the assistant's credentials, what a server's refusal may say back, the kept scores, the batched tasks; each finding fixed with a test, and `security.md` brought up to date

## Slice 5: Release prep ☐

- [x] 0.9.0's API description kept as the contract this wave keeps (`tests/fixtures/openapi-0.9.0.json`)
- [ ] The compatibility draft covers the new `[assistant]` settings
- [ ] Guides, changelog, upgrade from every earlier release on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- The assistant of 0.8.0 and 0.9.0 always sent a temperature of 0.2. Newer models refuse any temperature with a 400, so through the messages interface's compatibility layer it could not have answered with a current model. The temperature is now sent only when set.
- AppWren's assistant asks one question and reads one whole answer, so it needs no streaming and gives the model no tools. Bedrock is spoken to through `/converse`, which answers in plain JSON, so no decoder of AWS's event stream is needed.
- Measured at the start of the wave with `scripts/perf.py` on SQLite: at 1,000 applications every page answers within a second. At 5,000, the dashboard, data quality, overlap, the portfolio list, and Home for someone over the whole portfolio each take about 1.5 s; every other page takes a fifth of a second or less, apart from the engineering maturity page (0.9 s) and the capability map (0.1 to 0.5 s). Of the 1.5 s, scoring every application in service takes 1.2 s: 0.8 s reading the facts, much of it loading whole technology and release rows for 50,000 components where six columns are used, and 0.3 s in the engine. One run measured data quality at 6.9 s; two more runs gave 1.5 s.
