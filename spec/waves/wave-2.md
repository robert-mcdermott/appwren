# Wave 2: The landscape (v0.2.0)

**Goal:** see each application in its surroundings: what it talks to and what data passes, where it runs, what it costs and who pays, what else does the same job, and what breaks if it goes. Wave 1 made each application's record trustworthy on its own; this wave connects the records, so that the questions a portfolio review actually asks ("what else touches this data?", "what goes down with it?", "what are we paying twice for?", "what falls out of support next year?") are answered from the screen.

**Branch:** `wave-2` · **Target version:** `0.2.0` · **Status:** ◐ in progress

## Exit criteria

The wave is done when, on a fresh checkout and on an installation upgraded from 0.1.0:

1. An owner records an interface between two applications with its direction, method, frequency, owner, and the data classes it carries; each application shows what it sends and receives; and a view shows every flow of a chosen data class, marking any application that receives a class its own record does not list (LND-03).
2. Any application, component, capability, technology, vendor, or hosting platform opens a focused picture of what it is connected to, usable from the keyboard and matched by a list that says everything the picture does (LND-04).
3. *What breaks if this goes* lists, for an application: what depends on it directly and beyond, the interfaces that would stop, the capabilities left with no provider, and the people and units affected (LND-04).
4. An application and its components are recorded as deployments in environments on hosting platforms; a platform shows everything that runs on it (LND-05).
5. An application's cost is recorded in lines by category and funding source, and the lines add up to its annual cost; contracts record the vendor, the applications covered, the term, renewal and notice dates, auto-renewal, licenses bought and used, and whether a data agreement is in place; renewals whose notice date is near are listed (CST-03, CST-04).
6. Cost per user and license use are factors of cost and burden, with their working; the worked example in [engine.md](../engine.md#a-worked-example) is updated and still produced exactly (CST-05).
7. Cost lines, contracts, and funding are withheld exactly as annual cost is: in records, lists, filters, exports, and the working (PLT-14).
8. Capabilities served by more than one application are listed with their applications' scores, costs, and decisions side by side (LND-06); the capability map can be colored by any score, by confidence, or by how many applications serve each capability (LND-07).
9. A timeline shows technology releases against their end of support, with the applications on each, and applications against their planned retirement (LND-08); the radar shows technologies by ring and kind with how many components use each (LND-09).
10. Support dates are imported from a file by an architect, with a dry run that says what would change (LND-08).
11. An export lists the applications that handle a chosen data class, with owners, versions, hosting, sign-in, and support status, withholding what the reader may not see (RPT-07).
12. An external reference is shown as a link where the program gives its system an address pattern (INV-16).
13. Those who may read everything browse every change in one place, narrowed by person, record, kind, and date (INV-18).
14. Upgrading a 0.1.0 installation keeps every row and file, and adds what is new in the default program without overwriting what the organization shaped.
15. The demo organization shows every new screen with convincing data, and its storylines still hold. The accessibility audit and keyboard check pass; lint and the private-terms check are clean; the suite passes on both databases.

Requirements delivered: LND-03 to LND-09; CST-03 to CST-05; RPT-07; INV-16, INV-18.

## Decisions needed from the maintainer

None block the start. These defaults have been taken and can be changed before the slice that depends on them:

- **A consumer depends on its source.** An application that receives data through an active interface counts among the dependents of the application that sends it, as a *depends on* link does (slice 1).
- **Interfaces are open like the catalog.** An interface is visible to whoever may see both of its applications, and kept by whoever may edit either (slice 1).
- **Environments** are a vocabulary: production, staging, test, development, and disaster recovery (slice 3).
- **Cost lines win.** Once an application has cost lines, its annual cost is their sum and is no longer typed in (slice 4).
- **Contracts are sensitive as a whole.** A contract is visible to managers, architects, auditors, and administrators, and to anyone who may see the sensitive fields of an application it covers (slice 4).
- **New factor weights for cost and burden:** annual cost 30, cost per user 15, license use 10, support effort 25, change effort 20. License use applies only where licenses bought are on record (slice 4).
- **End-of-life data comes from a file** in this wave, never from the network; the connector is wave 4's ([ADR-0003](../decisions/0003-quiet-by-default.md)) (slice 6).

---

## Slice 1: Interfaces and data flows ☑

**Goal:** what each application sends and receives, and where each class of data travels.

- [x] `interface`: a record of its own with a permanent reference, the application data comes from and the one it goes to, method, frequency, the data classes carried, an owner, a summary, and a status; vocabularies for method and frequency
- [x] Visibility and editing follow its two applications; a restricted application's interfaces are hidden with it
- [x] The application's page gains a **Connections** part: what it sends, what it receives, with the other end, method, frequency, and classes
- [x] The engine's *dependents* counts applications that receive its data
- [x] **Landscape → Data flows:** every interface carrying a chosen data class, and a mark where the receiving application's record does not list the class
- [x] Export of interfaces; the demo's interfaces; changelog entry (the guide is written in slice 8)

**Acceptance (met):** an interface appears on both applications and has its own history, which names the applications and people by name; a member, and a steward who keeps the other end, see none of a restricted application's interfaces, in lists, flows, counts, or exports, and naming an application one may not see fails exactly as naming one that does not exist; the worked example still has exactly three dependents; the flow view for a class lists exactly the interfaces the list gives for it.

**Done:** interfaces are a record type like any other, so lists, filters, export, history, and optimistic concurrency came with the registry. The access rules now ask a record type which applications it belongs to, where they asked whether it was a component. The demo has 24 interfaces, one of them re-keyed by hand each morning and one delivering identifiable research data to dashboards whose record lists only financial data.

## Slice 2: Dependency graph and impact ☑

**Goal:** the picture around any record, and an honest answer to *what breaks if this goes*.

- [x] One function that gathers a record's neighbors: links, interfaces, capabilities, components and their technologies, vendor, and succession; filtered by what the reader may see, with the rest counted. Later slices add platforms, contracts, and funding to it
- [x] `/graph/{ref}`: the focused picture, one ring out, with any neighbor opened a ring further; drawn as SVG, reachable and operable from the keyboard, with a list beside it that holds everything the picture does
- [x] **What breaks if this goes** on the application's Connections part: direct and transitive dependents, interfaces that stop, capabilities left with no active provider or without their primary, the people and units affected, and what its record says must outlive it
- [x] The keyboard check covers the picture

**Acceptance (met):** the list beside the picture always has as many records as the answer, and the keyboard check holds it so; nothing a reader may not see appears as a node, a row, or a name, in the picture or in the impact, and is counted instead; a loop of dependencies ends; impact for the worked example names its three dependents and the capability it alone provides.

**Done:** every kind of record has a picture, seen from its own side: an application's dependencies, flows, capabilities, parts, technologies, vendor, and what it replaced; a technology's components; a vendor's applications; a capability's providers. Impact follows the same rule the engine counts dependents by, ring by ring, and adds up the people who use anything it reaches as an upper bound.

## Slice 3: Deployments and hosting ☑

**Goal:** where everything runs.

- [x] `hosting_platform`: a shared record (a data center, a cloud account, a vendor's service, a cluster), kept by architects, with kind, provider, and location
- [x] `deployment`: an application, or one of its components, in an environment on a platform, with an address; named for what runs and where unless someone names it
- [x] The application's Components part gains **Where it runs**; a platform's page lists what runs on it, by environment
- [x] Platforms join the picture: an application runs on them, they host applications, and a vendor provides them
- [x] The demo's platforms and deployments; export; changelog entry

**Acceptance (met):** a deployment is visible exactly when its application is; a platform's page and its row in the list count only what the reader may see; a test holds the platform's list equal to the deployments list filtered by it, for every role; a component on a deployment must belong to its application; a retired platform takes nothing new.

**Done:** two more record types on the registry, with their lists, filters, exports, and histories. The demo has six platforms and 87 deployments: what the institute runs itself has production, tiers 1 and 2 have staging, and tier 1 systems in the data center have a standby at a provider. What vendors host has none.

## Slice 4: Cost, funding, and contracts ☑

**Goal:** what each application costs, who pays, and what is about to renew.

- [x] `funding_source`: a shared record (an operating budget, a grant, a chargeback, a capital project) with a code and, for a grant, an end date
- [x] `cost_line`: a yearly amount on an application, by category, with its funding source and an optional contract; the application's annual cost is the sum of its lines once it has any
- [x] `contract` and `contract_application`: vendor, number, term, notice period, auto-renewal, yearly value, licenses bought, a data agreement's standing, and the applications covered with the licenses each uses
- [x] Sensitive throughout: one function decides, and records, lists, history, exports, the picture, and the working call it
- [x] The engine: *cost per user* and *license use* as factors of cost and burden; a new version of the default scoring model; the worked example updated in the specification and in the test
- [x] An upgrade publishes the new default model only where the organization still runs the previous default unchanged
- [x] **Portfolio → Contracts:** renewals and notice dates ahead; flags for a notice date within 90 days and for a missing data agreement where confidential or restricted data is handled
- [x] The dashboard gains cost by category and by what pays, for those who see every application's cost
- [x] The application's page gains a **Cost** part; the demo's funding, lines, and contracts; exports; changelog entry

**Acceptance (met):** the sum of an application's lines is its annual cost in the record, the list, and the working, and a different figure typed in is refused; a member sees no line, contract, funding figure, cost-line event, or cost factor they could not see as annual cost; a contract seen through one application does not name another the reader may not see; the worked example produces the specification's figures to the decimal (cost and burden is now 2.7); an installation running 0.1.0's model unchanged gets the new one on upgrade, and one that has shaped its model keeps it.

**Done:** cost has a part of its own on the application's page, with the figure, the cost for each person who uses it, the lines, and the contracts that cover it. Contracts list what ends when and how soon the vendor must be told. The demo has 22 contracts and about 200 cost lines; its three storylines are a notice date two weeks off, health data with no data agreement, and five thousand licenses of which fourteen hundred are used.

## Slice 5: Overlap and the capability heat map ☑

**Goal:** where the organization pays twice, and where it is thin.

- [x] **Landscape → Overlap:** every capability with more than one application in service, its applications side by side with scores, recommendation, decision, users, and cost where visible; the primary named; totals for the capability
- [x] The capability map measured by a chosen measure: how many serve it, any of the four scores (the average of its applications), data confidence, or the lowest technical health; each figure in words as well as in its bar
- [x] Each figure opens the list it counts: the portfolio list narrowed by capability

**Acceptance (met):** the overlap page's applications for a capability equal the portfolio list filtered by it, for every role; a total of cost is given whole or not at all; the map says in text everything it says with a bar; a broader capability counts each application beneath it once; the three survey tools appear together with the hub as primary.

**Done:** both views are drawn from the portfolio list, with a new filter by capability that every list and export also takes. The demo has 17 capabilities served more than once.

## Slice 6: Technology lifecycle ☐

**Goal:** what falls out of support, and when.

- [ ] **Landscape → Lifecycle:** a timeline of technology releases to their end of support, each with how many components and applications are on it, and of applications to their planned retirement; with a table of the same
- [ ] **Landscape → Radar:** technologies by ring and kind, each with how many components use it, and those in use with no ring
- [ ] End-of-life data from a file: `appwren technologies import-eol FILE` and the same from the Technologies page, matched by each technology's key in the file, with a dry run that lists every date that would change; releases added, dates updated, nothing removed
- [ ] Guide and changelog entries

**Acceptance:** the timeline's counts equal the technology pages'; an import run twice changes nothing the second time; a date a person typed is replaced only when the file disagrees, and the change is in the history with the import named as its source.

## Slice 7: Exports, external references, and the whole history ☐

**Goal:** the evidence other processes ask the portfolio for.

- [ ] **Reports → Data handling:** the applications that handle a chosen data class, with accountable owner, sourcing, hosting and platforms, sign-in, technologies and their support, interfaces carrying the class, and the data agreement's standing; as a page and an export, withholding what the reader may not see
- [ ] External references shown as links where the program gives the system an address pattern; patterns checked when a pack is loaded
- [ ] **Reports → History:** every change in one place for managers, auditors, and administrators, narrowed by person, record, kind of record, action, and dates; sensitive values withheld as on a record

**Acceptance:** the data-handling list equals the applications list filtered by the class, for every role; a pattern can only produce an `https` address; the history page shows nothing a record's own history would withhold.

## Slice 8: Release prep ☐

- [ ] Guides: a new guide, *The landscape*; cost and contracts added to *The portfolio*; *Running the program*, the API guide, and the index updated; screenshots retaken
- [ ] `README.md` and `CHANGELOG.md` for 0.2.0
- [ ] The accessibility audit and keyboard check over every screen, old and new
- [ ] Upgrade from 0.1.0 checked on both databases: every row and file kept
- [ ] Fresh-clone install and quickstart checked on both databases
- [ ] Version `0.2.0`; pull request from `wave-2`; tag and release

## Notes

Decisions and discoveries made during the wave are logged here, newest last.

- **Access asks the record, not its type.** Who may see and keep a record was decided by asking whether it was an application, a component, or shared. An interface has two applications, and deployments, cost lines, and contracts are coming, so a record type now says which applications it belongs to: it is seen by whoever may see all of them and kept by whoever keeps any.
- **Undeclared data is marked, not fixed.** An interface that carries a class its receiver's record does not list is a disagreement between two records, and AppWren cannot know which is wrong. It marks the interface and the flow, and says what it costs: the receiver's exposure is worked out from what its record lists.
- **History names what an id points to.** A change to a vendor, a successor, or an owner was told as a number. Fields that hold another record or a person are now told by name, for every record type.
- **A record's parts are few.** Interfaces, dependencies, and (next) impact share one part of the application's page, Connections, where a part each would have made eleven.
- **Impact and the score follow one rule.** What depends on an application is worked out once: a recorded dependency, or receiving its data. The engine counts it for business value, and impact walks it outward, so the number in the working and the list on the page cannot disagree.
- **People affected is an upper bound, and says so.** The users of an application and of everything that depends on it are added together; the same person may use several. The page says "up to".
- **Where it runs sits with what it is made of.** Deployments are shown on the application's Components part: a component is what runs, and a deployment is where. A part of its own would have been an eighth for two short tables.
- **A deployment names itself.** Nobody wants to type "Tracker API, production". A record type may now say how to name a record that arrives without a name.
- **The sum is kept on the application.** An application's annual cost stays a column, written as the sum of its lines whenever they change, so every list, filter, sort, chart, and the engine go on reading one figure. Lines that add up to the figure already there change no score.
- **A contract's visibility is its own rule.** A contract belongs to several applications in different units, and is not seen by all who see them: it needs someone who may see the cost of one. Record types may now give a rule of their own for who sees and keeps them.
- **Cost breakdowns are for those who see all of it.** A total over applications a reader may see only in part would let them work out the rest, so the dashboard's cost figures are given whole or not at all.
- **License use is the contract's.** A contract's licenses in use are added up over every application it covers, and each of them is judged by that share: an application cannot be efficient with licenses its neighbor wastes.
- **An upgrade respects a shaped model.** The new default scoring model replaces only an earlier default that nobody changed, recognized by its digest. A test holds the 0.1.0 model's digest against the list.
- **Buttons in cards say what they edit.** "Edit" beside "Edit" on one page failed a scene and would fail a person using a screen reader's list of buttons.
- **A heat map without heat.** The capability map shows each figure as a number with the score's own bar, as everywhere else, where a block of color would have said less and asked more of the eye. "Weakest health" is offered beside the average: a capability is as exposed as the worst thing that serves it.
