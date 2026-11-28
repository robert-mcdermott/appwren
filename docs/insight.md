# Insight

This guide is for the portfolio team and for leadership: those who ask how the portfolio is moving, where its cost and use are concentrated, and what happened over a quarter. It covers trends between snapshots, an application's scores over time, shares of the portfolio, leadership reports, the record as it stood on a past day, scenarios, and the optional assistant.

Everything here is read from what AppWren already keeps. A portfolio snapshot keeps every scored application's scores as they were ([Portfolio snapshots](running-the-program.md#portfolio-snapshots)); a decision keeps the scores it was made on; and a leadership report, once made, keeps every figure in it. None of it is worked out again later from the records as they have since become.

## Trends

**Reports → Trends** puts two portfolio snapshots side by side, or one snapshot and today. For each it shows how many applications were scored, how many by recommendation, how many with low confidence, and the average of each score. Between them it lists:

| What moved | What it means |
|---|---|
| Recommendation changed | Today's recommendation, or the later snapshot's, differs from the earlier one's |
| Scores moved | A score rose or fell by half a point or more |
| Flags raised or cleared | A flag came or went |
| Added or gone | Scored in one and not the other |
| Decided between them | Every decision recorded after the earlier snapshot was taken, up to the later one |

![Trends between two quarterly snapshots: the figures each held, and the applications whose recommendation changed](img/trends-light.webp)

Each person sees what they may see: an application they cannot open is neither listed nor counted.

An application's **Scores** part shows its scores over time, a point for each portfolio snapshot and each decision, as a picture and as a table.

## Shares of the portfolio

**Reports → Shares of the portfolio** names the applications at one end of the portfolio in service:

| Share | Ranked by |
|---|---|
| The costliest tenth | Annual cost |
| The dearest tenth per user | Annual cost for each person who uses it |
| The least used fifth | Its count of users |
| The oldest fifth | Years since it went live |

Each share is worked out from the applications that have the figure it ranks by, and says how many do not. A share says where an application stands against the rest, not whether it costs too much or is used too little: that is for the scores and their defined bands ([The scores](the-portfolio.md#the-scores)), and a share never feeds a score. Cost is left out for anyone who may not see it.

![Shares of the portfolio: the costliest tenth and the least used fifth, each with the figure it was ranked by](img/shares-light.webp)

## Leadership reports

A **leadership report** says, for a period, where the portfolio stood and what happened in it. A manager makes one under **Reports → Leadership reports**, with a title and a period that has ended, often the last quarter (which is suggested). It holds:

- **Where the portfolio stood** when it was made: the applications in service, what they cost together (for those who see every cost), how many by recommendation and by decision on record, what needs attention, the flags raised, and engineering maturity.
- **How the scores moved**: from the last portfolio snapshot before the period, or its first, to its last, with the change in each average score and how many applications changed recommendation, moved on a score, or raised or cleared a flag.
- **The decisions in the period**, by what was decided, and how many went another way than recommended.
- **The reviews closed in it**, the initiatives under way (and any past their end) and done, the requests for something new, and the applications retired in it, with what they save a year.

A report is **worked out once, when it is made, and kept whole**. Reopening it reads what was kept, never the records as they are now, so a report read a year later says what it said then. Its **digest**, the SHA-256 of what it holds, is printed at its foot and checked whenever it is opened; a report that no longer matches says so.

![A leadership report for a quarter: its figures, where the portfolio stood, and how the scores moved](img/report-light.webp)

**Print** prints the report without the menus and buttons. Reports are read by those who may see every record (managers, auditors, and administrators), as they name applications from across the organization.

## As of a day

**Reports → As of a day** shows the applications that were in service at the end of a chosen day (the end of the last quarter, unless another is chosen): each as it was named then, its unit and stage then beside its stage now, and the decision on record then beside the decision now. It says how many have come into service since and how many have left.

Nothing is kept for this. Every change to a record is in its history with the values before and after, and the record on a day is those changes, up to the end of that day, applied in order. The decision on a day is the one recorded last by then; the scores are those of the nearest portfolio snapshot taken on or before it.

An application's **History** part offers **As it stood on a day**: each of its values then beside its value now, those that have changed first, the decision on record then, its scores in the snapshot of the time, and how many changes have been made since. A value someone may not see now, such as cost, is not shown for then either.

![An application as it stood half a year ago: its scores then, and each value then beside its value now, those that changed first](img/application-as-of-light.webp)

## Scenarios

A **scenario** asks what a set of changes would do before anyone commits to it. It is a record of its own (`SCN-0001`) under **Portfolio → Scenarios**, kept by architects and managers and read by everyone. **Edit the changes** names the applications and what would happen to each:

| Change | What it means |
|---|---|
| **Retire it** | It goes, and nothing takes its place |
| **Consolidate it into** another | Its users and work move onto an application that stays |
| **Replace it with** another | An application on record, in service or proposed, takes its place |

Its page then says what that would do, worked out from the records as they are each time it is opened:

| Effect | Worked out from |
|---|---|
| **Saved a year** | The annual cost of the applications that would go, before the cost of anything that takes their place. Only for those who may see what they cost |
| **People whose application would change** | Their counts of users |
| **Interfaces that would stop** | Each interface between an application that would go and one that stays, other than the one its work moves into |
| **Capabilities left with nothing** | Each capability that only the applications going serve, among those in service |
| **The risk that would go with them** | Each one's risk exposure and the warnings and dangers flagged on it today |

![A scenario: six labs' image analysis consolidated into the imaging core's pipeline, and what it would save and whom it would affect](img/scenario-light.webp)

**A scenario changes nothing.** No application's record, decision, or stage moves while it is built or changed. When it is agreed, **Make an initiative of it** adds a proposed initiative ([Initiatives and the roadmap](planning-change.md#initiatives-and-the-roadmap)) named after it, retiring the applications it takes away and moving their work onto those that take their place. The scenario keeps a link to the initiative, and changes no more.

## The assistant

If your organization has set one up ([`[assistant]`](configuration.md#assistant)), **Portfolio → Assistant** offers two things. Otherwise neither the page nor the menu entry is there.

The model may be one your organization runs on its own machines, a hosted service, or one on Amazon Bedrock: any server that speaks the chat completions interface, the messages interface, or Bedrock's Converse API.

- **Ask about the portfolio.** A question in your own words, such as *which applications handle participant consent, and what was decided about them?* The answer cites the applications it relies on, each a link to its record.
- **Draft an application from a document.** Paste a description (from a vendor's page, a proposal, or a design document) and the assistant fills in what it says: the name, a summary, sourcing, who uses it, how many, the data it handles, sign-in, and the like. Read and correct each value, choose the unit that answers for it, and add it yourself. A value the form would not take is left out, and named.

What the assistant is given is limited. It is told only of applications in service that you may see, and none that handle data more sensitive than the configuration allows. It changes nothing: an answer is read, and a draft is a form for you to finish. A reference it cites that it was not told of is not linked. Every exchange is kept, with what was sent and what came back, for a year unless the configuration says otherwise, and those who may see everything can read them.

The configuration may open the assistant to some roles only, and limits how often each person may ask in a day (a hundred times, unless it says otherwise). Past the limit, the assistant says so and answers again the next day. Each person has one question at a time waiting for an answer. When the model's server refuses a request, you are told that it did; why is kept with the exchange for an administrator.

## Next

- [Running the program](running-the-program.md#portfolio-snapshots): taking portfolio snapshots.
- [The API](api.md#insight): the routes for trends, shares, and reports.
