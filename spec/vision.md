# Vision

## The idea

A wren is one of the smallest birds in the garden and one of the most watchful. It knows every gap in the hedge, every branch that will bear its weight and every one that is about to break.

That is what most organizations want to know about their software and rarely do. Ask how many applications they run and the answer is a range. Ask who answers for a particular one and the answer is a name that left two years ago. The list that exists is a spreadsheet that was accurate the week someone built it. Nobody can say which systems hold patient or participant data on software the vendor stopped supporting, which three tools do the same job in three departments, or which small application, written by one person in a lab, has quietly become something forty studies depend on. Budget conversations about what to fund, what to keep, and what to switch off are had from memory.

The tools sold to fix this belong to large architecture practices. They take months to set up and a specialist to run, they ask owners to fill in long surveys, and the people who actually build and run the software never open them.

**AppWren is the smaller, sharper alternative.** It gives an organization one living record of every application it runs, who answers for it, what it is for, what it is built on, what it costs, and how healthy it is, and it turns that record into an explainable recommendation for each application: invest, maintain, tolerate, modernize, replace, consolidate, or retire. It runs on one machine, works on its first day with a sensible program already loaded, asks owners for the least it can, and keeps a history that a review board can rely on.

## Positioning

> AppWren is an open system of record for application portfolio management: know every application, who answers for it, and what to do with it, with the reasoning on the screen.

AppWren manages the *portfolio*: the inventory of applications and their parts, the capabilities they serve, the people and teams who own and use them, the technology they rest on, their cost, their assessments and scores, and the decisions made about them. It is **quiet by default**: everything it knows comes from people, from imported files, and from what other systems push to it, and an administrator may turn on read-only connectors one at a time ([ADR-0003](decisions/0003-quiet-by-default.md)).

## Who it is for

AppWren works for any organization with more applications than anyone can keep in their head, roughly fifty or more. It is built with particular care for **research and health organizations that are not large corporations**: independent research institutes, academic medical centers, universities, teaching hospitals, and the nonprofits around them. Their portfolios have a shape that general tools handle badly:

- **Software from everywhere.** Software-as-a-service subscriptions, commercial products run on site, systems built by central IT, open-source tools, and a long tail of **research software** written and kept by labs, cores, and individual scientists. All of it needs to be on the same map, judged by rules that fit what it is.
- **Many semi-autonomous groups.** Dozens or hundreds of labs, departments, and divisions, each choosing and paying for its own tools. Central IT does not own everything that matters, and the portfolio must be kept by the people closest to each application.
- **Sensitive data in unexpected places.** Patient information, identifiable research data, and controlled-access datasets turn up in lab tools, spreadsheets turned into databases, and vendor products nobody reviewed. Knowing which applications handle which data, on what technology, is the first step to protecting it, and to answering an auditor.
- **Money that ends.** Applications paid for by a grant need a decision before the grant does: who sustains it, who pays, or how it is wound down without losing the data.
- **One person who knows how it works.** Research software in particular is often kept by a single developer or a graduate student. That is a risk to every study that relies on it, and it is invisible until they leave.
- **Small central teams.** A handful of architects, product managers, or IT leaders covering hundreds of applications, with no budget for a specialist to run the tool.

**Engineering and product teams come first.** The first people to adopt a portfolio system are usually the product, application, and software engineering teams responsible for a set of applications, and the IT leaders they report to. So their path has to be right before anything else: registering an application in minutes, seeing what they owe on one page, getting objective signals from the tools they already use instead of answering surveys, and seeing scores they can understand and contest. The rest of the organization joins the same record.

Nothing in AppWren is specific to research or health care. Vocabularies, fields, questions, scoring profiles, rules, and branding are all configuration, and any organization that wants a lightweight, self-hosted portfolio system can adopt it.

| Persona | What they need from AppWren |
|---|---|
| **Software or application engineer** | Updates that take seconds, or happen from the tools they already use; a clear view of end-of-life and maturity work on what they maintain |
| **Application or product owner** | A page of their applications and what each needs; scores with explanations; a way to contest a score with evidence; their roadmap linked to the portfolio |
| **Unit or department steward** | Their unit's applications, who owns each, and a simple way to confirm the list is complete |
| **Solutions or enterprise architect** | The capability map, overlaps, the technology in use and its lifecycle, the dependencies between applications, and what breaks if one goes |
| **Portfolio manager** | A record they can trust, a scoring model they control, recommendations they can take to a review, and decisions recorded with their reasons |
| **IT leader or executive** | The portfolio by disposition, cost, and risk; the decisions pending; what changed since last quarter; exports for budget and roadmap planning |
| **Security and compliance** | Which applications handle which data, on which technology, with what sign-in, and which are past vendor support; evidence for the yearly risk analysis |
| **Finance and procurement** | What each application costs and who pays; grants and contracts coming to an end; savings from retirements |
| **Service desk and operations** | Who supports an application, how critical it is, and where its runbooks are |
| **Researcher or staff member** | Find the approved application for a need, see who supports it, and ask for something new |
| **Administrator at an adopting organization** | A system that installs in minutes, signs people in with the identity they already have, carries the organization's name and colors, and keeps its data portable |

## What makes AppWren different

These are the product bets. Each is a deliberate design choice.

1. **The reasoning is on the screen.** Every score shows its factors, their levels, where each came from, the weights, and the arithmetic. Every recommendation shows the rule that produced it. Anyone can redo the working by hand ([ADR-0011](decisions/0011-recommendations-advise.md)).

2. **People decide.** The system recommends; a named person decides, with a rationale and a date to look again. When the recommendation and the decision differ, both are shown, and the difference is a prompt for discussion, not an error.

3. **Unknown is not zero.** A missing answer is shown as missing and counted against confidence, never assumed. Below a confidence threshold the recommendation is *Assess*: complete the record first. Old answers expire. A recommendation is never made from data nobody has checked.

4. **One definition of an application.** Applications, their components, and their deployments are different records ([ADR-0013](decisions/0013-applications-components-deployments.md)), so the portfolio counts like with like and technical detail does not swamp it.

5. **Judged by the right rubric.** A pilot is not judged like a fifteen-year-old system of record, nor a shared platform like a departmental tool. Lifecycle stage, purpose, and pace choose the scoring profile and the rules. New work is *Incubated*, not condemned for having few users.

6. **Objective signals first.** Wherever a fact can be measured (end-of-life dates, maintainers, sign-in method, monitoring, users, cost, code activity) it is a field, not a survey question, and from wave 4 it can arrive by itself from the tools that already know it. Questions are kept for what only a person can judge, and each has a definition for every level.

7. **Research-ready.** Funding source and grant end dates, research continuity, data classes for identifiable and de-identified research data, external collaborators, and single-maintainer risk are part of the default program, with guardrails that flag them: a grant ending without a sustainment decision, restricted data on unsupported technology, a critical tool that one person keeps.

8. **Built for federated organizations.** Units form a hierarchy of any depth. Every application belongs to a unit, has exactly one accountable owner and named people in other roles, and is kept by the people closest to it. Leaders see roll-ups; stewards see their own unit; nobody at the center retypes anyone's records.

9. **Kept current by design.** A home page of what each person owes, attestations on a cadence in proportion to criticality, triggers when an owner leaves or a contract or grant ends, and data confidence on every page. A portfolio that goes stale says so.

10. **An unbroken history.** Every change to every record is written to an append-only log, chained by hash, with who, when, and what changed. Assessments and decisions are never edited, only superseded. The portfolio can be shown as it stood on any past date.

11. **Quiet by default.** No discovery scanning, no agents, and no outbound connections unless an administrator turns on a specific read-only connector. Safe to deploy anywhere and quick to approve, which matters for a system that holds a map of every application and its weak points.

12. **Open, portable, and yours.** Apache 2.0 licensed, with no paid edition. Runs on a laptop with SQLite or on a server with PostgreSQL. Everything exports in open formats. Name, logo, colors, and wording are settings, so an adopting organization presents it as its own.

## Scope

### AppWren does

- Keep an inventory of applications, their components and deployments, the vendors behind them, and the technologies they are built on, with owners, criticality, lifecycle, and links
- Map applications to a hierarchy of business capabilities, and show overlaps and gaps
- Record who answers for each application: exactly one accountable owner, and people in other named roles
- Record which units and groups use each application, how many people, and what depends on it
- Record the integrations between applications and the classes of data each carries
- Record technologies with their versions and support dates, and say what is approaching or past end of life
- Record cost and funding: what each application costs, who pays, and when contracts and grants end
- Assess applications with short, defined questionnaires, and combine answers with measured facts into explainable scores for business value, technical health, cost and burden, and risk exposure, with a data confidence figure
- Recommend a disposition for each application through ordered, configurable rules and guardrails, and record the disposition people decide, with its rationale
- Keep the record current with attestations, campaigns, reminders, and triggers
- From wave 4, take in facts from other tools through connectors an administrator enables, and through a push API
- Plan change: initiatives, roadmaps, intake of new requests, and a retirement playbook
- Report the portfolio to leadership with figures that explain themselves, trends, scenarios, and exports

### AppWren does not (non-goals)

- **Discover applications by scanning.** No network, device, or cloud-account crawling, and no agents. Connectors read named sources an administrator chooses; they never look for things on their own.
- **Replace other systems of record.** It is not a configuration database, a ticketing system, a contract system, a project-management tool, a source-code host, or a monitoring system. It records what the portfolio needs from them and links to them by reference.
- **Hold infrastructure detail.** Servers, network devices, and their configuration belong in an infrastructure inventory. AppWren records where an application runs, not how the machine is built.
- **Manage software licenses seat by seat.** It records what is bought and what is used, for each application; it does not allocate seats to people.
- **Make decisions on its own.** It recommends and records. It never changes a disposition, retires an application, or changes another system.
- **Hold the sensitive data it describes.** Records describe applications and the classes of data they handle; they never contain that data.
- **Require an AI provider.** Optional assistance may come later; the core never depends on one.

## Guiding principles

1. **The least that proves it.** Every screen is judged by how little it asks of an honest person to leave a trustworthy record.
2. **Describe once.** A vendor, a technology, or a capability is described in one place and linked everywhere else. Anything AppWren already knows is never asked again.
3. **Show the reasoning.** A score, a recommendation, or a due date always shows the rule and the inputs that produced it.
4. **People decide.** Rules propose; named people decide.
5. **The record is permanent.** History is append-only. Corrections are new entries, never erasures.
6. **Stand alone.** Every capability works on one machine with no other system. Integrations are optional additions.
7. **Few dependencies, well chosen.** Each runtime dependency is justified in a decision record. The browser gets no frameworks.
8. **Generic by default.** Nothing in the code or documentation assumes a particular institution. Vocabulary and branding are configuration.
9. **Accessible and fast.** WCAG 2.2 AA, keyboard-friendly, light and dark themes, and pages that load instantly on modest hardware.
10. **Unknown is not zero.** A missing answer is shown as missing, a stale one as stale, and nothing is assumed.

## What success looks like

- **Wave 1:** A portfolio manager installs AppWren, signs in, imports the organization's application list from a spreadsheet, and within an afternoon has owners, capabilities, and technologies recorded. Owners answer a short assessment. The portfolio chart places every application with its scores and confidence, each recommendation opens to its working, and the first decisions are recorded with their reasons.
- **Wave 2:** An architect sees the landscape: what depends on what, which data flows where, which capabilities are served three times, what each application costs and who pays, and what breaks if one is retired.
- **Wave 3:** The portfolio keeps itself current. Owners attest on schedule, departures and contract and grant ends raise tasks, and stale records lower confidence where everyone can see it.
- **Wave 4:** Most technical facts arrive by themselves from the tools that already know them, labelled with their source.
- **Wave 6:** A leader opens one report and sees the portfolio by disposition, cost, and risk, what changed since last year, and what a proposed set of retirements would save and break.
- **v1.0:** Another organization adopts AppWren, re-brands it, connects single sign-on and its own tools, loads its own program, and runs its portfolio reviews on it without help from the original team.
