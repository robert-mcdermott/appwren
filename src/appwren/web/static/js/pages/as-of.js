// As of: the portfolio, or one application, as it stood at the end of a chosen day, read
// from the history. Nothing is stored for it.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { recordChip } from "../components/record.js";
import { card, dispositionBadge, emptyState, pageHeader, pill, stat } from "../components/ui.js";
import { show } from "./page.js";

const DIMENSIONS = [["business_value", "Business value"], ["technical_health", "Technical health"], ["cost_burden", "Cost and burden"], ["risk_exposure", "Risk exposure"]];

function iso(day) {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

/** The day asked for, or the end of the last quarter. */
function chosen() {
  const asked = query().get("on");
  if (asked) return asked;
  const now = new Date();
  return iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 0));
}

function dayPicker(on) {
  const id = "as-of-day";
  return h("div", { class: "filters" }, h("div", { class: "field" }, h("label", { for: id }, "As it stood at the end of"),
    h("input", { id, class: "input", type: "date", value: on, max: iso(new Date()), onchange: (event) => event.target.value && setQuery({ on: event.target.value }) })));
}

function decided(vocab, key) {
  return key ? dispositionBadge(key, label(vocab, "dispositions", key), { decided: true }) : h("span", { class: "subtle" }, "None");
}

export function portfolioAsOf(main) {
  const on = chosen();
  return show(main, {
    title: "As of a day",
    load: async () => {
      const [found, vocab] = await Promise.all([get("/api/v1/as-of", { on }, { fresh: true }), vocabularies()]);
      return { found: found.data, vocab };
    },
    view: ({ found, vocab }) => {
      const rows = found.applications;
      const stage = (key) => label(vocab, "lifecycle", key);
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "As of a day",
          lede: "The applications in service at the end of a day, each with its stage and decision then beside its stage and decision now. Read from the history: nothing here was kept for the purpose." }),
        dayPicker(on),
        h("div", { class: "grid-3" }, stat(String(rows.length), `In service on ${date(found.on)}`),
          stat(String(found.since.added), "Come into service since"), stat(String(found.since.left), "Left service since")),
        found.snapshot ? h("p", { class: "muted" }, "Scores as of that day are those of the snapshot ", h("a", { href: `/trends?before=${found.snapshot.ref}` }, `“${found.snapshot.name}”`), ` (${date(found.snapshot.taken_at)}).`) : null,
        card({ title: plural(rows.length, "application"), flush: rows.length > 0 },
          rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, ["Application then", "Unit", "Stage then", "Stage now", "Decision then", "Decision now"].map((text) => h("th", { scope: "col" }, text)))),
            h("tbody", {}, rows.map((row) => h("tr", {},
              h("td", {}, h("a", { class: "cell-main", href: `/applications/${row.ref}/as-of?on=${found.on}` }, row.name_then ?? row.name),
                h("div", { class: "cell-sub" }, row.ref, row.name_then && row.name_then !== row.name ? `, now ${row.name}` : "")),
              h("td", {}, row.unit ?? "—"), h("td", {}, stage(row.lifecycle)),
              h("td", {}, row.status_now !== "active" ? pill("Archived", "") : row.lifecycle_now === row.lifecycle ? h("span", { class: "subtle" }, "The same") : stage(row.lifecycle_now)),
              h("td", {}, decided(vocab, row.decision)),
              h("td", {}, row.decision_now === row.decision ? h("span", { class: "subtle" }, "The same") : decided(vocab, row.decision_now)))))))
            : emptyState({ iconName: "history", title: "Nothing in service then", text: "Choose a later day." })));
    },
  });
}

function shown(row, which) {
  const value = row[which];
  if (value == null || value === "") return h("span", { class: "subtle" }, "Empty");
  if (row.kind === "date") return date(value);
  if (row.kind === "int") return Number(value).toLocaleString();
  return String(value);
}

export function applicationAsOf(main, params) {
  const on = chosen();
  return show(main, {
    title: `${params.ref} as of ${on}`,
    load: async () => (await get(`/api/v1/applications/${params.ref}/as-of`, { on }, { fresh: true })).data,
    view: (found) => {
      const header = pageHeader({ eyebrow: `Application · ${found.ref}`, title: `${found.name}, as it stood`,
        lede: "Each value at the end of the day chosen, beside its value now, from the history." });
      if (!found.existed) {
        return h("div", { class: "stack-lg" }, header, dayPicker(on),
          emptyState({ iconName: "history", title: `Not on record on ${date(found.on)}`, text: "It was added later. Choose a later day." }));
      }
      const changed = found.fields.filter((row) => row.changed);
      const scores = found.scores;
      return h("div", { class: "stack-lg" }, header, dayPicker(on),
        h("p", {}, h("a", { href: `/applications/${found.ref}` }, "Back to it as it is now"),
          `. ${plural(found.changes_since, "change")} since; ${plural(changed.length, "value")} differ${changed.length === 1 ? "s" : ""} now.`),
        h("div", { class: "grid-2" },
          card({ title: "Its decision then" }, found.decision
            ? h("p", {}, h("strong", {}, found.decision.label), `, decided ${date(found.decision.decided_on)} by ${found.decision.by} (${found.decision.ref}).`)
            : h("p", { class: "muted" }, "No decision was on record.")),
          card({ title: "Its scores then" }, scores
            ? [h("p", { class: "muted" }, `From the snapshot “${scores.snapshot.name}”, ${date(scores.snapshot.taken_at)}.`),
              h("dl", { class: "dl" }, DIMENSIONS.map(([key, text]) => [h("dt", {}, text), h("dd", {}, scores.scores[key] == null ? "Not known" : scores.scores[key].toFixed(1))]))]
            : h("p", { class: "muted" }, "No portfolio snapshot on or before that day holds it."))),
        card({ title: "Its record", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["", `On ${date(found.on)}`, "Now"].map((text, index) => h("th", { scope: "col" }, index ? text : h("span", { class: "sr-only" }, "Field"))))),
          h("tbody", {}, [...changed, ...found.fields.filter((row) => !row.changed)].map((row) => h("tr", {},
            h("th", { scope: "row" }, row.label), h("td", {}, shown(row, "then")),
            h("td", {}, row.changed ? h("strong", {}, shown(row, "now")) : h("span", { class: "subtle" }, "The same")))))))));
    },
  });
}
