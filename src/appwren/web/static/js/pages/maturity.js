// Engineering maturity by unit: how many applications are at each level under each unit, each
// count a link to the list behind it. A unit with units below it opens to show them.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { query } from "../core/router.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

function cell(count, level, unitId) {
  if (!count) return h("td", { class: "numeric subtle" }, "0");
  const params = new URLSearchParams({ maturity: level });
  if (unitId) params.set("unit", unitId);
  return h("td", { class: "numeric" }, h("a", { href: `/applications?${params}` }, String(count)));
}

export function maturityReport(main) {
  const unit = query().get("unit");
  return show(main, {
    title: "Engineering maturity",
    load: async () => (await get("/api/v1/maturity", unit ? { unit } : null, { fresh: true })).data,
    view: (data) => {
      const head = h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"),
        data.levels.map(([, text]) => h("th", { scope: "col", class: "numeric" }, text)), h("th", { scope: "col", class: "numeric" }, "All")));
      const row = (item, name) => h("tr", {}, h("th", { scope: "row" }, name),
        data.levels.map(([key]) => cell(item.counts[key], key, item.unit?.id)),
        h("td", { class: "numeric" }, String(item.total)));
      const rows = data.rows.map((item) => row(item, item.unit.has_children
        ? h("a", { href: `/maturity?unit=${item.unit.id}` }, item.unit.name) : item.unit.name));
      const all = { ...data.all, unit: data.unit };
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Engineering maturity",
          lede: "What engineering practice each application has, measured from its record and its repositories: bronze for monitoring, backups, and documentation; silver adds tests and continuous integration; gold adds automated dependency updates and no open critical alert. An application is at the level of its least mature component." }),
        data.unit ? h("p", { class: "muted" }, unit ? [h("a", { href: data.up ? `/maturity?unit=${data.up}` : "/maturity" }, "Up a level"), " · "] : null,
          `Each count includes the units below. Units in ${data.unit.name}:`) : null,
        data.all.total ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" }, head,
          h("tbody", {}, rows, row(all, data.unit ? `All of ${data.unit.name}` : "The whole organization")))))
          : emptyState({ iconName: "quality", title: "Nothing to measure here", text: "No application you can see is in this unit or the units below it." }));
    },
  });
}
