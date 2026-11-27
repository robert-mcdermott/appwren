// Retirements: those under way, with their progress and dates, and those done, with the
// savings each realized and the total by year.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { recordChip } from "../components/record.js";
import { card, emptyState, pageHeader, pill, stat } from "../components/ui.js";
import { show } from "./page.js";

const money = (value) => (value == null ? h("span", { class: "subtle" }, "Withheld") : Number(value).toLocaleString());

export function retirementReport(main) {
  return show(main, {
    title: "Retirements",
    load: async () => (await get("/api/v1/retirements", null, { fresh: true })).data,
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Retirements",
        lede: "Applications being retired, with how far each has got, and those retired, with what each saves a year: its annual cost when it was retired." }),
      h("div", { class: "grid-3" }, stat(String(data.under_way.length), "Under way"), stat(String(data.done.length), "Done"),
        stat(Number(data.savings).toLocaleString(), "Saved a year, all told")),
      card({ title: plural(data.under_way.length, "retirement") + " under way", flush: data.under_way.length > 0 },
        data.under_way.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Application", "To be retired by", "Steps done"].map((text) => h("th", { scope: "col" }, text)))),
          h("tbody", {}, data.under_way.map((item) => h("tr", {}, h("td", {}, h("a", { class: "cell-main", href: `/applications/${item.ref}?tab=retirement` }, item.name), h("div", { class: "cell-sub" }, item.ref)),
            h("td", { class: "nowrap" }, date(item.planned_on), item.late ? h("div", {}, pill("Past its date", "danger")) : null),
            h("td", {}, `${item.progress} of ${item.steps}`)))))) : h("p", { class: "muted" }, "None. A retirement is planned on the application's Retirement part.")),
      card({ title: "Done", flush: data.done.length > 0 },
        data.done.length ? [h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Application", "Retired", "Saves a year"].map((text, i) => h("th", { scope: "col", class: i === 2 ? "numeric" : null }, text)))),
          h("tbody", {}, data.done.map((item) => h("tr", {}, h("td", {}, recordChip(item)), h("td", { class: "nowrap" }, date(item.completed_on)),
            h("td", { class: "numeric" }, money(item.savings))))))),
        data.savings_by_year.length ? h("p", { class: "card-note muted" }, "By the year each was retired: ",
          data.savings_by_year.map((row) => `${row.year}, ${Number(row.savings).toLocaleString()}`).join("; "), ".") : null,
        data.withheld ? h("p", { class: "card-note subtle" }, `What ${plural(data.withheld, "application")} cost is not shown to you, and is left out of the totals.`) : null]
          : emptyState({ iconName: "retire", title: "Nothing retired through a plan yet", text: "When every step of a retirement plan is done, the application is retired and its savings are counted here." })),
    ),
  });
}
