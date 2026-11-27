// Data flows: where each class of data travels between applications, and where it arrives
// at an application whose record does not say it holds it.

import { get } from "../core/api.js";
import { h, icon } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { recordChip } from "../components/record.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";
import { exportLink } from "./records.js";

const SENSITIVITY = [["Public", ""], ["Internal", ""], ["Confidential", "warn"], ["Restricted", "danger"]];

export function sensitivityPill(level) {
  const [text, tone] = SENSITIVITY[level] ?? ["Not rated", ""];
  return pill(text, tone);
}

export function dataFlows(main) {
  return show(main, {
    title: "Data flows",
    load: async () => {
      const chosen = query().get("data_class");
      const [flows, vocab] = await Promise.all([get("/api/v1/data-flows", chosen ? { data_class: chosen } : null, { fresh: true }), vocabularies()]);
      return { flows: flows.data, vocab };
    },
    view: ({ flows, vocab }) => {
      const chosen = flows.classes.find((item) => item.key === flows.data_class);
      const classes = h("div", { class: "class-picker", role: "group", "aria-label": "Class of data" }, flows.classes.map((item) =>
        h("button", { type: "button", class: "class-choice", "aria-pressed": String(item.key === flows.data_class),
          onclick: () => setQuery({ data_class: item.key === flows.data_class ? null : item.key }, { replace: false }) },
        h("span", { class: "cell-main" }, item.label), sensitivityPill(item.sensitivity),
        h("span", { class: "cell-sub" }, plural(item.interfaces, "interface")))));
      const rows = flows.interfaces;
      const lost = rows.filter((r) => r.undeclared.includes(flows.data_class));
      const table = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "From"), h("th", { scope: "col" }, "To"), h("th", { scope: "col" }, "Interface"),
          h("th", { scope: "col" }, "Method"), h("th", { scope: "col" }, "How often"))),
        h("tbody", {}, rows.map((r) => h("tr", {},
          h("td", {}, r.source ? recordChip(r.source) : ""),
          h("td", {}, h("div", { class: "stack-sm" }, r.target ? recordChip(r.target) : "",
            r.undeclared.includes(flows.data_class) ? h("span", { class: "flag flag-warn" }, icon("flag", "icon icon-sm"), "Its record does not list this class") : null)),
          h("td", {}, h("a", { class: "cell-main", href: `/interfaces/${r.ref}` }, r.name), h("div", { class: "cell-sub" }, r.ref)),
          h("td", {}, label(vocab, "interface_methods", r.method)),
          h("td", {}, r.frequency ? label(vocab, "interface_frequencies", r.frequency) : h("span", { class: "subtle" }, "Not said")))))))
        : h("p", { class: "muted" }, "No interface is recorded as carrying it.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Data flows",
          lede: "Where each class of data travels between applications. Choose a class to follow it.",
          actions: [h("a", { class: "btn", href: "/interfaces" }, `All ${plural(flows.total, "interface")}`), exportLink("interfaces")] }),
        flows.total || flows.classes.length ? classes : null,
        !flows.total ? card({}, emptyState({ iconName: "flow", title: "No interfaces recorded yet",
          text: "An interface says what one application sends to another: how, how often, and which classes of data. Add one from an application\u2019s Connections." })) : null,
        chosen ? [
          lost.length ? alert("warn", h("p", {}, `${plural(lost.length, "interface delivers", "interfaces deliver")} ${chosen.label.toLowerCase()} to an application whose record does not list it. `,
            "Its risk exposure is worked out from the classes its record lists, so it is understated until the record or the interface is corrected.")) : null,
          card({ title: `${plural(rows.length, "interface carries", "interfaces carry")} ${chosen.label.toLowerCase()}`, flush: rows.length > 0 }, table),
          card({ title: `${plural(flows.holders.length, "application holds", "applications hold")} it` }, flows.holders.length
            ? h("div", { class: "chips" }, flows.holders.map((app) => recordChip(app)))
            : h("p", { class: "muted" }, "No application's record lists it.")),
        ] : null);
    },
  });
}
