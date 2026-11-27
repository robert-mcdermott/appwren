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
const app = (words, tab = "") => async (page) =>
  `/applications/${await first(`/api/v1/applications?q=${encodeURIComponent(words)}`)(page)}${tab ? `?tab=${tab}` : ""}`;
const record = (path, words) => async (page) =>
  `/${path}/${await first(`/api/v1/${path}?q=${encodeURIComponent(words)}`)(page)}`;

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
  { name: "capability-map", as: "architect", path: "/capability-map" },
  { name: "capability", as: "architect", path: record("capabilities", "Participant surveys") },
  { name: "technologies", as: "architect", path: "/technologies" },
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
  { name: "auditor", as: "auditor", path: "/applications" },
];
