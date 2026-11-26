# ADR-0012: Measures become levels through defined bands

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

Some scoring factors are measures with no natural ceiling: the number of users, annual cost, the number of applications that depend on this one. To be combined with answers on a one-to-five scale, each must become a level.

There are two common ways. **Portfolio-relative** levels put each application in a percentile of the whole portfolio: the top fifth by users scores five. **Defined bands** set fixed boundaries: a thousand users or more scores five.

Percentiles adapt to any portfolio size without tuning. But an application's score then changes when *other* applications are added, edited, or retired, which nobody looking at that application can explain. A score that moves when nothing about the application has changed is the fastest way to lose an owner's trust.

## Decision

- Every measure becomes a level through **defined bands** held in the scoring profile: for example users `[10, 50, 250, 1000]` give levels one to five. The bands, and the level they produced, are shown in the working.
- The default bands are chosen for an organization of a few hundred to a few thousand people, and are part of the program, so an adopter changes them in the app.
- An application's scores change only when something about the application, its links, or the program changes, and the history can say which.
- Portfolio-relative views remain available as *reports* (for example "the costliest tenth of the portfolio"), but they never feed a score.

## Consequences

- Scores are stable and explainable. The working reads "1,200 people use it: 1,000 or more is level 5".
- Bands need tuning for very small or very large organizations. The default program says so, and the starter programs from wave 7 come with bands for their size.
- Changing a band is a program change: it produces a new version of the profile, and the next snapshot records it.

## Alternatives

- **Percentiles:** self-tuning, but scores that move for reasons outside the record.
- **Percentiles frozen once a period:** stable within a period, but still impossible to explain from the application's own record, and it makes the scoring of a new application depend on when it was added.
