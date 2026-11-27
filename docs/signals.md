# Facts from other systems

This guide is for administrators who connect AppWren to the tools the organization already runs, and for everyone who reads what those tools supply. It covers connectors, values from other systems and overriding them, applications found that are not on record, push sources, catalog files, engineering maturity, and how all of this joins the scores.

## Nothing is connected until you connect it

A new installation makes no connection to anything. Each source is switched on separately, by an administrator, for one named source:

- A **connector** reads a source on a schedule: support dates, what the repositories know, who signs in.
- A **push source** is one of your own tools posting facts to AppWren with a key you issue.
- A **catalog file** is kept beside the code and imported by whoever keeps the application.

Whatever arrives is marked with where it came from, recorded in the history like any other change, and never wins over a person: anyone who keeps the record can override it, with a reason.

## Connectors

**Admin → Connectors** lists the connectors set up, their recent runs, and the kinds of source AppWren can read. Choose **Add** beside a kind, name it, and give what is not secret (an address, an organization, a tenant). It is added switched off. Choose **Check** to see that it reaches its source, then **Switch on**.

![Admin, Connectors: each connector, whether it is on, its source, its credential's variable, and its runs](img/connectors-light.webp)

**A credential never goes into AppWren.** A connector that needs one names the environment variable that holds it, such as `APPWREN_GITHUB_TOKEN`; the server reads it when the connector runs. The page shows only whether it is set. Give each credential the least access it needs, and only read access.

| Kind | What it reads | Credential |
|---|---|---|
| **End-of-life data** | Support dates for technology releases, from the public endoflife.date dataset, for each technology with an end-of-life key | None. Only each technology's key is sent |
| **Source code hosting** | For each component whose repository is in one organization on GitHub or a GitHub Enterprise server: languages, when its code last changed, how many people changed it over 90 days, open dependency alerts by severity, and whether it has a README, tests, continuous integration, automated dependency updates, and a catalog file | A token that can only read the organization's repositories: their metadata, contents, and dependency alerts |
| **Identity provider** | For each application registered with Microsoft Entra ID: its active users over 30 days, from sign-ins; and those registered that are not on record | An application registration with the Microsoft Graph application permissions `Application.Read.All` and `AuditLog.Read.All`, consented by an administrator. Its client secret is the credential |

### End-of-life data

Give each technology its key in the dataset (on its record, **End-of-life key**: `python`, `nodejs`, `postgresql`). Each run follows the same rules as [support dates from a file](the-landscape.md#support-dates-from-a-file): releases are added and dates updated, nothing is removed, and a date the dataset does not give is left as it is. A key the dataset does not know is listed as not matched.

### Source code hosting

Give the host (`https://github.com`, or your GitHub Enterprise server) and the organization, as it appears in repository addresses. A component is read when its **Repository** is in that organization on that host. A repository the token cannot read is listed as not matched, and nothing else about it changes. Where the host will not say whether a repository has dependency alerts, its alerts are not known, which is not the same as none.

An application whose every repository was read gets its **maintainers** from the people who changed them over 90 days. From only some of them the count would be too low, so then its own number stands.

### The identity provider

Give the tenant (its ID or domain) and the client ID of the registration AppWren reads with. Each application registered there is matched to a record: by its identifier at the provider, kept on the record as its **Sign-in registration**, or else by its name or one of its aliases. A matched application's **users** become the people who signed in to it over the last 30 days. One that matches nothing is listed under [Not on record](#not-on-record).

### A run

Each connector that is on runs daily, or as often as you set, on the [scheduled work](running-the-program.md#scheduled-work-and-email); **Run now** runs it at once. A run reads everything first, under a time limit and a size limit on each answer, and only then writes, in one transaction. **A run that fails changes nothing**, and says why on the page. Every run is listed with what it read, what changed, what stayed the same, what a person's override kept, and what it could not match.

## Values from other systems

A value a source supplies is written to the record's own field, so every list, filter, export, and score reads one place. It is kept with its source and the time it was read. On the record, **From other systems** lists each one; a technology's releases table marks the dates that came from a source.

![A technology's releases, their dates marked with their source, and the values from other systems](img/technology-sourced-light.webp)

Someone who keeps the record can **Override** a value, saying why the source is wrong. The override wins until it is removed with **Use the source's value**; meanwhile the source's later readings wait beside it, and are shown. Changing such a field by hand on the record counts as an override too. Both are in the history, with who and why.

![Overriding a support date, with the reason](img/sourced-override-light.webp)

## Not on record

**Portfolio → Not on record** lists the applications registered with the identity provider that match no record, for stewards, architects, and managers. Each is listed once.

- **Add** makes an application record named for it, in a unit you choose, with the provider's identifier kept on it. The next run matches it and gives it its users.
- **Dismiss** says why it is not kept on record, such as a test registration. A dismissed one can be listed again.

One that someone records by hand is matched by the next run and leaves the list; one the provider no longer lists, that nobody decided about, goes. A connector never makes a record by itself.

![Not on record: applications people sign in to that the portfolio does not know, to add or dismiss](img/discovered-light.webp)

## Push sources

For a tool AppWren has no connector for, such as the service desk or monitoring, an administrator issues a **push key** under **Admin → Connectors → Push keys**. The key is shown once and kept only as a hash; if it is lost, revoke it and issue another. The tool posts facts with it:

```bash
curl -X POST https://appwren.example.org/api/v1/facts \
  -H "Authorization: Bearer $APPWREN_PUSH_KEY" -H "Content-Type: application/json" \
  -d '{"facts": [
        {"record": "APP-0042", "field": "incidents_90d", "value": 3, "observed_at": "2026-11-20T09:00:00Z"},
        {"record": "APP-0042", "field": "tickets_90d", "value": 27}
      ]}'
```

Each fact names a record by its reference, a field, a value, and optionally when it was observed (with its time zone; now, if not given) and, for a technology, the `release`. Any field a connector fills may be posted, and two only pushes fill:

| Field | Of | What it is |
|---|---|---|
| `incidents_90d` | An application | Incidents over the last 90 days |
| `tickets_90d` | An application | Support tickets over the last 90 days |

A batch of up to 1,000 facts is checked whole before anything is written: one bad fact and nothing lands, and the answer names each problem by its place in the list. The facts are shown as from the key's name. **A key posts facts and does nothing else**: it reads nothing and no other route accepts it, and a person signed in cannot post facts.

## Catalog files

An application and its components can be described in a `catalog-info.yaml` kept beside their code. On an application's **Components** part, **Export a catalog file** writes one; **Import one** reads one back, showing first what would change.

![Importing a catalog file: what would change, before anything does](img/catalog-import-light.webp)

The file holds documents with `kind`, `metadata`, and `spec`. A `System` describes the application: its `description`, `tags`, `lifecycle` (`production`, `experimental`, `deprecated`), and links to its documentation and home page. Each `Component` or `Resource` describes one of its parts: its `type` (`service`, `website`, `library`, `database`, and so on), its description, and its repository, from a `github.com/project-slug` annotation or a link of type `source`. A part is matched by the reference AppWren wrote into it, or by name; one that matches none is added. Owners are not taken from a file: people are named in AppWren.

Only what the file says is changed, and nothing is removed, so the same file twice changes nothing the second time. Files are read with a safe loader. An exported file carries AppWren's references, so it matches the same records when imported again.

## Engineering maturity

Each component's engineering practice is measured by checks, each from a record's field or a fact a source supplied:

| Level | Adds these checks | Read from |
|---|---|---|
| **Bronze** | Monitoring, backups, documentation | The application's record; documentation is its documentation address, or a README in the repository |
| **Silver** | Tests, continuous integration | The repository |
| **Gold** | Automated dependency updates, no open critical dependency alert | The repository |

A component reaches a level when every check of that level and those below it is met. A check about code does not apply to a part that is not code, such as a database; code with no repository recorded cannot pass it. An application is at the level of its **least mature component**. Only what is built here, or has a repository recorded, is measured: a bought product's engineering is its vendor's.

A component's page shows its level, each check and why, and what it needs for the next level; an application's **Components** part shows each component's. The applications list filters by level, and **Reports → Engineering maturity** counts the applications at each level under each unit, each count a link to the list behind it.

![Engineering maturity by unit: how many applications are at each level](img/maturity-light.webp)

The levels and their checks are part of the scoring model, beside the cadence, and can be changed [with a pack](running-the-program.md#or-change-it-with-a-pack).

## Signals in the scores

What sources supply joins the scores as **signals**, each a factor in the dimension it informs:

| Signal | Dimension | Weight | From |
|---|---|---|---|
| Incidents over 90 days | Technical health | 10 | A push source |
| Open critical and high dependency alerts | Technical health | 10 | Source code hosting |
| Days since its code changed (built here) | Technical health | 5 | Source code hosting |
| Engineering maturity | Technical health | 10 | Its checks, where a repository was read |
| Support tickets over 90 days | Cost and burden | 10 | A push source |

**A signal counts only where a source supplies it.** Elsewhere it does not apply, which is not the same as unknown: it neither lowers confidence nor moves the score, so an application with no source scores exactly as before. A dimension's other factors still add up to 100; a signal comes on top. The working names where each signal came from, and where a field such as users or maintainers was filled by a source.

![The working, with the signals a source supplied and where each came from](img/application-working-signals-light.webp)

A signal's weight is set on **Admin → Program → Scoring and cadence** like any other factor's, and the weights there add up to 100 without the signals. An installation still running an earlier default scoring model unchanged gets the signals and the maturity levels on upgrade. One that shaped its own model keeps it as it is.

## Next

- [The API](api.md): the routes for connectors, push keys, facts, catalog files, and maturity.
- [Running the program](running-the-program.md): the scoring model, and scheduled work.
