// Data quality: how much of the portfolio can be trusted, by the unit that answers for each
// application. Every count opens the applications it counts.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { unitOptions, units } from "../core/lookups.js";
import { query } from "../core/router.js";
import { listHref, statTile } from "../components/charts.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

export function dataQuality(main) {
  return show(main, {
    title: "Data quality",
    load: async () => {
      const [report, unitIndex] = await Promise.all([get("/api/v1/data-quality", Object.fromEntries(query()), { fresh: true }), units()]);
      return { report: report.data, units: unitIndex };
    },
    view: ({ report, units: unitIndex }) => {
      const link = (figure) => listHref("/list", figure.filters);
      const cell = (figure) => h("td", { class: "numeric" }, figure.count ? h("a", { href: link(figure) }, String(figure.count)) : h("span", { class: "subtle" }, "0"));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Data quality",
          lede: "A portfolio is only as good as what is known about it. Each figure opens the applications it counts, and each application says what it lacks." }),
        h("div", { class: "filters" }, filterSelect("unit", unitOptions(unitIndex.tree, { blank: "The whole organization" }), "Unit")),
        report.total.count ? [
          h("div", { class: "tiles" }, statTile({ value: report.total.count, label: "Applications in service", href: link(report.total) }),
            report.issues.map((figure) => statTile({ value: figure.count, label: figure.label, href: link(figure), tone: figure.key === "no_accountable" ? "danger" : "warn" }))),
          card({ title: "By the unit that answers for them", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Applications"),
              report.issues.map((issue) => h("th", { scope: "col" }, issue.label)))),
            h("tbody", {}, report.units.map((row) => h("tr", {}, h("th", { scope: "row" }, row.unit.name), cell(row.total), row.issues.map(cell))))))),
        ] : card({}, emptyState({ iconName: "quality", title: "Nothing recorded yet" })));
    },
  });
}
