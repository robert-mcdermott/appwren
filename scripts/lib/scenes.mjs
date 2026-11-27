// The screens the documentation shows and the accessibility audit walks. One line each:
// a name, who is signed in (a key from the demo's sample people), a path, and optionally a
// step to run in the page first (a JavaScript expression), such as opening a dialog.
//
// A path may be a function of the page, for addresses that depend on what the demo holds.

const first = (api, pick = "(rows) => rows[0].ref") => async (page) => page.evaluate(
  `fetch(${JSON.stringify(api)}).then((r) => r.json()).then((body) => (${pick})(body.data))`);
// A step that presses the button of that name. If there is none it says so, and the audit
// reports it, so that a renamed button fails and is not passed over in silence.
const click = (text) => `(() => { const el = [...document.querySelectorAll("button, a")].find((each) => each.textContent.trim() === ${JSON.stringify(text)});
  if (el) el.click(); else window.__sceneMissed = ${JSON.stringify(`there is no button called "${text}"`)}; })()`;
// The same, for a button known by its accessible name, where several share the same words.
const press = (name) => `(() => { const el = [...document.querySelectorAll("button[aria-label]")].find((each) => each.getAttribute("aria-label") === ${JSON.stringify(name)});
  if (el) el.click(); else window.__sceneMissed = ${JSON.stringify(`there is no button called "${name}"`)}; })()`;
const app = (words, tab = "") => async (page) =>
  `/applications/${await first(`/api/v1/applications?q=${encodeURIComponent(words)}`)(page)}${tab ? `?tab=${tab}` : ""}`;
const record = (path, words) => async (page) =>
  `/${path}/${await first(`/api/v1/${path}?q=${encodeURIComponent(words)}`)(page)}`;

// A record past its confirmation that someone still answers for, and that is otherwise known.
const stale = first("/api/v1/portfolio?in_service=true&quality=not_confirmed",
  "(rows) => `/applications/${(rows.find((row) => !row.quality.includes('no_accountable') && row.confidence >= 60) ?? rows[0]).ref}`");

export const SCENES = [
  { name: "home-manager", as: "portfolio", path: "/" },
  { name: "home-steward", as: "res_steward", path: "/" },
  { name: "home-engineer", as: "rse", path: "/" },
  { name: "home-leader", as: "cio", path: "/" },
  { name: "dashboard", as: "portfolio", path: "/dashboard" },
  { name: "data-quality", as: "portfolio", path: "/data-quality" },
  { name: "portfolio-chart", as: "portfolio", path: "/portfolio" },
  { name: "portfolio-cost", as: "portfolio", path: "/portfolio?view=cost" },
  { name: "decisions", as: "portfolio", path: "/decisions?show=mismatch" },
  { name: "snapshots", as: "portfolio", path: "/snapshots" },
  { name: "list", as: "portfolio", path: "/list?in_service=true&quality=low_confidence" },
  { name: "applications", as: "portfolio", path: "/applications" },
  { name: "application", as: "res_steward", path: app("Specimen Tracker") },
  { name: "application-scores", as: "res_steward", path: app("Specimen Tracker", "scores") },
  { name: "application-working", as: "res_steward", path: app("Specimen Tracker"),
    step: `(document.querySelector(".scorecard-item") ?? { click: () => (window.__sceneMissed = "the scorecard") }).click()` },
  { name: "application-assessment", as: "res_steward", path: app("Specimen Tracker", "assessment") },
  { name: "application-decisions", as: "clin_lead", path: app("Clinic Scheduler", "decisions") },
  { name: "application-components", as: "res_steward", path: app("Specimen Tracker", "components") },
  { name: "application-capabilities", as: "portfolio", path: app("Old Surveys", "capabilities") },
  { name: "application-history", as: "portfolio", path: app("Specimen Tracker", "history") },
  { name: "assess", as: "res_steward", path: async (page) => `${await app("Specimen Tracker")(page)}/assess` },
  { name: "decide", as: "cio", path: app("Research Data Warehouse"), step: click("Record a decision") },
  { name: "application-edit", as: "res_steward", path: app("Specimen Tracker"), step: click("Edit") },
  { name: "application-member", as: "rse", path: app("Clinic Scheduler") },
  { name: "application-connections", as: "res_steward", path: app("Specimen Tracker", "connections") },
  { name: "interface-add", as: "res_steward", path: app("Specimen Tracker", "connections"), step: click("It sends data") },
  { name: "graph", as: "architect", path: async (page) => (await app("Research Data Warehouse")(page)).replace("/applications/", "/graph/") },
  { name: "graph-open", as: "architect", path: async (page) => (await app("Specimen Tracker")(page)).replace("/applications/", "/graph/"),
    step: `(document.querySelector(".gexpand") ?? { dispatchEvent: () => (window.__sceneMissed = "a record to expand") }).dispatchEvent(new MouseEvent("click", { bubbles: true }))` },
  { name: "data-flows", as: "architect", path: "/data-flows?data_class=identifiable_research" },
  { name: "data-flows-all", as: "architect", path: "/data-flows" },
  { name: "interfaces", as: "architect", path: "/interfaces" },
  { name: "interface", as: "architect", path: record("interfaces", "Enrollment figures") },
  { name: "hosting-platforms", as: "architect", path: "/hosting-platforms" },
  { name: "hosting-platform", as: "architect", path: record("hosting-platforms", "Campus data center") },
  { name: "deployments", as: "architect", path: "/deployments" },
  { name: "deployment", as: "res_steward", path: first("/api/v1/deployments?q=Specimen+Tracker", "(rows) => `/deployments/${rows[0].ref}`") },
  { name: "deployment-add", as: "res_steward", path: app("Specimen Tracker", "components"), step: click("Say where it runs") },
  { name: "application-cost", as: "res_steward", path: app("Specimen Tracker", "cost") },
  { name: "application-cost-withheld", as: "rse", path: app("Clinic Scheduler", "cost") },
  { name: "cost-lines-edit", as: "res_steward", path: app("Specimen Tracker", "cost"), step: click("Edit the lines") },
  { name: "contracts", as: "portfolio", path: "/contracts" },
  { name: "contracts-due", as: "portfolio", path: "/contracts?ending_within=90" },
  { name: "contract", as: "portfolio", path: record("contracts", "Pinecrest") },
  { name: "contract-covers", as: "portfolio", path: record("contracts", "Pinecrest"), step: click("Edit what it covers") },
  { name: "funding-sources", as: "portfolio", path: "/funding-sources" },
  { name: "funding-source", as: "portfolio", path: record("funding-sources", "Research operations") },
  { name: "capability-map", as: "architect", path: "/capability-map" },
  { name: "capability-heat", as: "architect", path: "/capability-map?measure=weakest_health" },
  { name: "capability-confidence", as: "architect", path: "/capability-map?measure=confidence" },
  { name: "overlap", as: "portfolio", path: "/overlap" },
  { name: "overlap-member", as: "rse", path: "/overlap" },
  { name: "capability", as: "architect", path: record("capabilities", "Participant surveys") },
  { name: "technologies", as: "architect", path: "/technologies" },
  { name: "lifecycle", as: "architect", path: "/lifecycle" },
  { name: "lifecycle-ended", as: "architect", path: "/lifecycle?support=ended" },
  { name: "radar", as: "architect", path: "/radar" },
  { name: "import-support-dates", as: "architect", path: "/technologies", step: click("Import support dates") },
  { name: "technology", as: "architect", path: record("technologies", "PostgreSQL") },
  { name: "vendors", as: "architect", path: "/vendors" },
  { name: "vendor", as: "architect", path: record("vendors", "Fieldnote") },
  { name: "components", as: "architect", path: "/components" },
  { name: "component", as: "res_steward", path: record("components", "Specimen Tracker database") },
  { name: "people", as: "admin", path: "/admin/people" },
  { name: "units", as: "admin", path: "/admin/units" },
  { name: "appearance", as: "admin", path: "/admin/appearance" },
  { name: "admin-sso", as: "admin", path: "/admin/sso" },
  { name: "account", as: "rse", path: "/account" },
  { name: "data-handling", as: "portfolio", path: "/data-handling?data_class=health" },
  { name: "data-handling-member", as: "rse", path: "/data-handling?data_class=identifiable_research" },
  { name: "history", as: "auditor", path: "/history" },
  { name: "history-everything", as: "auditor", path: "/history?kind=all" },
  { name: "auditor", as: "auditor", path: "/applications" },
  // Keeping current (wave 3)
  { name: "notices", as: "portfolio", path: "/notices" },
  { name: "scheduled-work", as: "admin", path: "/admin/scheduled-work" },
  { name: "application-stale", as: "portfolio", path: stale },
  { name: "confirm", as: "portfolio", path: stale, step: click("Confirm the record") },
  { name: "campaigns", as: "portfolio", path: "/campaigns" },
  { name: "campaign", as: "portfolio", path: first("/api/v1/campaigns", "(rows) => `/campaigns/${rows.find((row) => row.status === 'open').ref}`") },
  { name: "campaign-start", as: "portfolio", path: "/campaigns", step: click("Start a campaign") },
  { name: "campaign-mine", as: "res_steward", path: first("/api/v1/campaigns", "(rows) => `/campaigns/${rows.find((row) => row.status === 'open').ref}?mine=1`") },
  { name: "tasks", as: "portfolio", path: "/tasks?show=open" },
  { name: "tasks-mine", as: "res_steward", path: "/tasks" },
  { name: "task", as: "portfolio", path: first("/api/v1/tasks?mine=true", "(rows) => `/tasks/${rows[0].id}`") },
  { name: "holdings", as: "admin", path: first("/api/v1/accounts?q=Orrin", "(rows) => `/people/${rows.find((row) => row.status === 'disabled')?.id ?? rows[0].id}/holdings`") },
  { name: "search", as: "architect", path: "/search?q=sample%20tracker" },
  { name: "palette", as: "architect", path: "/", step: `document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, metaKey: true, bubbles: true }))` },
  { name: "views", as: "portfolio", path: "/list?in_service=true&quality=not_confirmed&tier=1", step: click("Views") },
  { name: "add-duplicate", as: "portfolio", path: "/applications",
    step: `(async () => { ${click("Add an application")}; await new Promise((done) => setTimeout(done, 700));
      const box = [...document.querySelectorAll(".drawer input")].find((el) => el.closest(".field")?.querySelector("label")?.textContent.trim() === "Name");
      if (!box) { window.__sceneMissed = "the name field"; return; }
      box.value = "Expense reporting"; box.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((done) => setTimeout(done, 1200)); })()` },
  { name: "contests", as: "architect", path: app("Flow Cytometry Scheduler", "scores") },
  { name: "applications-built-on", as: "architect", path: first("/api/v1/technologies?q=PostgreSQL", "(rows) => `/applications?technology=${rows[0].ref}&release=13`") },
  { name: "program", as: "portfolio", path: "/admin/program?list=platform_kinds" },
  { name: "program-fields", as: "portfolio", path: "/admin/program?tab=fields" },
  { name: "program-questions", as: "portfolio", path: "/admin/program?tab=questions" },
  { name: "program-scoring", as: "portfolio", path: "/admin/program?tab=scoring" },
  { name: "program-decisions", as: "portfolio", path: "/admin/program?tab=decisions" },
  // Signals (wave 4)
  { name: "connectors", as: "admin", path: "/admin/connectors" },
  { name: "connector-add", as: "admin", path: "/admin/connectors", step: press("Add a connector: End-of-life data") },
  { name: "technology-sourced", as: "architect", path: record("technologies", "Ubuntu") },
  { name: "application-code", as: "res_steward", path: app("Freezer Watch", "components") },
  { name: "component-code", as: "res_steward", path: record("components", "Freezer Watch application") },
  { name: "discovered", as: "portfolio", path: "/discovered" },
  { name: "discovered-add", as: "portfolio", path: "/discovered", step: press("Add Room Booking") },
  { name: "application-sourced", as: "portfolio", path: app("Grant Management System") },
  { name: "maturity", as: "portfolio", path: "/maturity" },
  { name: "applications-maturity", as: "portfolio", path: "/applications?maturity=none" },
  { name: "application-working-signals", as: "portfolio", path: app("Freezer Watch", "scores") },
  { name: "push-key", as: "admin", path: "/admin/connectors", step: click("Issue a key") },
  { name: "catalog-import", as: "res_steward", path: app("Specimen Tracker", "components"),
    step: `(async () => { const ref = location.pathname.split("/")[2];
      const text = await (await fetch(\`/api/v1/applications/\${ref}/catalog\`)).text();
      ${click("Import one")}; await new Promise((done) => setTimeout(done, 700));
      const box = document.querySelector("[role=dialog] textarea");
      if (!box) { window.__sceneMissed = "the catalog file box"; return; }
      box.value = text.replace(/description: .*/, "description: Follows every specimen from collection to release.")
        + "---\\napiVersion: appwren/v1\\nkind: Component\\nmetadata:\\n  name: specimen-labels\\n  title: Specimen Labels\\nspec:\\n  type: library\\n";
      ${click("Check what would change")}; await new Promise((done) => setTimeout(done, 1200)); })()` },
  // Planning change (wave 5)
  { name: "reviews", as: "portfolio", path: "/reviews" },
  { name: "review", as: "portfolio", path: first("/api/v1/reviews?state=closed", "(rows) => `/reviews/${rows[0].ref}`") },
  { name: "review-upcoming", as: "portfolio", path: first("/api/v1/reviews?state=planned", "(rows) => `/reviews/${rows[0].ref}`") },
  { name: "roadmap", as: "portfolio", path: "/roadmap" },
  { name: "initiative", as: "architect", path: first("/api/v1/initiatives?q=Executive", "(rows) => `/initiatives/${rows[0].ref}`") },
  { name: "decision-start-initiative", as: "architect", path: app("Intranet", "decisions") },
  { name: "requests", as: "portfolio", path: "/requests" },
  { name: "request", as: "portfolio", path: first("/api/v1/requests?state=evaluating", "(rows) => `/requests/${rows[0].ref}`") },
  { name: "request-ended", as: "portfolio", path: first("/api/v1/requests?state=approved", "(rows) => `/requests/${rows[0].ref}`") },
  { name: "request-options", as: "portfolio", path: first("/api/v1/requests?state=evaluating", "(rows) => `/requests/${rows[0].ref}`"), step: click("Edit") },
  { name: "retirement", as: "portfolio", path: app("Old Surveys", "retirement") },
  { name: "retirements", as: "portfolio", path: "/retirements" },
  { name: "stage-gate", as: "res_steward", path: app("Specimen Tracker"), step: click("Edit") },
  // Insight (wave 6)
  { name: "trends", as: "portfolio", path: "/trends" },
  { name: "shares", as: "portfolio", path: "/shares" },
  { name: "application-over-time", as: "portfolio", path: app("Freezer Watch", "scores") },
  { name: "sourced-override", as: "architect", path: record("technologies", "Python"),
    step: `document.querySelectorAll("details").forEach((d) => { d.open = true; }); ${press("Override support ends of 3.12")}` },
];
