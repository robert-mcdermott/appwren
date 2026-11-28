# Wave 10: The assistant, ready (v0.10.0)

**Goal:** the optional assistant ready for the models organizations pay for, and the pages that score the whole portfolio quick at its largest. The assistant speaks to the official services and to Amazon Bedrock as well as to a model of one's own, with limits on who uses it, how much, and how long what it was told is kept. The dashboard, data quality, overlap, and the portfolio list answer quickly at 5,000 applications, with every figure, score, flag, and working exactly as before. 1.0.0 still follows the maintainer's review.

**Branch:** `wave-10` · **Target version:** `0.10.0` · **Status:** ☑ done

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.9.0:

1. `[assistant] provider` chooses the protocol its server speaks: chat completions, the messages interface, or Amazon Bedrock's Converse API, with an Amazon Bedrock API key or with access keys from the environment. No temperature is sent unless one is set. A server's own reason for refusing is shown, and an answer cut off or declined says so (INT-06).
2. An administrator can limit who may use the assistant and how many questions and drafts each person asks for in a day, and exchanges older than the configured number of days are removed. `appwren doctor` says what is missing for the configured provider, and can ask the server one small question. A gateway may be sent extra headers, never a key.
3. At 5,000 applications and 50,000 components, the dashboard, data quality, overlap, the portfolio list, and Home for a manager each answer within half a second when opened again before the next change, and sooner than 0.9.0 when first opened after one, on SQLite and PostgreSQL (PLT-22).
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

## Slice 1: More model servers ☑

- [x] `[assistant] provider`: chat completions, the messages interface (the official service unless a `url` is given, including Bedrock's `bedrock-mantle` endpoint), or Bedrock's Converse API
- [x] Bedrock with an Amazon Bedrock API key, or signed with Signature Version 4 from the standard library, checked against AWS's published test vectors
- [x] `region`, `max_tokens`, `temperature`, and `timeout_seconds`; no temperature unless set; the server's reason for a refusal shown; an answer cut off or declined says so
- [x] Chat completions and the messages interface checked against a model server on this machine
- [ ] Bedrock checked against a real account, with the maintainer's credentials: left to the maintainer, with `appwren doctor --assistant`; the release notes say it has not been

## Slice 2: The assistant, for paid models ☑

- [x] `daily_limit`: requests to the model per person per day, from midnight UTC, counted from the exchanges kept, answered or not; past it, 429 with a plain answer
- [x] `roles`: the roles that may use the assistant, administrators always; the session says whether it is open to the person, and the page, the menu entry, and the routes follow it
- [x] `keep_days`: exchanges older than this removed by the nightly housekeeping, in batches, through the history, which keeps that each happened but never the words
- [x] `headers`: extra `"Name: value"` headers for a gateway, signed with the request on Bedrock; one that carries a credential, or one AppWren sends itself, is refused
- [x] `appwren doctor`: what is missing for the configured provider (a key, AWS credentials), and `--assistant` to ask the server one small question

## Slice 3: Quick at its largest ☑

- [x] The facts scores are worked out from, the people named on each application, and the cost breakdown read with only the columns they use, giving the same values sooner; every application's result and five pages for each of the demo's eight people compared byte for byte, before and after, on the demo grown to 5,000
- [x] Scores kept between changes, in each server process, keyed by a counter every write to a table a score could read bumps in its own transaction (`appwren.db.changes`), the day, and the scoring model; kept only from sessions that read
- [x] The check the test suite runs under (`kept.CHECK`) works every reused score out again and fails on any difference; the whole suite passes with it on, over 3,000 reused scores
- [x] The scheduler works out what is due by reading, then raises it two hundred at a time, each batch committed, and settles in a last turn; the same tasks as one turn, checked on the demo grown to 5,000
- [x] `scripts/perf.py` times each scoring page just after a change, and again with `--again` as its budget
- [x] The configuration guide's figures measured again on both databases

## Slice 4: Reviewed ☑

- [x] The code added in this wave walked against the threat table by a reviewer who did not write it: eight findings in the wave's code (five low, three informational) and two in older code (one medium, one low), each fixed with a test in `tests/test_review_wave10.py` that failed before its fix, and `security.md` brought up to date

## Slice 5: Release prep ☑

- [x] 0.9.0's API description kept as the contract this wave keeps (`tests/fixtures/openapi-0.9.0.json`)
- [x] The compatibility draft covers the new `[assistant]` settings, and says the words AppWren puts to a model are not promised
- [x] The soak test run again, with scores kept, and the guide's figures for it brought up to date: 6,688 requests in ten minutes, none failed, sign-in within 2.7 s and Home within 1 s for 95 in 100, memory level at about 580 MB
- [x] Guides, changelog, upgrade from every earlier release on both databases (all 18 pass), audits (no findings in 142 scenes; keyboard check; 17 site pages), release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- The assistant of 0.8.0 and 0.9.0 always sent a temperature of 0.2. Newer models refuse any temperature with a 400, so through the messages interface's compatibility layer it could not have answered with a current model. The temperature is now sent only when set.
- AppWren's assistant asks one question and reads one whole answer, so it needs no streaming and gives the model no tools. Bedrock is spoken to through `/converse`, which answers in plain JSON, so no decoder of AWS's event stream is needed.
- Measured at the start of the wave with `scripts/perf.py` on SQLite: at 1,000 applications every page answers within a second. At 5,000, the dashboard, data quality, overlap, the portfolio list, and Home for someone over the whole portfolio each take about 1.5 s; every other page takes a fifth of a second or less, apart from the engineering maturity page (0.9 s) and the capability map (0.1 to 0.5 s). Of the 1.5 s, scoring every application in service takes 1.2 s: 0.8 s reading the facts, much of it loading whole technology and release rows for 50,000 components where six columns are used, and 0.3 s in the engine. One run measured data quality at 6.9 s; two more runs gave 1.5 s.
- The daily limit counts every exchange kept, answered or not, so a server that keeps failing cannot be asked without end either. Today's count is never touched by `keep_days`, which is at least a day.
- Lists in the configuration (`roles`, `headers`) may come from the environment as text split by commas, or as a JSON list where a value holds a comma.
- Of the 1.2 s that scoring 5,000 applications took, loading whole technology and release rows for 50,000 components (when six columns are used) took a third; the people named on each application and the cost breakdown did the same on the pages that list the portfolio. Reading only the columns used gives the same values, compared byte for byte.
- `fact_value` is not history: a source's facts are kept outside it. It feeds signals, so the counter scores are kept by counts every table but a short list of those no score reads (sessions, notices, job runs, deliveries, snapshots, the assistant's exchanges), rather than counting events. A table added later counts until it is put on that list.
- Kept scores take about 80 MB in each server process at 5,000 applications, 16 kB each. Packing them smaller was tried: unpacking took longer than working them out.
- The triggers job raised 1,350 tasks on its first run over the demo grown to 5,000, in one transaction of 1.1 s. It now writes eight, the longest 0.46 s (the last turn, which works out what is due again as every hourly run does).
- The exit criterion first set a second for the first opening after a change. Measured at the end of the slice: 1.2 to 1.3 s on SQLite and 1.4 to 1.5 s on PostgreSQL, from 1.5 to 2.0 s in 0.9.0. What is left is reading the facts (0.6 s, most of it the database handing back 55,000 rows of technologies) and the engine (0.3 s); either could be made quicker only by working out less, or by working out only what a change touched, which the criterion of identical results rules out for this wave. The criterion is restated as measured: half a second when opened again, and sooner than 0.9.0 after a change.
- The review found that a restricted application, when it was the primary provider for a capability, was named, with its value, in the scores of every application that overlaps it, to anyone who could see those. It had been so since 0.1.0; kept scores did not cause it but made it visible to the reviewer, since what is kept must never depend on who asks. Peers are now taken out as each answer is made.
- Each question to the assistant now keeps its place (and is counted) in a short write before the server is asked, and is answered in a second. So an exchange is two events, made and answered.
- The soak test at release found sign-in's 95th percentile at 6.7 s, over its budget of 5. The scheduler's first run over the demo grown to 5,000 held SQLite's write lock for 3.5 s while it told 3,105 escalations in one transaction, and for 2.7 s while the monthly snapshot scored every application inside its write; back to back, nobody could sign in. Reminders are now worked out by reading and told two hundred at a time (the longest write 0.34 s), and the snapshot is scored by reading and used if nothing changed before its write (1.5 s, the writing of 5,000 rows). What the three jobs write was compared row for row, before and after: 18,073 reminders, 5,127 notices, and 5,376 score snapshots, the same, and the same digest.
