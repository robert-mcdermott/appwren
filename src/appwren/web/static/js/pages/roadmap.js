// The roadmap: initiatives on a timeline by their dates, narrowed by unit, kind, or stage,
// each bar a link, with a table that says the same.

import { get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { editRecord } from "../components/record-forms.js";
import { hrefOf } from "../components/record.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const DAY = 86400000;

function filter(name, choices, text) {
  return h("select", { class: "select", "aria-label": text, onchange: (event) => setQuery({ [name]: event.target.value || null }) },
    choices.map(([key, said]) => h("option", { value: key, selected: String(key) === (query().get(name) ?? "") }, said)));
}

export function roadmapPage(main) {
  const params = Object.fromEntries(query());
  return show(main, {
    title: "Roadmap",
    load: async () => {
      const [found, vocab, unitIndex] = await Promise.all([get("/api/v1/roadmap", params, { fresh: true }), vocabularies(), units()]);
      return { ...found.data, vocab, units: unitIndex };
    },
    view: (data) => {
      const { vocab } = data;
      const start = new Date(data.from);
      const span = (new Date(data.to) - start) / DAY;
      const place = (day) => Math.min(100, Math.max(0, ((new Date(day) - start) / DAY / span) * 100));
      const years = [];
      for (let year = start.getFullYear(); year <= new Date(data.to).getFullYear(); year += 1) years.push(year);
      const scale = h("div", { class: "life-row life-scale", "aria-hidden": "true" }, h("span", {}), h("div", { class: "life-track life-years" }, years.map((year) => {
        const mark = h("span", {}, String(year));
        mark.style.setProperty("left", `${place(`${year}-01-01`)}%`);
        return mark;
      })), h("span", {}));
      const bar = (item) => {
        const from = place(item.starts_on ?? item.ends_on ?? data.today);
        const to = place(item.ends_on ?? data.to);
        const line = h("a", { class: "life-bar road-bar", "data-stage": item.stage, href: hrefOf(item.ref), tabindex: "-1", "aria-hidden": "true" });
        line.style.setProperty("left", `${from}%`);
        line.style.setProperty("width", `${Math.max(1, to - from)}%`);
        const now = h("i", { class: "life-today" });
        now.style.setProperty("left", `${place(data.today)}%`);
        return h("div", { class: "life-track" }, line, now);
      };
      const rows = data.initiatives.map((item) => h("div", { class: "life-row" },
        h("div", { class: "life-name" }, h("a", { class: "cell-main", href: hrefOf(item.ref) }, item.name),
          h("div", { class: "cell-sub" }, `${label(vocab, "initiative_kinds", item.kind)} · ${item.unit.name ?? ""}`)),
        bar(item),
        h("div", { class: "life-end" }, h("span", {}, label(vocab, "initiative_stages", item.stage),
          item.ends_on && item.ends_on < data.today && !["done", "cancelled"].includes(item.stage) ? h("span", { class: "text-danger" }, " · past its end") : null),
          h("div", { class: "cell-sub" }, item.starts_on || item.ends_on ? `${item.starts_on ? date(item.starts_on) : "?"} to ${item.ends_on ? date(item.ends_on) : "?"}` : "No dates yet",
            ` · ${plural(item.applications, "application")}`))));
      const add = can("keep") ? button("Add an initiative", { kind: "btn-primary", iconName: "plus", onclick: () => editRecord("initiative", {}) }) : null;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Portfolio", title: "Roadmap",
          lede: "What the decisions commit the organization to: each initiative from its start to its end, with what it changes.",
          actions: [h("a", { class: "btn", href: "/initiatives" }, "As a list"), add] }),
        h("div", { class: "filters" },
          filter("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
          filter("kind", options(vocab, "initiative_kinds", { blank: "Any kind" }), "Kind"),
          filter("stage", options(vocab, "initiative_stages", { blank: "Not done or cancelled" }), "Stage")),
        data.initiatives.length ? card({ title: plural(data.initiatives.length, "initiative") }, h("div", { class: "life-list" }, scale, rows),
          h("p", { class: "subtle life-key" }, "Each bar runs from an initiative's start to its end; one with no end runs off the right. The line is today."),
          data.undated ? h("p", { class: "subtle" }, `${plural(data.undated, "initiative")} has no dates yet, and is drawn at today.`) : null)
          : card({}, emptyState({ iconName: "lifecycle", title: "No initiative here",
            text: "An initiative is a planned change with its dates: start one from a decision on an application's Decisions part, or add one here." })));
    },
  });
}
