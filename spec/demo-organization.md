# The demo organization

`appwren demo` builds a complete, fictional organization to explore: the **Bramblewood Institute for Health Research**. It exists so that anyone can see every feature working with realistic content within a minute of installing, so that every screenshot in the documentation shows the real application, and so that the test suite has an end-to-end exercise of the whole system.

Bramblewood is invented. Its people, labs, applications, and vendors do not exist, and nothing in it is taken from a real organization.

## Rules

1. **Built by the real code.** The generator does not insert rows. It calls the same services the app uses, in order, under a simulated clock: accounts are created, applications are registered and edited, owners come and go, assessments are answered, snapshots are taken, and decisions are recorded and superseded. Every record, score, and event in the demo is genuine output, and the history chain verifies.
2. **Deterministic.** The same seed produces the same organization, record for record. A different seed produces different people and details with the same shape.
3. **Relative to today.** History is generated backward from the day the demo is built, so there is always an assessment about to expire, a decision due for review, a grant ending this year, and a technology reaching end of support next quarter.
4. **Invented and unmistakably so.** Email addresses use `bramblewood.example`. Vendor and product names are made up and checked against the private-terms list. Well-known open-source technologies (programming languages, databases, operating systems) appear under their own names, because a portfolio without them would not be believable; their support dates in the demo are invented and labelled as such.
5. **Clearly marked.** A demo installation shows a "Demo data" marker on every page, and its sign-in page offers one-click sign-in as each sample person.
6. **Grows with the product.** Each wave extends the generator to cover what the wave adds. The last check of every release is that the demo shows every documented screen with data.

## The institute

Bramblewood is a mid-sized, independent, nonprofit research institute with a research clinic, about 2,000 staff, and an IT organization that has just moved its application list out of a spreadsheet.

| Area | Units |
|---|---|
| **Research divisions** | Cancer Biology · Immunology · Population Health · Computational Biology · Clinical Research |
| **Labs** | About 30, each named for its principal investigator |
| **Core facilities** | Genomics · Biorepository · Imaging · Flow Cytometry · Research Computing |
| **Clinic** | Bramblewood Research Clinic: Infusion · Clinical Laboratory · Research Pharmacy · Patient Access |
| **Administration** | Information Technology (with product and engineering teams) · Information Security · Compliance and Privacy · Sponsored Programs · Finance · Human Resources · Facilities · Communications · Philanthropy |

Units nest three and four deep, so scoped roles and roll-ups have something to show.

### People

About 180 accounts: a portfolio manager and two architects; IT leaders and division leaders; stewards for most units; product managers, engineers, and research software engineers who own applications; principal investigators and lab managers who own lab tools; and an auditor. One owner has left, so some of their applications are orphaned. Sample accounts for each role are listed on the demo's sign-in page.

### Scale

Enough to look like an organization that has used AppWren for a year, and small enough to build in under a minute. Wave 1 figures:

| Records | About | Notes |
|---|---|---|
| Org units | 57 | Four levels, including IT teams and 24 labs |
| Accounts | 180 | Every role represented; one who has left |
| Capabilities | 43 | The default program's starter map |
| Vendors | 30 | Software companies, service providers, open-source projects, a consortium, a partner university |
| Technologies | 24 | Languages, frameworks, databases, operating systems, platforms; each with releases and invented support dates |
| Applications | 107 | Every sourcing type and tier, most lifecycle stages, and about forty research tools kept by labs |
| Components | 120 | Most built and commercial applications decomposed; most SaaS with none |
| Interfaces | 24 | Clinical messages, feeds to the warehouse, files between administrative systems, and one re-keyed by hand |
| Hosting platforms | 6 | A data center, a standby site, two cloud accounts, a research cluster, and lab workstations |
| Deployments | 87 | Production for everything the institute runs itself; staging for tiers 1 and 2; a standby for tier 1 in the data center |
| Assessments | 125 | Re-assessments over time; some expired; a dozen applications never assessed |
| Decisions | 70 | Some superseded; several mismatches with today's recommendation; some due for review |
| Portfolio snapshots | 4 | Quarterly, for the last year |
| Events | about 2,000 | All verified by `appwren verify` |

### Storylines

Hand-written situations, each asserted by a test, so that every wave 1 screen has something worth reading:

- **The worked example.** *Specimen Tracker* produces exactly the figures in [engine.md](engine.md#a-worked-example): Modernize, with three flags.
- **Three tools for one job.** Three survey tools serve *Participant surveys*: the survey hub is the primary; an old in-house tool is recommended for consolidation into it, and the decision agrees; the clinic's questionnaires are recommended for consolidation too, but the decision on record keeps them, for a reason the scores cannot know.
- **The grant ends.** A lab's imaging pipeline, paid for by a grant that ends in five months, with no decision recorded.
- **The single maintainer.** A tier 2 analysis platform kept by one research software engineer.
- **The incubator.** A pilot of a new electronic lab notebook, in Evaluating, recommended *Incubate*.
- **The mismatch.** A commercial scheduling system recommended *Replace*; the decision on record is *Maintain* until a contract ends, with a review date next month.
- **The orphan.** Four applications whose accountable owner left, flagged and listed on the steward's home page.
- **Not enough to say.** A dozen applications recorded from the spreadsheet import with no assessment, recommended *Assess*, each showing what would raise its confidence.
- **The end of support.** A database release used by a dozen components reaches end of support next quarter.
- **The data nobody recorded.** The research data warehouse sends enrollment figures, with identifiable research data in them, to the executive dashboards, whose record lists only financial data. The flow view marks it.
- **Retired properly.** An old reporting tool retired last year, with its decision, its successor, and its history.
