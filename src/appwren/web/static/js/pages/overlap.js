// Overlap: every capability served by more than one application, with those applications
// side by side, so that what is paid for twice can be seen and talked about.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { listHref } from "../components/charts.js";
import { hrefOf, recordChip } from "../components/record.js";
import { card, dispositionBadge, emptyState, pageHeader, pill, scoreFigure } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

const SCORES = [["business_value", "Value"], ["technical_health", "Health"], ["cost_burden", "Cost"], ["risk_exposure", "Risk"]];
const money = (amount) => (amount === "withheld" ? h("span", { class: "subtle" }, "Withheld") : amount == null ? h("span", { class: "subtle" }, "—") : Number(amount).toLocaleString());

function side(item, vocab) {
  const disposition = (key, decided) => (key ? dispositionBadge(key, label(vocab, "dispositions", key), { decided }) : h("span", { class: "subtle" }, decided ? "None" : "—"));
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Application"), SCORES.map(([, text]) => h("th", { scope: "col" }, text)),
      h("th", { scope: "col" }, "Recommended"), h("th", { scope: "col" }, "Decided"),
      h("th", { scope: "col", class: "numeric" }, "People"), h("th", { scope: "col", class: "numeric" }, "A year"))),
    h("tbody", {}, item.applications.map((app) => h("tr", {},
      h("td", {}, h("div", { class: "row-sm wrap" }, recordChip(app), app.is_primary ? pill("Primary provider", "accent") : null)),
      SCORES.map(([key, text]) => h("td", {}, scoreFigure(app.scores[key], { label: text }))),
      h("td", {}, disposition(app.recommendation, false)), h("td", {}, disposition(app.decision, true)),
      h("td", { class: "numeric" }, app.users == null ? h("span", { class: "subtle" }, "—") : Number(app.users).toLocaleString()),
      h("td", { class: "numeric" }, money(app.annual_cost)))))));
}

export function overlapPage(main) {
  return show(main, {
    title: "Overlap",
    load: async () => {
      const [found, vocab, unitIndex] = await Promise.all([get("/api/v1/overlap", Object.fromEntries(query()), { fresh: true }), vocabularies(), units()]);
      return { found: found.data, vocab, units: unitIndex };
    },
    view: ({ found, vocab, units: unitIndex }) => {
      const items = found.capabilities;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Overlap",
          lede: items.length
            ? `${plural(items.length, "capability is", "capabilities are")} served by more than one application in service: ${plural(found.applications, "application")} in all.${found.unnamed ? ` ${found.unnamed} of them ${found.unnamed === 1 ? "has" : "have"} no primary provider named.` : ""}`
            : "Capabilities served by more than one application in service.",
          actions: h("a", { class: "btn", href: "/capability-map" }, "The map") }),
        h("div", { class: "filters" }, filterSelect("unit", unitOptions(unitIndex.tree, { blank: "The whole organization" }), "Unit"),
          filterSelect("domain", options(vocab, "domains", { blank: "Every domain" }), "Domain")),
        items.length ? items.map((item) => card({
          title: h("span", {}, h("a", { href: hrefOf(item.ref) }, item.name), h("span", { class: "subtle" }, ` · ${plural(item.applications.length, "application")}`)),
          actions: h("a", { class: "btn btn-sm", href: listHref("/list", item.filters), "aria-label": `${item.name}: open these applications as a list` }, "As a list"),
          flush: true,
          footer: h("p", { class: "subtle" }, `Together: ${Number(item.users).toLocaleString()} people`,
            item.annual_cost == null ? "" : `, ${Number(item.annual_cost).toLocaleString()} a year`, ". ",
            item.primary ? "" : "No primary provider is named, so none of them is recommended for consolidation. ",
            item.consolidate ? `${plural(item.consolidate, "is", "are")} recommended for consolidation into the primary.` : "") },
        side(item, vocab)))
          : card({}, emptyState({ iconName: "capability", title: "No capability is served twice",
            text: "When two applications in service serve the same capability, they appear here side by side." })));
    },
  });
}
