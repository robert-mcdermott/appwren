// The capability map: what the organization does, and how many applications serve each part.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { listHref } from "../components/charts.js";
import { hrefOf } from "../components/record.js";
import { card, emptyState, pageHeader, scoreFigure } from "../components/ui.js";
import { show } from "./page.js";

// What the map can be measured by. Scores are the average over a capability's applications.
const MEASURES = [
  ["applications", "How many serve it", "The number of applications in service that serve each capability."],
  ["business_value", "Business value", "The average business value of the applications that serve each capability."],
  ["technical_health", "Technical health", "The average technical health of the applications that serve each capability."],
  ["weakest_health", "Weakest health", "The technical health of the weakest application that serves each capability: where the capability is most at risk."],
  ["cost_burden", "Cost and burden", "The average for cost and burden; 5 is light to keep."],
  ["risk_exposure", "Risk exposure", "The average for risk exposure; 5 is little exposure."],
  ["confidence", "Data confidence", "How much is known about the applications that serve each capability, on average."],
];

/** How many serve a capability, and whether that is none, one, or an overlap worth a look. */
function count(node) {
  const n = node.applications.length;
  const state = n === 0 ? "none" : n > 1 ? "overlap" : "one";
  const words = n === 0 ? "No application serves it" : n > 1 ? `${n} applications serve it` : "One application serves it";
  return h("span", { class: "cap-count", "data-state": state, title: words }, h("span", { "aria-hidden": "true" }, String(n)),
    h("span", { class: "sr-only" }, words));
}

/** A capability's figure for the measure chosen, as a link to the applications behind it. */
function figure(node, measure) {
  if (measure === "applications") return count(node);
  const value = node.measures[measure];
  const name = MEASURES.find(([key]) => key === measure)[1];
  if (value == null) return h("span", { class: "subtle cap-none" }, "Nothing to measure");
  const shown = measure === "confidence" ? h("span", { class: "cap-confidence", "data-low": String(value < 70) }, `${value}%`) : scoreFigure(value, { label: name });
  return h("a", { class: "cap-figure", href: listHref("/list", node.filters), "aria-label": `${node.name}: ${name.toLowerCase()} ${value}${measure === "confidence" ? "%" : " of 5"}, over ${plural(node.measures.applications, "application")}` }, shown);
}

function branch(nodes, measure) {
  return h("ul", { class: "cap-list" }, nodes.map((node) => h("li", {},
    h("div", { class: "cap-item" }, h("a", { href: hrefOf(node.ref) }, node.name), node.children.length && measure === "applications" ? null : figure(node, measure)),
    node.children.length ? branch(node.children, measure) : null)));
}

export function capabilityMap(main) {
  return show(main, {
    title: "Capability map",
    load: async () => (await get("/api/v1/capability-heat", null, { fresh: true })).data,
    view: (roots) => {
      const wanted = query().get("measure");
      const measure = MEASURES.some(([key]) => key === wanted) ? wanted : "applications";
      const leaves = (node) => (node.children.length ? node.children.flatMap(leaves) : [node]);
      const all = roots.flatMap(leaves);
      const overlaps = all.filter((node) => node.applications.length > 1).length;
      const gaps = all.filter((node) => node.applications.length === 0).length;
      const picker = h("div", { class: "segmented wrap", role: "group", "aria-label": "Measure the map by" }, MEASURES.map(([key, text]) =>
        h("button", { type: "button", "aria-pressed": String(key === measure), onclick: () => setQuery({ measure: key === "applications" ? null : key }) }, text)));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Capability map",
          lede: `What the organization does: ${plural(all.length, "capability", "capabilities")}. ${overlaps} served more than once; ${gaps} served by nothing on record.`,
          actions: [h("a", { class: "btn", href: "/overlap" }, "Overlap"), h("a", { class: "btn", href: "/capabilities" }, "As a list")] }),
        roots.length ? [picker, h("p", { class: "muted" }, MEASURES.find(([key]) => key === measure)[2],
          measure === "applications" ? "" : " Each figure opens the applications it is worked out from."),
        h("div", { class: "cap-map" }, roots.map((root) => card({ title: root.name,
          actions: measure === "applications" ? null : figure(root, measure) },
        root.summary ? h("p", { class: "subtle" }, root.summary) : null, branch(root.children.length ? root.children : [root], measure))))]
          : emptyState({ iconName: "capability", title: "No capabilities yet", text: "Load the default program, or add capabilities one by one." }));
    },
  });
}
