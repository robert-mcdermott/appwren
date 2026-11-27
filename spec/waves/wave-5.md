# Wave 5: Planning change (v0.5.0)

**Goal:** decisions become planned, tracked change. Waves 1 to 4 made a record that is true, connected, kept current, and fed by the tools that already know it, and a decision recorded against it. This wave carries a decision through: the portfolio is reviewed on a cadence with an agenda drawn from what needs deciding; what is decided becomes an initiative on a roadmap with dates; a request for something new is checked against what already serves the need before anything is built or bought; an application cannot move to a stage without what that stage requires; and a retirement is a plan with a checklist that ends in savings on the record.

**Branch:** `wave-5` · **Target version:** `0.5.0` · **Status:** ◐ in progress

The people who decide come first here ([roadmap](../roadmap.md)): a review that is quick to prepare and leaves a record of what was decided, and a roadmap that shows what the decisions commit the organization to.

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.4.0:

1. A portfolio review has a scope (a unit and everything beneath it, narrowed by tier if wished), a date, and an agenda drawn from that scope: applications whose decision differs from today's recommendation, whose decision is due for review, that have no decision, or that were added by hand. Each item shows the recommendation and the decision on record; a decision recorded during the review is kept on its item; a closed review is a record of what was decided and changes no more (PLN-01).
2. An initiative (a modernization, migration, consolidation, retirement, or other change) names the applications it changes and what it does to each, has an owner, a stage, and start and end dates, and shows the decisions on record for those applications. The roadmap shows initiatives on a timeline by unit and kind, each bar a link (PLN-02).
3. A request for something new names the need and the capability it serves; it lists the applications that already serve that capability and any whose names are close; options to build, buy, partner, or reuse are compared; and the request ends approved (adding a proposed application named for it), met by an existing application, or declined, each with a reason (PLN-03).
4. Moving an application to a stage requires that stage's required fields, and a move short of them is refused with what is missing. The program can switch the gates off (DEC-06).
5. A retirement plan for an application has a date and a checklist (users told, data archived, interfaces removed, licenses ended, access removed, infrastructure torn down), each step done by a named person on a date; when every step is done the application is retired and the savings (its annual cost at that point) are on record, and a report sums the savings realized (DEC-07).
6. The role-by-route matrix covers every new route; the demo shows every new screen with convincing data and its storylines still hold; the accessibility audit and keyboard check pass; the suite passes on both databases.

Requirements delivered: PLN-01 to PLN-03; DEC-06, DEC-07.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **Who runs a review:** managers, and leaders over its unit. Anyone may read one about what they may see (slice 1).
- **The agenda is drawn, then kept.** Drawing the agenda adds what needs deciding at that moment; items can be added or removed by hand until the review is closed. The review does not change what a decision is or who may record one: a decision recorded in a review is an ordinary decision, kept on the item as well (slice 1).
- **Initiatives are records,** with a reference (`INI-0001`), a unit, an owner, and a history, kept by managers, architects, and the unit's stewards. Their kinds and stages are vocabularies the program can rename (slice 2).
- **A request is a record too** (`REQ-0001`), opened by anyone, worked by stewards, architects, and managers. Approving one adds an application in the *proposed* stage; it never builds or buys anything (slice 3).
- **Stage gates are on by default** for a new installation and for an upgraded one. They apply to a move to a later stage, not to a record created at a stage or to a move back (slice 4).
- **Savings are the annual cost at retirement,** from the cost lines when there are any, else the application's annual cost (slice 5).

---

## Slice 1: Review cycles ☑

**Goal:** a portfolio review that is quick to prepare and leaves a record of what was decided.

- [x] `review` and `review_item`: a scope, a date, a chair, a state (planned, open, closed); items with why each is on the agenda, the recommendation and decision at that moment, and the decision taken in the review
- [x] Drawing the agenda from the scope; adding and removing items by hand
- [x] The review's page: the agenda with each item's recommendation, decision on record, and mismatch; recording a decision from it; closing it
- [x] Reviews listed under Portfolio; Home shows a review that is coming up to the people who run it

**Acceptance:** an agenda drawn from a scope holds exactly the applications that need deciding there; a decision recorded during the review is on its item; a closed review changes no more.

## Slice 2: Initiatives and roadmap ☑

**Goal:** what the decisions commit the organization to, with dates.

- [x] `initiative` as a record, with its kind, stage, owner, and dates, and `initiative_application` with what it does to each application
- [x] On the initiative: its applications with the decision on record for each; on an application: the initiatives that change it
- [x] The roadmap: initiatives on a timeline by unit and kind, each bar a link, with a list that says the same
- [x] Starting an initiative from a decision, with its application filled in

**Acceptance:** the roadmap shows exactly the initiatives in its filters, and an application's page lists every initiative that names it.

## Slice 3: Intake ☑

**Goal:** a request for something new, checked against what is already there.

- [x] `request` as a record, with the need, the capability, who asked, and options to build, buy, partner, or reuse
- [x] What already serves the capability, and what is named like the request, shown on it
- [x] Ending it: approved (an application in the proposed stage, named for it), met by an existing application, or declined; each with a reason

**Acceptance:** a request for a capability already served lists every application serving it; approving one adds exactly one proposed application, and ending it twice is refused.

## Slice 4: Stage gates ☑

**Goal:** what each stage requires, required.

- [x] A move to a later stage refused while that stage's required fields are missing, with what is missing, in the editor, the API, and an import
- [x] A program switch for the gates

**Acceptance:** a move short of the stage's requirements is refused with the list; with the gates off it is allowed and the list is still shown.

## Slice 5: Retirement playbook ☐

**Goal:** a retirement that is planned, checked off, and counted.

- [ ] `retirement`: an application's plan, its date, and its checklist, each step done by a named person on a date with a note
- [ ] Completing it retires the application and records the savings
- [ ] Retirements under way and done, with the savings realized by year

**Acceptance:** a plan with every step done retires its application with its savings on record, and the report's total is the sum of the plans behind it.

## Slice 6: Release prep ☐

- [ ] Guides, changelog, upgrade from 0.4.0 on both databases, audits, release, and the site republished

## Notes

Decisions and discoveries made during the wave are logged here, newest last.
- **Stage gates never stop a retirement.** Stage requirements add up, stage by stage, so a move to *retired* would otherwise ask for a full record. Moving to a retired or archived stage, and moving back, need nothing.
- **The demo's history was kept without gates.** Its two years were recorded before stage gates existed, so the builder records them with the gates off and the portfolio team switches them on six days before the build.
