// The web app's entry point: find out about the product and who is signed in, then draw.

import { get, peek } from "./core/api.js";
import { h } from "./core/dom.js";
import { apply, setOrganizationPalette, setOrganizationRamp } from "./core/prefs.js";
import { fallback, route, start } from "./core/router.js";
import { can, setSession } from "./core/session.js";
import { openPalette } from "./components/cmdk.js";
import { commands, mountShell } from "./components/shell.js";
import { emptyState } from "./components/ui.js";
import { setProduct, setTitle } from "./pages/page.js";

apply(); // paint with the remembered mode and palette before anything else
const root = document.getElementById("app");

function applyBranding(meta) {
  setProduct(meta.branding.product_name);
  setOrganizationPalette(meta.branding.palette);
  setOrganizationRamp(meta.branding.score_ramp);
  document.getElementById("favicon").href = meta.branding.favicon || "/img/wren-mark.svg";
}

async function boot() {
  let meta;
  try {
    meta = (await get("/api/v1/meta", null, { fresh: true })).data;
  } catch {
    root.replaceChildren(h("div", { class: "page" }, emptyState({ iconName: "alert",
      title: "The server is not responding", text: "Check that it is running, then reload this page." })));
    return;
  }
  applyBranding(meta);

  let me = null;
  try {
    me = (await peek("/api/v1/session")).data;
  } catch (error) {
    if (error.status !== 401) throw error;
  }
  if (!me) {
    const path = window.location.pathname + window.location.search;
    if (window.location.pathname !== "/sign-in") {
      history.replaceState({}, "", path === "/" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(path)}`);
    }
    (await import("./pages/sign-in.js")).signIn(root, meta);
    return;
  }
  setSession(me);
  if (window.location.pathname === "/sign-in") history.replaceState({}, "", "/");

  const { main, redrawBrand } = mountShell(root, meta);
  const page = (file, name, ...extra) => async (params) => (await import(`./pages/${file}.js`))[name](main, ...extra, params);

  route("/", page("home", "home", meta));
  route("/account", page("account", "account"));
  route("/applications", page("records", "applicationList"));
  route("/applications/:ref", page("record", "applicationPage"));
  route("/applications/:ref/assess", page("assess", "assess"));
  for (const type of ["component", "vendor", "technology", "capability"]) {
    const path = { component: "components", vendor: "vendors", technology: "technologies", capability: "capabilities" }[type];
    route(`/${path}`, page("records", "recordList", type));
    route(`/${path}/:ref`, page("record", "recordPage", type));
  }
  route("/capability-map", page("capability-map", "capabilityMap"));
  route("/portfolio", page("portfolio", "portfolioChart"));
  route("/decisions", page("decisions", "decisionList"));
  route("/snapshots", page("decisions", "snapshotList"));
  route("/snapshots/:ref", page("decisions", "snapshotPage"));
  if (can("admin")) {
    route("/admin/people", page("admin-people", "adminPeople"));
    route("/admin/units", page("admin-units", "adminUnits"));
    route("/admin/appearance", page("admin-appearance", "adminAppearance"));
    route("/admin/sso", page("admin-sso", "adminSso"));
  }
  fallback(page("not-found", "notFound"));

  window.addEventListener("appwren:signed-out", () => window.location.reload());
  window.addEventListener("appwren:branding", async () => {
    const next = (await get("/api/v1/meta", null, { fresh: true })).data;
    Object.assign(meta, next);
    applyBranding(meta);
    redrawBrand(meta);
    const theme = document.getElementById("theme");
    theme.href = `/theme.css?v=${Date.now()}`;
    setTitle(document.querySelector("h1")?.textContent ?? "");
  });
  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest?.("input, textarea, select, [contenteditable]");
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openPalette(commands(meta));
    } else if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      openPalette(commands(meta));
    }
  });
  await start();
}

boot();
