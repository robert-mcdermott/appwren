// The capability map: what the organization does, and how many applications serve each part.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { hrefOf } from "../components/record.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

/** How many serve a capability, and whether that is none, one, or an overlap worth a look. */
function count(node) {
  const n = node.applications.length;
  const state = n === 0 ? "none" : n > 1 ? "overlap" : "one";
  const words = n === 0 ? "No application serves it" : n > 1 ? `${n} applications serve it` : "One application serves it";
  return h("span", { class: "cap-count", "data-state": state, title: words }, h("span", { "aria-hidden": "true" }, String(n)),
    h("span", { class: "sr-only" }, words));
}

function branch(nodes) {
  return h("ul", { class: "cap-list" }, nodes.map((node) => h("li", {},
    h("div", { class: "cap-item" }, h("a", { href: hrefOf(node.ref) }, node.name), node.children.length ? null : count(node)),
    node.children.length ? branch(node.children) : null)));
}

export function capabilityMap(main) {
  return show(main, {
    title: "Capability map",
    load: async () => (await get("/api/v1/capability-map", null, { fresh: true })).data,
    view: (roots) => {
      const leaves = (node) => (node.children.length ? node.children.flatMap(leaves) : [node]);
      const all = roots.flatMap(leaves);
      const overlaps = all.filter((node) => node.applications.length > 1).length;
      const gaps = all.filter((node) => node.applications.length === 0).length;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Capability map",
          lede: `What the organization does: ${plural(all.length, "capability", "capabilities")}. ${overlaps} served more than once; ${gaps} served by nothing on record.`,
          actions: h("a", { class: "btn", href: "/capabilities" }, "As a list") }),
        roots.length ? h("div", { class: "cap-map" }, roots.map((root) => card({ title: root.name },
          root.summary ? h("p", { class: "subtle" }, root.summary) : null, branch(root.children.length ? root.children : [root]))))
          : emptyState({ iconName: "capability", title: "No capabilities yet", text: "Load the default program, or add capabilities one by one." }));
    },
  });
}
