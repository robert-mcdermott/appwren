// Trends: two portfolio snapshots side by side (or one and today), with what moved between
// them: the figures each held, changed recommendations, scores that moved, flags that came
// or went, applications added or gone, and the decisions recorded between them.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date, dateTime, plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { recordChip } from "../components/record.js";
import { card, dispositionBadge, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const DIMENSIONS = [["business_value", "Business value"], ["technical_health", "Technical health"], ["cost_burden", "Cost and burden"], ["risk_exposure", "Risk exposure"]];

function picker(name, snapshots, value, blank) {
  return h("select", { class: "select", "aria-label": name === "before" ? "From the snapshot" : "To", onchange: (event) => setQuery({ [name]: event.target.value || null }) },
    blank ? h("option", { value: "", selected: !value }, blank) : null,
    snapshots.map((s) => h("option", { value: s.ref, selected: s.ref === value }, `${s.name} (${date(s.taken_at)})`)));
}

function delta(a, b, digits = 0) {
  if (a == null || b == null) return h("span", { class: "subtle" }, "—");
  const change = Number((b - a).toFixed(digits));
  return change === 0 ? h("span", { class: "subtle" }, "No change") : h("span", {}, `${change > 0 ? "+" : ""}${change.toLocaleString()}`);
}

function badge(vocab, key) {
  return key ? dispositionBadge(key, label(vocab, "dispositions", key)) : h("span", { class: "subtle" }, "None");
}

export function trendsPage(main) {
  const params = Object.fromEntries(query());
  return show(main, {
    title: "Trends",
    load: async () => {
      const [snapshots, vocab] = await Promise.all([get("/api/v1/portfolio-snapshots", null, { fresh: true }), vocabularies()]);
      const list = snapshots.data;
      const before = params.before ?? list[1]?.ref ?? list[0]?.ref;
      const after = params.before ? params.after : (list[1] ? list[0].ref : null);
      const found = before ? (await get("/api/v1/trends", { before, after }, { fresh: true })).data : null;
      return { snapshots: list, vocab, found, before, after };
    },
    view: ({ snapshots, vocab, found, before, after }) => {
      if (!found) {
        return h("div", { class: "stack-lg" }, pageHeader({ eyebrow: "Reports", title: "Trends" }),
          emptyState({ iconName: "chart", title: "No portfolio snapshot yet", text: "A snapshot is taken on the first of each month, or by a manager at any time. Trends compare two of them." }));
      }
      const a = found.before.figures;
      const b = found.after.figures;
      const keys = [...new Set([...Object.keys(a.recommendations), ...Object.keys(b.recommendations)])];
      const row = (text, x, y, digits = 0) => h("tr", {}, h("th", { scope: "row" }, text),
        h("td", { class: "numeric" }, x == null ? "—" : Number(x).toLocaleString()), h("td", { class: "numeric" }, y == null ? "—" : Number(y).toLocaleString()),
        h("td", { class: "numeric" }, delta(x, y, digits)));
      const figures = card({ title: "The figures", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"), h("th", { scope: "col", class: "numeric" }, found.before.name),
          h("th", { scope: "col", class: "numeric" }, found.after.name), h("th", { scope: "col", class: "numeric" }, "Change"))),
        h("tbody", {}, row("Applications scored", a.scored, b.scored), row("With low confidence", a.low_confidence, b.low_confidence),
          keys.map((key) => row(`Recommended: ${label(vocab, "dispositions", key)}`, a.recommendations[key] ?? 0, b.recommendations[key] ?? 0)),
          DIMENSIONS.map(([key, text]) => row(`Average ${text.toLowerCase()}`, a.averages[key], b.averages[key], 2))))));
      const moved = found.moved;
      const recs = card({ title: `${plural(moved.recommendation.length, "recommendation")} changed`, flush: moved.recommendation.length > 0 },
        moved.recommendation.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Application", "Was", "Is"].map((text) => h("th", { scope: "col" }, text)))),
          h("tbody", {}, moved.recommendation.map((item) => h("tr", {}, h("td", {}, recordChip(item)), h("td", {}, badge(vocab, item.from)), h("td", {}, badge(vocab, item.to)))))))
          : h("p", { class: "muted" }, "No recommendation changed."));
      const scores = card({ title: `${plural(moved.scores.length, "application")} whose scores moved by ${found.threshold} or more`, flush: moved.scores.length > 0 },
        moved.scores.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Application", "What moved"].map((text) => h("th", { scope: "col" }, text)))),
          h("tbody", {}, moved.scores.map((item) => h("tr", {}, h("td", {}, recordChip(item)),
            h("td", {}, Object.entries(item.changes).map(([key, c]) => h("div", {}, `${DIMENSIONS.find(([k]) => k === key)[1]}: ${c.from.toFixed(1)} to ${c.to.toFixed(1)}`))))))))
          : h("p", { class: "muted" }, "No score moved that far."));
      const decided = card({ title: `${plural(found.decided.length, "decision")} recorded between them`, flush: found.decided.length > 0 },
        found.decided.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Application", "Decided", "Recommended then", "By"].map((text) => h("th", { scope: "col" }, text)))),
          h("tbody", {}, found.decided.map((d) => h("tr", {}, h("td", {}, recordChip(d)), h("td", {}, dispositionBadge(d.disposition, label(vocab, "dispositions", d.disposition), { decided: true })),
            h("td", {}, badge(vocab, d.recommendation)), h("td", {}, d.by, h("div", { class: "cell-sub" }, date(d.decided_on))))))))
          : h("p", { class: "muted" }, "None."));
      const flags = moved.flags.length ? card({ title: `${plural(moved.flags.length, "application")} whose flags changed`, flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, ["Application", "Raised", "Cleared"].map((text) => h("th", { scope: "col" }, text)))),
        h("tbody", {}, moved.flags.map((item) => h("tr", {}, h("td", {}, recordChip(item)), h("td", {}, item.raised.join(", ") || "—"), h("td", {}, item.cleared.join(", ") || "—"))))))) : null;
      const comings = found.added.length || found.gone.length ? card({ title: "Added and gone" }, h("div", { class: "stack-sm" },
        found.added.length ? h("p", {}, "Scored only in the later: ", found.added.map((item, i) => [i ? ", " : "", recordChip(item)])) : null,
        found.gone.length ? h("p", {}, "Scored only in the earlier: ", found.gone.map((item, i) => [i ? ", " : "", recordChip(item)])) : null)) : null;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Trends",
          lede: "Two portfolio snapshots side by side, or one and today: the figures each held, and what moved between them. Each snapshot is read as it was kept." }),
        h("div", { class: "filters" }, picker("before", snapshots, before), picker("after", snapshots, after ?? "", "Today")),
        h("p", { class: "subtle" }, `From ${found.before.name}, ${dateTime(found.before.taken_at)}, to ${found.after.taken_at ? `${found.after.name}, ${dateTime(found.after.taken_at)}` : "today"}.`),
        figures, recs, scores, decided, flags, comings);
    },
  });
}
