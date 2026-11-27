// Shares of the portfolio: which applications are at one end of it. A share never feeds a
// score: that is for the defined bands.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { recordChip } from "../components/record.js";
import { alert, card, pageHeader } from "../components/ui.js";
import { icon } from "../core/dom.js";
import { show } from "./page.js";

export function sharesPage(main) {
  return show(main, {
    title: "Shares of the portfolio",
    load: async () => (await get("/api/v1/shares", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Shares of the portfolio",
        lede: "Which applications in service are at one end of the portfolio: the costliest, the least used, the oldest. A share says where an application stands among the others; it never feeds a score." }),
      data.cost_withheld ? alert("info", icon("info"), h("div", {}, `What ${plural(data.cost_withheld, "application")} cost is not shown to you, so they are left out of the shares by cost.`)) : null,
      h("div", { class: "grid-2" }, data.shares.map((share) => card({ title: share.label, flush: share.items.length > 0 },
        h("p", { class: "card-note muted" }, `${share.definition} ${share.items.length} of ${share.of}${share.not_known ? `; ${share.not_known} with no figure are left out` : ""}.`),
        share.items.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Application"), h("th", { scope: "col", class: "numeric" }, share.unit))),
          h("tbody", {}, share.items.map((item) => h("tr", {}, h("td", {}, recordChip(item)),
            h("td", { class: "numeric" }, Number(item.value).toLocaleString(undefined, { maximumFractionDigits: 1 })))))))
          : h("p", { class: "muted" }, "Nothing here: no application has this figure."))))),
  });
}
