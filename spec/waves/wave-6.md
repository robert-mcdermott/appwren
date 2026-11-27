# Wave 6: Insight (v0.6.0)

**Goal:** answer leadership's questions from the record, with figures that explain themselves. Waves 1 to 5 made a record that is true, connected, current, fed by other tools, and carried through to planned change. This wave reads it back as a whole: defined measures and how they moved between snapshots; a leadership report frozen when it is made; any application, and the portfolio, as it stood on a chosen date; and a scenario that shows what a set of proposed changes would do before anyone commits to it.

**Branch:** `wave-6` · **Target version:** `0.6.0` · **Status:** ◐ in progress

Leadership comes first here ([roadmap](../roadmap.md)): every figure is a link to the list it counts, every report says when it was made and from what, and nothing is a projection that the record cannot back.

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.5.0:

1. A set of defined measures (applications in service, by disposition, annual cost, people served, assessed and confirmed in time, decided, at each maturity level) is shown with each figure a link to its list, and how each moved between two portfolio snapshots. Applications whose recommendation or decision changed, and whose scores rose or fell by half a point or more, are listed between any two snapshots. An application's page shows its scores over time (RPT-04).
2. Reports by share of the portfolio (the costliest tenth, the least used fifth) are shown, and never feed a score (SCR-14).
3. A leadership report for a period is worked out once and stored whole, with its SHA-256; opening it later shows what was stored, never the records as they are now; it prints cleanly (RPT-05).
4. Any application, and the portfolio, can be shown as it stood on a chosen date, from the history (RPT-06).
5. A scenario is a proposed set of changes (retire this, consolidate that into this, replace) with its effect: cost saved, people whose application changes, interfaces that would break, capabilities left uncovered, and the risk taken away. It changes nothing until someone acts on it (PLN-04).
6. The role-by-route matrix covers every new route; the demo shows every new screen with convincing data and its storylines still hold; the accessibility audit and keyboard check pass; the suite passes on both databases.

Requirements delivered: RPT-04 to RPT-06; PLN-04; SCR-14.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Measures are defined in code, with their definitions on the page.** Each says what it counts and links to that list. The program does not define new measures yet (slice 1).
- **Shares of the portfolio never feed a score.** They answer "which are the costliest", not "is this one costly"; the engine stays on defined bands (ADR-0012) (slice 1).
- **A leadership report is a record** (`RPT-0001`) made by a manager, frozen when made, shown to anyone who may read the whole portfolio, and withheld in part from no one: it is made from what its maker may see, and says so (slice 2).
- **As of reads the history.** Nothing is stored for it: the state on a day is the changes up to the end of that day. Scores as of a day are the nearest portfolio snapshot taken on or before it (slice 3).
- **A scenario is a record too** (`SCN-0001`), kept by architects and managers; it changes nothing, and can be turned into an initiative (slice 4).

---

## Slice 1: Measures and trends ☐

**Goal:** what the portfolio looks like in figures, and how it moved.

- [ ] Defined measures, each with its definition and a link to its list, now and at a portfolio snapshot
- [ ] Movement between two snapshots: changed recommendations and decisions, scores that rose or fell
- [ ] An application's scores over time
- [ ] Shares of the portfolio: the costliest tenth, the least used fifth, and more

**Acceptance:** each measure's figure is the length of the list behind it, and movement between two snapshots lists exactly the applications that moved.

## Slice 2: Leadership report ☐

**Goal:** a report for a budget or roadmap meeting that reopens unchanged.

- [ ] `report`: a period, worked out once and stored whole with its SHA-256
- [ ] What it holds: the measures and how they moved, decisions taken, reviews held, initiatives, requests, retirements and savings, and the flags that matter
- [ ] A page that prints cleanly

**Acceptance:** a report reopened after the records change shows exactly what it showed when made, and its digest checks.

## Slice 3: As of ☐

**Goal:** the record as it stood on a chosen date.

- [ ] Any application as it stood on a date, from the history
- [ ] The portfolio as it stood on a date: what was in service, at what stage, with what decision

**Acceptance:** an application changed after a date shows, as of that date, the values it had then.

## Slice 4: Scenarios ☐

**Goal:** what a set of changes would do, before anyone commits to it.

- [ ] `scenario` with its proposed changes: retire, consolidate into, or replace
- [ ] Its effect: cost saved, people whose application changes, interfaces that would break, capabilities left uncovered, risk taken away
- [ ] Turning a scenario into an initiative

**Acceptance:** a scenario's effect is exactly what its applications' records give, and building one changes no record.

## Slice 5: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.5.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.
