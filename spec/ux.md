# UX and design system

AppWren should feel like a well-made professional tool: calm, quick, and exact. Most of the people who keep a portfolio do so a few minutes a month and did not ask to, so the design has two jobs. For the owner of an application it must make their part short and obvious. For the people who run the portfolio it must make hundreds of connected records readable at a glance, and every score traceable to what produced it.

## Design principles

1. **Answer first.** Every page leads with the answer to the question that brought the person there: *what do I owe?*, *what is this, and who answers for it?*, *what should we do with it?*, *where does the portfolio stand?*
2. **Short by default, deep on demand.** Lists are dense and scannable. Detail opens beside them, not instead of them.
3. **Show the working.** A score, a confidence figure, or a recommendation is never a bare number or label. One click shows what produced it.
4. **Recommendation, decision, and flags are different things.** What the system suggests, what people decided, and what needs attention are three signals, never one color.
5. **The URL is the state.** Filters, sort, tabs, and the open record all live in the URL. Back works, and every view can be shared.
6. **One record, one click from its neighbors.** An application shows its components, capabilities, technologies, vendor, and what depends on it; each of those shows every application that uses it.
7. **Keyboard first, mouse friendly.** Everything is reachable by keyboard.
8. **Honest states.** Unknown is shown as unknown, expired as expired, withheld as withheld, and nothing is green by default.
9. **Accessible.** WCAG 2.2 AA in every palette and mode.

## Identity

### The mark

The logo is a **stylized wren on a perch**: a compact, rounded body with the short, sharply cocked tail that makes a wren recognizable in silhouette, standing on a single short line. It is drawn from a few geometric strokes in a single color so that it holds at 16 pixels as a favicon and scales to a hero. The perch is a branch: one line, the shape every portfolio chart is drawn from, and the thing a wren knows best, whether it will bear weight.

- Supplied as SVG in three forms: the mark alone, the mark with the wordmark beside it, and a single-color version for print and dark backgrounds.
- The wordmark sets *App* in regular weight and *Wren* in semibold, in the interface font.
- Clear space equal to the height of the tail on every side.

An adopting organization replaces the mark and wordmark with its own. "AppWren" then appears only as a small "Powered by AppWren" link in the footer, which can be turned off.

### Voice

Plain words, short sentences, no jargon the reader did not bring with them. The interface says "Who answers for this?" and "What would we lose without it?", and never "Populate business application attributes". Buttons name their outcome ("Record: Modernize"), errors say what to do next, and empty states teach.

## Visual language

### Tokens

All visual values are CSS custom properties defined once in `tokens.css`. Colors are `light-dark()` pairs in `oklch()`, so each has a day and a night value side by side and the two stay balanced.

- **Surfaces:** `--bg`, `--surface-1..3`, `--border`, `--border-strong`, and `--control-border` for the edge of form fields, which must reach 3:1 against the page
- **Text:** `--text`, `--text-muted`, `--text-subtle`, `--text-inverse`
- **Accent:** `--accent`, `--accent-hover`, `--accent-strong`, `--accent-soft`, `--on-accent`
- **Signal:** `--ok`, `--warn`, `--danger`, `--info`, `--neutral`, each with a `-soft` tint, for flags and states
- **Score:** `--score-1..5`, an ordinal ramp (see below), each with a readable text color on top
- **Disposition:** `--disp-invest`, `--disp-maintain`, `--disp-tolerate`, `--disp-modernize`, `--disp-replace`, `--disp-consolidate`, `--disp-retire`, `--disp-incubate`, `--disp-assess`
- **Record types:** `--rec-application`, `--rec-component`, `--rec-capability`, `--rec-technology`, `--rec-vendor`, each with a `-soft` tint
- **Series:** `--series-0..5`, categorical colors for charts
- **Spacing:** 4 px base scale (`--space-1` = 4 px … `--space-10` = 64 px)
- **Radius:** `--radius-s` 6 px, `--radius-m` 10 px, `--radius-l` 16 px
- **Elevation:** three shadow levels, deeper in dark mode
- **Motion:** 120, 200, and 320 ms durations, all disabled under `prefers-reduced-motion`

### Scores, dispositions, and flags

Three signals, kept apart:

- **Scores** use an ordinal ramp in a single hue, pale for 1 and deep for 5, always with the figure itself and a short bar. A score reads as *how much, on a scale where more is better*. Coverage under 100% is shown beneath the figure; a thin dimension is drawn hatched.
- **Dispositions** each have a hue and an icon, used for the recommendation and the decision alike, with the disposition's name always written. The recommendation is drawn outlined, the decision filled, so the two can sit side by side and a mismatch is visible without color.
- **Flags** use the signal colors (amber for warning, red for danger, blue for information), always with an icon and a sentence.

Color is never the only signal for any of them.

| Disposition | Hue | Icon idea |
|---|---|---|
| Invest | Green | Arrow rising |
| Maintain | Teal | Level line |
| Tolerate | Sand | Pause |
| Modernize | Blue | Arrows turning |
| Replace | Violet | Swap |
| Consolidate | Ochre | Merge |
| Retire | Grey-red | Sunset |
| Incubate | Lime | Seedling |
| Assess | Grey | Question |

### Record types

Each record type has one hue and one icon, used consistently in chips, list rows, graph nodes, and page headers. A test keeps record hues well away from the signal colors and the score ramp in every palette.

| Record | Hue | Icon idea |
|---|---|---|
| Application | Indigo | Window with a title bar |
| Component | Teal | Stacked blocks |
| Capability | Ochre | Hexagon |
| Technology | Blue | Chip |
| Vendor | Slate | Storefront |

Later record types (deployment, interface, contract, initiative, request) take their hues when their wave arrives, under the same test.

### Typography

- **Font:** the platform's system UI stack. Nothing to download. Tabular numerals in tables and figures.
- **Scale:** 12 / 13 / 14 (body) / 16 / 18 / 20 / 24 / 30 / 36 px.
- **Weights:** 400, 500, 600.

### Themes: mode and palette

Appearance has two independent choices, under **Appearance** in the top bar and in the command palette.

- **Mode:** light, dark, or follow the system.
- **Palette:** a named set of colors with a day and a night version. The organization sets the default; each person may choose another, remembered in their browser.

| Palette | By day | After dark |
|---|---|---|
| **Wren** (default) | Warm paper neutrals, ink text, a deep moss-green accent, a thin russet rule | Warm charcoal, soft moss accent |
| **Slate** | Cool white and grey, cobalt accent; the conventional enterprise look | Blue-black surfaces, bright cobalt accent |
| **Garnet** | Neutral greys with a deep red accent, for the many institutions whose colors are red | Near-black with a softened garnet accent |

Every palette and mode is checked for AA contrast, first on the token pairs and then by sampling the rendered text of the main pages against its real background.

### Branding

An organization makes AppWren its own in **Admin → Appearance**, with a live preview and no file editing:

- product name and organization name,
- logo for light and dark backgrounds, and a favicon,
- default palette, and optionally its own accent color,
- from wave 7, a full custom palette, a message and image on the sign-in page, footer links, an email header, and its own words for key terms ("unit" may be "department"; "application" may be "solution").

The server generates `theme.css` from these settings. A chosen accent is checked for contrast against its backgrounds before it can be saved, lightened automatically for dark mode, and given readable text on top. Uploaded images are size-limited, type-checked, and, for SVG, sanitized.

## Information architecture

```text
Top bar:  [mark / product name]  [ ⌘K Search… ]  [+ New]  [🔔] [appearance] [me]

Sidebar:  Home
          Portfolio     Applications · Portfolio chart · Decisions
          Landscape     Capabilities · Technologies · Vendors
                        Dependencies (2) · Data flows (2) · Lifecycle (2)
          Plan          Review cycles (5) · Initiatives (5) · Requests (5)
          Reports       Dashboard · Data quality · Trends (6) · Scenarios (6)
          ───────────
          Admin         Program · People and units · Appearance · Connectors (4) · System
```

Numbers in brackets are the wave in which a page arrives; the sidebar never shows an empty section.

- Each person sees only the sections their roles use. A member sees Home, the catalog, and the applications they are named on.
- **Command palette (⌘K or Ctrl-K):** find any record by reference or name, jump to a page, or run an action ("New application", "Switch to dark").
- The sidebar collapses to icons on narrow screens and becomes a drawer on a phone. Looking up an application, checking what you owe, and attesting work on a phone; assessment and administration assume a larger screen.

## Key screens

| Screen | Purpose | Highlights |
|---|---|---|
| **Home** | What I owe and what is waiting | One list, most urgent first: applications I answer for with no assessment or an expired one, low confidence, missing required fields, decisions due for review, and flags. For a steward, their unit's applications nobody answers for. For a manager, the portfolio's mismatches and decisions due |
| **Applications** | Find and compare | A dense table with reference, name, unit, accountable owner, lifecycle, tier, sourcing, scores, confidence, recommendation, and decision; filters for all of them; the selected application opens beside the list |
| **Application** | Everything about one application | Header with reference, name, lifecycle, tier, accountable owner, the recommendation and decision side by side, and flags. The *scorecard* strip: four scores and confidence, each opening its working. Tabs: Overview, Components, Capabilities, People, Assessment, Decisions, Links, History |
| **Assess** | Answer the questions | One question at a time or all on one page; each question a row of five choices with the definition of the level under the pointer; *Don't know* always available; the scores and recommendation that would result update beside the form as answers change |
| **The working** | Why this score | Each factor with its level, weight, value, and source; unknown and not-applicable factors with the reason; the sum; the rule that fired and the thresholds compared; what would raise confidence, with links |
| **Record a decision** | A named decision | The recommendation and its working beside the form; the disposition chosen, the rationale, a review date, a target date, and for *Replace* or *Consolidate* the successor; refused with the reason if the person lacks the authority |
| **Portfolio chart** | See the portfolio at once | Business value against technical health, bubbles sized by cost (where the viewer may see cost) and colored by risk exposure on the score ramp, the threshold lines drawn, quadrant names in the corners; filters by unit, domain, sourcing, and lifecycle; a bubble opens its application; a table of the same points; a second view of value against cost and burden; applications that cannot be placed listed beside it |
| **Capabilities** | What the organization does, and with what | The capability tree with a count of applications on each; a capability's page lists its applications with the primary marked |
| **Technologies** | What the portfolio is built on | Each technology with its radar ring, releases and support dates, and the components that use each release, soonest end of support first |
| **Dashboard** | Where the portfolio stands | Counts by recommendation and by decision; mismatches; flags; lifecycle; sourcing; confidence; end-of-life exposure; every tile opens the records behind it |
| **Data quality** | How much can be trusted | Applications without an accountable owner, without a capability, without an assessment, with expired assessments, under the confidence threshold, and missing fields required at their stage, by unit |
| **Admin: Program** | Shape the program | Vocabularies, fields, the questionnaire, the scoring profiles and rules, cadences; from wave 3 editing all of them with an impact preview |
| **Admin: Appearance** | Brand it | Names, logos, palette, and accent with a live preview and contrast results |

## Components

Each is a small ES module that returns DOM. There is no virtual DOM and no templating library.

- **Layout:** app shell, sidebar, top bar, page header, split view, drawer, modal, tabs
- **Records:** record chip (icon, reference, name), score figure with a working popover, disposition badge (outlined or filled), flag, people-in-roles list, scorecard strip
- **Data display:** data table (sortable, column chooser, dense mode), definition list, stat tile, timeline, empty state, skeleton, withheld marker
- **Forms:** fields with server errors on their fields, level picker (a row of defined levels), record picker, person picker, unit picker, capability picker, date picker, the organization's own fields rendered from their definitions
- **Charts (SVG):** bubble chart with quadrants, bar, stacked bar, donut, and from wave 6 line, each with a table behind it

## Interaction details

- **Score figure:** clicking it opens the working for that dimension. The confidence figure opens the list of unknown factors in order of weight, each with a link to where it is entered.
- **Level picker:** five choices in a row, each with its name, and *Don't know*; the definition of the focused level is shown beneath, so a respondent never has to remember what 3 means for maintainability.
- **Recommendation and decision:** shown side by side in the header. When they differ, a *mismatch* flag sits between them and opens both workings.
- **Due dates:** shown as relative time with the date on hover; amber inside the warning window; red when past.
- **Undo:** reversible actions (adding a link or a capability, removing a tag) show a toast with Undo. Assessments and decisions are not undoable; they ask for confirmation and are superseded, never erased.
- **History:** every record's History tab shows changes as a readable timeline ("Lifecycle changed from Active to Containment by … "), filterable by kind.
- **Empty states teach:** an empty portfolio explains how to add the first application or import a spreadsheet, and what counts as an application.
- **Printing:** an application, the list, the portfolio chart, and the dashboard have print styles and produce clean PDFs from the browser's print dialog.

## Accessibility checklist

- Landmarks, headings in order, and a skip link
- A visible focus ring (2 px, offset) in every palette and mode
- Every control reachable and operable by keyboard; no traps in drawers or modals
- `aria-live` announcements for saves, async results, and workflow actions
- Form errors tied to their fields and summarized at the top
- The portfolio chart and every chart have tabular alternatives; each bubble is a link with a spoken label
- Targets at least 24 × 24 px
- Respects `prefers-reduced-motion` and `prefers-contrast`
- An automated audit runs over every documented screen, and a manual screen-reader script is run before each release

## Performance budgets

| Budget | Target |
|---|---|
| App shell JS and CSS (gzipped) | ≤ 100 KB |
| Each part loaded on first use (gzipped) | ≤ 40 KB |
| First meaningful render on a laptop | < 1 s |
| List API response (p95) at 5,000 applications | < 300 ms |
| Application page API response with its working (p95) | < 200 ms |
| Score preview while answering | < 150 ms |
| Demo organization build | < 60 s |
