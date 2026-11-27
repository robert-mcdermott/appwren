# Wave 3: Keeping current (v0.3.0)

**Goal:** a portfolio that stays true without a central team chasing it. Waves 1 and 2 made a record worth keeping and connected it. This wave makes it keep itself: the app knows what falls due and says so, in the app and by email; owners confirm their records on a cadence in proportion to what is at stake, and a record nobody has confirmed lowers confidence where everyone can see it; departures, renewals, end of support, and grant ends raise tasks for the person who must act; anything on record can be found; and the program is shaped in the app, with a preview of what a change would do.

**Branch:** `wave-3` · **Target version:** `0.3.0` · **Status:** ◐ in progress

Owners come first here as everywhere ([roadmap](../roadmap.md)). In this wave that means: one list of what is theirs, reminders before anything is late rather than after, confirming a record in one step, and a way to say a score is wrong.

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.2.0:

1. One process runs each scheduled job exactly once, however many servers share the database; what ran and what it did is on record, and an administrator can run or pause a job (CUR-04).
2. Whoever something waits on is told before it falls due and after; what stays late goes to the unit's steward, then its leader. Notices appear in the app, and by email through an SMTP server the administrator names, as they happen or as a daily digest by each person's choice; nothing is sent until email is set up (CUR-04).
3. The people named on an application confirm its record in one step, on a cadence set by tier; a record past its confirmation is stale, says so on its page and in data quality, and lowers data confidence by an amount the scoring model sets, with the reason in the working (CUR-03).
4. A campaign asks the owners of the applications in a unit, narrowed by tier or stage, to assess or to confirm their records by a date; each item closes itself when the thing is done; the campaign shows progress by unit, and coverage by unit matches the list behind it (CUR-05).
5. A departure, a contract notice date, a release reaching end of support, and a grant ending each raise a task for the person who must act, with a date; a task closes itself when its cause is settled, or by a person with a note; everything a departing person answers for is passed on in one step (CUR-06, CUR-07).
6. One search finds any record its searcher may see and nothing else; a filtered list can be saved under a name and shared (CUR-08).
7. Adding an application whose name, alias, or vendor product is close to one already on record shows the candidates first (INV-15).
8. An owner contests a factor's value with a note and a link to the evidence; a manager or architect accepts it or answers it, and both stay on the record (SCR-13).
9. The portfolio team edits vocabularies, the organization's own fields, the question bank, the scoring profiles, thresholds and rules, and the cadences in the app, and sees which applications' scores, recommendations, and flags would change before publishing; publishing changes exactly those (CUR-09).
10. A portfolio snapshot is taken on the first of each month by itself.
11. Upgrading a 0.2.0 installation keeps every row and file, and no record is stale on the day of the upgrade.
12. The demo organization shows every new screen with convincing data, and its storylines still hold. The role-by-route matrix covers every new route; the accessibility audit and keyboard check pass; lint and the private-terms check are clean; the suite passes on both databases.

Requirements delivered: CUR-03 to CUR-09; INV-15; SCR-13.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **The application is what is confirmed.** Confirming an application confirms its record and its parts: components, interfaces, where it runs, cost lines, and the people named on it. Contracts, vendors, and technologies are kept by the portfolio team and architects, and are not confirmed on a cadence (slice 2).
- **Who confirms:** anyone named on the application, its unit's stewards, and managers (slice 2).
- **How often:** every 6 months for tiers 1 and 2, every 12 for tiers 3 to 5. The periods are in the scoring model's cadence, beside how long an assessment stays current (slice 2).
- **A stale record lowers confidence by 15 points**, never below zero, and *Confirm the record* heads the list of what would raise it. A record that was never confirmed is stale one period after it was added, or after the day this installation began asking, whichever is later; so nothing is stale on the day of an upgrade (slice 2).
- **Reminders:** two weeks before a date and the day after it; a week late goes to the unit's steward, three weeks late to its leader. These are in the cadence too (slice 1).
- **Email is optional and off** until `[mail]` names a server; its password comes from the environment, as single sign-on's secret does (slice 1).
- **Triggers are the program's, not code's to time.** How far ahead a contract notice, an end of support, and a grant end raise a task are cadence settings: 60, 180, and 180 days. A signal crossing a threshold waits for signals, in wave 4 (slice 4).
- **A departure raises tasks; it does not reassign by itself.** The application shows that nobody is accountable, and a steward is asked to name someone. Passing everything on is one deliberate step (slice 4).
- **Contesting a score is about one factor.** An owner says which factor is wrong, what it should be, and why, with a link to the evidence. The score does not move until the record or an assessment is changed; accepting a contest says so and points the owner to the change (slice 5).

---

## Slice 1: Schedules and email ☑

**Goal:** the app knows what falls due, and says so.

- [x] The scheduler: jobs as rows with a lease, so one process runs each, from the server or from `appwren jobs run`; runs that did something, and failures with their reason, kept for ninety days
- [x] Admin → Scheduled work: each job, when it last ran and what it did, run now, pause
- [x] Notices: in the app, with a count in the top bar and a page of them; each person's choice of email as it happens, a daily digest, or none
- [x] Reminders over what has a date: an assessment about to expire, a decision's review and target dates, a contract's notice date; before, after, then the steward and the leader
- [x] `[mail]` in the configuration file; an outbox in the database, sent with retries and a limit; nothing written before email was set up is ever sent; `appwren doctor` checks the server

**Acceptance (met):** two connections to one database run a job once between them; an overdue review reminds its decider, then the steward, then the leader, each once; with no mail server nothing is attempted and nothing is sent later.

**Done:** three jobs run inside the server: reminders, email, and housekeeping. A process claims a job's row before running it, with a lease that lapses if the process dies, so several workers, several servers, and `appwren jobs run` from a scheduled task run each job once between them; what is due comes from the database and the clock, so a restart catches up. Runs that did something, and failures with their reason, are kept for ninety days. Admin → Scheduled work shows each job and can run or pause it; `appwren jobs` does the same. Reminders look at an assessment's end (by tier), a current decision's review and target dates, and a contract's notice date, for applications in service; later slices add their own dates through `reminders.SOURCES`. Whoever a thing waits on is told two weeks ahead and the day after; an assessment and a target that stay late go to the unit's steward after a week and its leader after three; a review stays with whoever decided, or the unit's leaders if they have left; a notice date stays with the contract's owner. Each stage is said once for a given date, moving the date starts again, and something found long overdue is told once at the stage it has reached. The three periods are read from the scoring model's cadence, with these defaults until the model says otherwise. Email is optional: with `[mail]` set, notices go to an outbox in the database and are sent from there, each as it happens or as a daily summary by each person's choice, with retries and a limit, and nothing written before email was set up is ever sent. The bell in the top bar counts unread notices. The demo sends the reminders of its last two months, and what is more than a week old has been read. The acceptance tests are in `tests/test_schedule.py` and `tests/test_mail.py`, which sends over real SMTP to a server inside the test.

## Slice 2: Attestation ☑

**Goal:** owners confirm their records, and a record nobody confirms says so.

- [x] `attestation`: a statement by a named person on a date that an application's record is right, with an optional note; never edited
- [x] **Confirm the record** on the application, for those who may; when it is next due on the page
- [x] A stale record: a mark on the page, a flag, a figure in data quality and on the dashboard, a filter on the list, an item on Home, and reminders
- [x] The engine: a stale record lowers confidence by the model's amount, with the line in the working; *Confirm the record* first in what would raise it
- [x] The day this installation began asking, written by the upgrade; the demo's confirmations

**Acceptance (met):** an application past its confirmation loses exactly the model's amount of confidence and regains it when confirmed; one added the day before an upgrade is not stale after it.

**Done:** a confirmation is an `attestation` row: the application, who, when, and an optional note, in the application's history as *Confirmed the record*. The people named on an application, its unit's stewards, and managers may confirm it; a retired or archived one is not confirmed. How often comes from the scoring model's cadence (`confirm_months`), and the penalty from `stale_penalty`; the engine reads `stale`, `confirm_due`, and `confirmed_on` as facts, takes the penalty off confidence after the coverage is averaged, puts *Confirm the record* first in what would raise it, and raises the built-in *stale* flag. Because confidence is what the rules read, a stale record can move to *Assess*; that is the point. The day the installation began asking is written by every setup and upgrade (`attestation_began`) if it is not there, and a record never confirmed is due one period after the later of that day and the day it was added. The application's page has a line under its scores saying when the record was last confirmed and when it is next due, as a warning with the cost when it is late, and a button for those who may. Data quality counts *Not confirmed in time*, the portfolio list filters by it, Home lists it for the people named, and the scheduler reminds whoever answers for it, then the steward and the leader. The default scoring model's cadence gained the periods, the penalty, the reminder periods, and the trigger periods for slice 4; the 0.2.0 default's digest is in the list an upgrade replaces. The demo's records are confirmed on their cadence from the day each was added; about one in twelve has lapsed, the leaver's four were last confirmed over a year ago, and the spreadsheet nobody kept up was never confirmed, so 22 of the 106 in service are stale. The acceptance tests are in `tests/test_attestation.py`.

## Slice 3: Campaigns ☑

**Goal:** ask the owners, by a date, and see who has answered.

- [x] `campaign` (`CMG`) and `campaign_item`: a kind (assess, or confirm the record), a unit and everything beneath it, narrowed by tier and stage, a date, a message
- [x] Starting one lists every application with whoever is asked, and tells each person once with a count
- [x] An item closes itself when an assessment or a confirmation is recorded after the campaign began; items can be excused with a reason
- [x] The campaign's page: progress, coverage by unit with the least covered first, every item; remind, close, cancel
- [x] Items on Home and in the reminders

**Acceptance (met):** coverage by unit is the length of the list behind each figure; an item closes when, and only when, its thing is done after the campaign began.

**Done:** a campaign (`CMG`) is the people asked, one thing (confirm the record, or assess), a unit and everything beneath it narrowed by tier and stage, a date, and a note. Managers and stewards run campaigns over the units they hold their role for; one over the whole organization needs the role over all of it. A preview says how many applications and people it would ask and lists the applications with nobody to ask, before anything is saved. Starting it makes an item for each application in service, asked of its accountable owner or, where they have gone, a steward of its unit, and tells each person once with a count. An item is done when the record is confirmed or the application assessed after the campaign began: confirming and assessing close the items they answer, and the reminders job closes any a change elsewhere did not, under the scheduler's name. Whoever runs it may excuse an item with a reason, remind those still to do it, close it (what was found is kept), or cancel it. Its page gives the progress, coverage by unit with the least covered first (each unit a link to its own list), and every item, which can be narrowed to what was asked of the reader; items are shown only to those who may see their application. Pending items are on Home, said once where a stale record or an expired assessment would say the same, and in the reminders, which go up to the steward and the leader. The demo has a closed spring assessment campaign in Clinical Research, three quarters done, and a record confirmation in Shared Resources under way. The acceptance test is `tests/test_campaigns.py::test_a_campaign_asks_the_owners_and_tracks_who_has_answered`.

## Slice 4: Triggers and reassignment ☑

**Goal:** what happens in the world raises a task for whoever must act.

- [x] `task`: what is to be done, about which record, for whom, by when, why; closed by itself when its cause is settled, or by a person with a note
- [x] Triggers run each day: a contract's notice date near, a release in use reaching end of support, a grant near its end; each raises one task, never two
- [x] A departure: disabling an account raises a task at once for each application left with nobody accountable
- [x] A page of what a person holds, with the means to pass it all on in one step
- [x] Tasks on Home and in the reminders

**Acceptance (met):** each trigger raises one task for the right person and closes it when settled; disabling an owner leaves nothing without one.

**Done:** a task (`task`) is what is to be done, about which record, for whom, by when, and why, with its cause as a unique key. A fourth job, the triggers, runs hourly: a contract's notice date within the cadence's 60 days raises a task for its owner; a release in use within 180 days of its end of support (or up to 90 days past it) raises one for each application on it, for whoever answers for that application; a grant within 180 days of its end (the application's own grant end, or a grant funding source behind its cost lines) raises one asking for a decision; an accountable owner whose account is disabled raises one for a steward of the unit, or failing one a manager, at once from the disabling and again at every turn if missed. Where nobody answers for an application, its unit's steward is given the task. A task settles itself when its cause is no longer there (the contract's term changed or ended, nothing runs on the release, the grant's date moved, someone is accountable again) or, for a grant, when a decision is recorded after it was raised; the scheduler closes it with the reason under its own name. A person who has the task, or a steward or manager over it, marks it done or dismisses it, with a note. Tasks are on Home, on a page of their own (yours, everything open you may see, those with nobody to do them, closed), and in the reminders, which now carry a contract's notice date as its task's. Every person has a page of what they hold; an administrator or a manager passes all of it on in one step, each role on each record, each contract and interface owned, each open task, and each pending campaign item, telling the person who receives it. Disabling an account does not pass anything on by itself: the departure tasks say who must decide, and the application shows that nobody is accountable until they do. The demo runs the triggers over its last two months: the leaver's four applications, the database release ending next quarter, the grants ending, and the Calendra notice date each have a task with someone to do it. The research software engineer, who was named on nothing in the 0.2.0 demo, now keeps the two pieces of research software in its storylines. The acceptance tests are in `tests/test_tasks.py`.

## Slice 5: Find and tidy ☑

**Goal:** anything on record can be found, and kept in order.

- [x] One search across every record type, cut to what the searcher may see, ranked; in the command palette and on a page of its own
- [x] Saved views: a list's filters under a name, private or shared
- [x] Likely duplicates when an application is added or renamed, by name, alias, and vendor product
- [x] Contesting a score: on a factor, with a note and a link; accepted or answered by the portfolio team; listed for them

**Acceptance (met):** a search never returns a record its searcher could not open, for each of the seven roles; a contest and its answer stay on the record.

**Done:** the search (`appwren.inventory.find`) asks each kind's own list for what matches, so what a person may find is decided by the one rule every list already uses, and ranks each kind's matches (a reference, the whole name, the start of a name, the start of its words, anywhere in the name, elsewhere on the record), putting the kind with the best match first. It is in the command palette, which now finds records as well as pages, and on a page of its own. A saved view is a list's path and its filters under a name, private unless a steward, architect, manager, or administrator shares it; it holds no rows, and where someone was in a list is not kept. Every list of records and the portfolio list have a **Views** button. Likely duplicates are offered while an application is added or renamed: the same words in any order, or nearly the same spelling, between the new name and its aliases and those of every application the person may see, or the same product from the same vendor; nothing is merged. A contest names one factor, the level the owner says it should be, why, and a link to the evidence; whoever keeps the application raises it, and a manager or an architect over its unit accepts or answers it, telling the owner. Open contests are on the answerers' Home and in the application's history, as are the answers. The demo has an answered contest on the clinic's scheduler and one waiting on the flow cytometry scheduler, and a shared view of the critical records nobody has confirmed. The acceptance tests are `tests/test_find.py::test_a_search_never_returns_a_record_its_searcher_could_not_open`, which opens every result as each of the seven roles, and `test_an_owner_contests_a_factor_and_the_portfolio_team_answers`.

**Not done:** a page of likely duplicate pairs across the whole portfolio, and merging two records into one. Duplicates are offered where they are made, which is where they are cheapest to stop.

## Slice 6: Program editors ☐

**Goal:** the program is shaped where it is used.

- [ ] Admin → Program: vocabularies, the organization's own fields, the question bank, profiles and their weights, thresholds, rules, and cadences
- [ ] A draft, and a preview of every application whose scores, recommendation, or flags would change; publishing makes a new version
- [ ] Monthly portfolio snapshots, taken by the scheduler

**Acceptance:** publishing a changed model changes exactly the applications the preview listed.

## Slice 7: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.2.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.
