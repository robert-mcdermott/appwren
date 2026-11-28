# The program handbook

This guide is for the portfolio team: the people who run an application portfolio program with AppWren, from the first decisions to the yearly rhythm of reviews. The other guides say what each screen does. This one says what to do with them, in what order, and why.

A portfolio program answers three questions about every application the organization runs, and keeps the answers true: **what do we run, who answers for it, and what should we do with it?** AppWren keeps the record, works out a recommendation from it, and holds the decision people take. The program is the people and the habits that keep all three current.

## 1. Decide before you start

A few decisions shape everything after them. Make them on paper first; each takes minutes in AppWren once made.

| Decision | Why it matters | Where it lives |
|---|---|---|
| **What counts as an application** | Everything is counted in applications. A definition people can apply the same way keeps the count meaningful | The definition, with its examples, in a program pack: `appwren program export`, then `appwren program import`. Admin → Program does not edit it. See [What counts as an application](the-portfolio.md#what-counts-as-an-application) |
| **The units** | Every application belongs to one unit, which answers for it. Units are how work is shared out, how scope is set, and how leaders see their part | Admin → Units |
| **Who decides** | A decision is taken by a manager or a leader over the application's unit (a manager for the whole organization decides anywhere), and by default not by the person accountable for it. A team too small for anyone else to decide can let an accountable owner who also holds one of those roles decide for their own application; each such decision is marked as the owner's own. Decide who those people are | Admin → People, roles; Admin → Program, decisions |
| **Who keeps records** | Stewards keep a unit's applications complete and current. One per unit is enough to begin | Admin → People, roles |
| **The tiers** | How critical an application is sets how often its record is confirmed and its assessment renewed, and weighs in its business value | Admin → Program, lists for the tiers, and scoring and cadence for how often |
| **What is sensitive** | Annual cost, sign-in, backup, and the last restore test are withheld by default from people without a part in an application. Mark which of the organization's own fields are sensitive as well. The built-in fields change only with a program pack | Admin → Program, fields, for the organization's own fields; a program pack for the built-in ones |

If your organization is a university, an academic medical center, a nonprofit, a company, or a research institute, begin from that [starter program](getting-started.md#start-from-a-program-shaped-like-yours): it makes most of the list-shaped decisions for you, and every one can be changed.

## 2. The roles, as a program uses them

| Role | In a running program |
|---|---|
| **Member** | Everyone. Reads the catalog and keeps the applications they are named on |
| **Accountable owner** | Not a role but a name on each application: the one person who answers for it. Confirms its record and answers its assessment. Every application has exactly one |
| **Steward** | Keeps a unit's applications complete, chases what is missing, and runs campaigns for the unit |
| **Leader** | Sees a unit and everything beneath it, decides for it, and runs its portfolio reviews |
| **Architect** | Keeps the shared records (capabilities, technologies, vendors) and weighs scenarios |
| **Manager** | Runs the portfolio: decides for the units the role is held over, makes leadership reports, and, when held for the whole organization, decides anywhere and shapes the program |
| **Auditor** | Reads everything, including the full history, and changes nothing |
| **Administrator** | Runs the installation: people, sign-in, appearance, connectors, tokens, webhooks |

Keep the portfolio team small: one or two managers, an architect, and a steward in each unit that has many applications. Leaders take part through reviews.

## 3. The first ninety days

### Weeks 1 to 2: the inventory

Bring in the applications you already know from a spreadsheet ([Import applications](the-portfolio.md#import-applications)). Do not chase completeness: name, unit, accountable owner, lifecycle stage, and sourcing are enough to begin. **Portfolio → Applications** and **Reports → Data quality** show what each record lacks.

Capabilities cannot be set from the spreadsheet. They are mapped application by application, on each record's **Capabilities** tab, and until an application is mapped, whether it overlaps with another and how unique it is to the organization are unknown: it is missing from **Landscape → Overlap**, and its business value lacks the uniqueness factor. Map the applications of the pilot units first, in these weeks or alongside the first campaign.

Then turn on what other systems already know ([Facts from other systems](signals.md)): the identity provider lists applications people sign in to that are not on record (**Portfolio → Not on record**), and support dates arrive by themselves.

### Weeks 3 to 6: the first confirmation campaign

Start a **campaign** for one unit, asking each owner to confirm their records by a date (**Portfolio → Campaigns**). Owners are reminded, stewards and leaders are told what stays late, and the campaign closes each item by itself. A first campaign with one willing unit teaches more than any amount of planning; widen it once it works.

### Weeks 6 to 10: assessment

Ask the owners of tier 1 and tier 2 applications to **assess** them: nine questions, each with five described levels. An assessment alone rarely gives a recommendation. Data confidence is how much of each of the four scores' weight is known, averaged. While it is below the model's threshold (70 by default), or business value or technical health is less than half known, the rule *Not enough data* recommends *Assess*. The answers carry only part of that weight. The rest comes from the record: the tier and how many people use it, and the capabilities it serves (business value); how people sign in, its monitoring, how many people maintain it, and the technology releases its components are built on (technical health); its annual cost (cost and burden); and the classes of data it handles and its backup (risk exposure). For example, an application with the minimum to begin, a tier, its users, and a full assessment had a confidence of 48 and was recommended *Assess*; with its data classes, annual cost, sign-in, backup, monitoring, and maintainers filled in as well, 96, and *Invest*. Expect most recommendations in the first ninety days to be *Assess* until owners fill in their records, and treat each one as a list of what to fill in: the working names the missing facts that would raise confidence most. **Reports → Dashboard** shows what is recommended across the portfolio, and how confident each recommendation is.

### Weeks 10 to 13: the first review and the first decisions

Hold a **portfolio review** for one unit (**Portfolio → Reviews**), with an agenda drawn from what needs deciding: applications whose decision differs from the recommendation, decisions due again, and those with none. Decide in the room. Each decision says what to do (invest, maintain, tolerate, modernize, replace, consolidate, retire, incubate, or assess further), why, by when, and when to look again.

At the end of the quarter, make the first **leadership report** (**Reports → Leadership reports**). It is kept as it was made, so next quarter's can be set beside it.

## 4. The yearly rhythm

Once running, the program keeps a rhythm. Most of it AppWren runs by itself; people do the deciding.

| When | What | Who | Where |
|---|---|---|---|
| Continuously | Values from other systems arrive; tasks are raised when a contract's notice date nears, a release in use nears its end of support, a grant ends, or an owner leaves | AppWren | Tasks, Home |
| Continuously | Each owner confirms their records on the cadence their tier sets (by default every six months for tiers 1 and 2, every year for the rest), and renews assessments as they expire (every year for tiers 1 and 2, every eighteen months to two years for the rest) | Owners | Home |
| Every month | A portfolio snapshot keeps every application's scores | AppWren | Reports → Trends |
| Every quarter | Each unit's portfolio review decides what is due, and initiatives are updated | Leaders, managers | Portfolio → Reviews, Roadmap |
| Every quarter | A leadership report: where the portfolio stood, how it moved, what was decided, retired, and saved | Managers | Reports → Leadership reports |
| Twice a year | A confirmation campaign across every unit, to catch what slipped. A steward runs one only over their own units; one across the whole organization needs a manager for all of it | A manager for the whole organization, or each unit's steward | Portfolio → Campaigns |
| Every year | Review the program itself. In the app: the lists, the organization's own fields, the wording of the questions, and, under Scoring and cadence, each factor's weight in each profile, the thresholds, and how often records are confirmed, assessments renewed, reminders sent, and tasks raised. In a program pack: the definition of an application, the built-in sensitive fields, and the rules, guardrails, and flags. Preview any change to the scoring model before publishing it | A manager for the whole organization | Admin → Program; `appwren program export` and `import` |
| Every year | Look at the shares of the portfolio (the costliest tenth, the least used fifth) and weigh scenarios for the next year's initiatives | Managers, architects | Reports → Shares of the portfolio, Portfolio → Scenarios |

### Running a quarterly review well

- **Draw the agenda a week before** and send it to the people who own what is on it. A review of twenty applications is plenty for an hour.
- **Start with mismatches**: a decision that no longer agrees with the recommendation is either a decision to revisit or a record to correct. Both are worth the time.
- **Decide or defer, with a date.** A decision to tolerate an application for a year is a decision. Leaving it undecided is not.
- **Close the review** when it ends. It becomes a record of what was decided, and nothing in it changes after.

### From decision to done

A decision to modernize, replace, consolidate, or retire offers **Start an initiative**, which puts the change on the roadmap with an owner, dates, and a budget. A request for something new is checked against what already serves the need before anything is bought. A retirement is a plan with a checklist that ends with the application retired and its savings on record. See [Planning change](planning-change.md).

### Before committing to a large change

Build a **scenario** first (**Portfolio → Scenarios**): name the applications that would be retired, consolidated, or replaced, and AppWren works out what it would save, whom it would affect, which interfaces would stop, and which capabilities would be left with nothing. Nothing changes until it becomes an initiative. See [Insight](insight.md#scenarios).

## 5. Measures worth watching

| Measure | Read it from | What good looks like |
|---|---|---|
| Records confirmed on time | Reports → Data quality | Rising each quarter, then steady above nine in ten |
| Applications with an accountable owner | Reports → Data quality | Every one. An application nobody answers for is the first thing to fix |
| Recommendations made with low confidence | Reports → Dashboard | Falling, as assessments and facts from other systems fill in |
| Decisions that differ from the recommendation | Reports → Dashboard, Mismatches | Few, and each with a reason someone would stand behind |
| Applications past end of support | Reports → Dashboard | Falling, each with a decision and a date |
| Savings from retirements | Reports → Retirements | Recorded for every retirement, summed by year |
| How the portfolio moved | Reports → Trends | Read quarter to quarter, not day to day |

Every figure opens the list it counts. A number nobody can open is not a number to manage by.

## 6. What goes wrong, and what to do

| Sign | Likely cause | What to do |
|---|---|---|
| Owners ignore reminders | Too many at once, or the first contact was a demand | Start with one unit, explain why, and have the leader ask, not the portfolio team |
| Scores nobody believes | Thin records and old assessments | Look at the confidence first. Fill in the record and reassess before arguing with the score. Owners can contest a score with evidence |
| Reviews run long | Agendas too big, or decisions reopened every time | Smaller agendas, decisions with review dates a year out, and mismatches first |
| The inventory grows faster than it is kept | Everything counted as an application | Revisit the definition: a server, a report, or a module is a component of something, not an application |
| Decisions never happen | Nobody's job | Make one manager responsible for every review being held, every quarter |

## Next

- [Getting started](getting-started.md): install, and set up the organization.
- [Running the program](running-the-program.md): roles, who sees what, and shaping the program.
- [Adopting AppWren](adopting.md): for an organization deciding whether, and how, to take it up.
