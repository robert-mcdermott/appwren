// Data handling: the applications that handle a class of data, with what an analysis of
// risk asks about each. The same rows can be exported.

import { buildUrl, get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { recordChip, supportPill, tierMeter } from "../components/record.js";
import { alert, card, emptyState, pageHeader } from "../components/ui.js";
import { sensitivityPill } from "./data-flows.js";
import { show } from "./page.js";
import { agreementPill } from "./records.js";

const withheld = () => h("span", { class: "subtle" }, "Withheld");
const none = (text = "Not said") => h("span", { class: "subtle" }, text);

export function dataHandling(main) {
  return show(main, {
    title: "Data handling",
    load: async () => {
      const chosen = query().get("data_class");
      const [found, vocab] = await Promise.all([get("/api/v1/data-handling", chosen ? { data_class: chosen } : null, { fresh: true }), vocabularies()]);
      return { found: found.data, vocab };
    },
    view: ({ found, vocab }) => {
      const chosen = found.classes.find((item) => item.key === found.data_class);
      const classes = h("div", { class: "class-picker", role: "group", "aria-label": "Class of data" }, found.classes.map((item) =>
        h("button", { type: "button", class: "class-choice", "aria-pressed": String(item.key === found.data_class),
          onclick: () => setQuery({ data_class: item.key === found.data_class ? null : item.key }, { replace: false }) },
        h("span", { class: "cell-main" }, item.label), sensitivityPill(item.sensitivity),
        h("span", { class: "cell-sub" }, plural(item.applications, "application")))));
      const rows = found.applications;
      const built = (row) => (row.technologies.length
        ? h("div", { class: "stack-sm" }, row.support ? supportPill(row.support) : null,
          h("span", { class: "cell-sub" }, [...new Set(row.technologies.map((t) => [t.name, t.release].filter(Boolean).join(" ")))].join(", ")))
        : none(row.hosting === "vendor_cloud" ? "The vendor's to keep" : "Nothing recorded"));
      const table = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, ["Application", "Accountable", "Where it runs", "Sign-in", "Built on", "Carries it", "Data agreement"].map((text) => h("th", { scope: "col" }, text)))),
        h("tbody", {}, rows.map((row) => h("tr", {},
          h("td", {}, h("div", { class: "stack-sm" }, recordChip(row), tierMeter(vocab, row.tier),
            h("span", { class: "cell-sub" }, [row.unit, row.sourcing ? label(vocab, "sourcing", row.sourcing) : null].filter(Boolean).join(" · ")))),
          h("td", {}, row.accountable.length ? row.accountable.join(", ") : h("span", { class: "pill pill-danger" }, "Nobody")),
          h("td", {}, row.platforms.length ? row.platforms.join(", ") : row.hosting ? label(vocab, "hosting", row.hosting) : none(),
            row.vendor ? h("div", { class: "cell-sub" }, row.vendor) : null),
          h("td", {}, row.sign_in === "withheld" ? withheld() : row.sign_in ? label(vocab, "sign_in", row.sign_in) : none()),
          h("td", {}, built(row)),
          h("td", {}, row.sends || row.receives ? `${row.receives} in, ${row.sends} out` : none("No interface")),
          h("td", {}, row.data_agreement === "withheld" ? withheld() : agreementPill(vocab, row.data_agreement)))))))
        : h("p", { class: "muted" }, "No application in service is recorded as handling it.");
      const notes = chosen ? [
        found.unsupported ? `${plural(found.unsupported, "of them runs", "of them run")} on technology past its end of support.` : null,
        found.no_agreement ? `${plural(found.no_agreement, "is", "are")} under a contract with no data agreement.` : null,
      ].filter(Boolean) : [];
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Data handling",
          lede: "The applications that handle a class of data, with who answers for each, where it runs, how people sign in, what it is built on, and whether a data agreement covers it. Choose a class.",
          actions: chosen ? h("a", { class: "btn", href: buildUrl("/api/v1/exports/data-handling", { data_class: chosen.key, format: "csv" }), download: "" }, "Export") : null }),
        found.classes.some((item) => item.applications) ? classes
          : card({}, emptyState({ iconName: "shield", title: "No application says what data it handles yet",
            text: "Record the classes of data on each application, and this page shows where each class is held." })),
        chosen ? [
          notes.length ? alert(found.unsupported || found.no_agreement ? "warn" : "info", h("p", {}, notes.join(" "))) : null,
          card({ title: `${plural(rows.length, "application handles", "applications handle")} ${chosen.label.toLowerCase()}`,
            actions: h("a", { class: "btn btn-sm", href: `/data-flows?data_class=${chosen.key}` }, `${plural(found.interfaces, "interface carries", "interfaces carry")} it`), flush: rows.length > 0 }, table),
        ] : null);
    },
  });
}
