// Leadership reports: made once for a period by a manager, and kept whole. Reopening one
// reads what was kept, with its digest and whether it still matches. Each prints cleanly.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, dateTime, plural } from "../core/format.js";
import { navigate } from "../core/router.js";
import { can } from "../core/session.js";
import { segments } from "../components/charts.js";
import { banner, field, submit } from "../components/form.js";
import { closeOverlay, openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill, stat } from "../components/ui.js";
import { show } from "./page.js";

const DIMENSIONS = [["business_value", "Business value"], ["technical_health", "Technical health"], ["cost_burden", "Cost and burden"], ["risk_exposure", "Risk exposure"]];
const TONES = { invest: "ok", maintain: "info", tolerate: "info", modernize: "warn", migrate: "warn", replace: "warn", consolidate: "warn", retire: "danger" };
const money = (value) => (value == null ? "Not shown" : Number(value).toLocaleString());
const period = (report) => `${date(report.period_from)} to ${date(report.period_to)}`;

function iso(day) {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

/** The last full quarter before today, as a period and a title. */
function lastQuarter(now = new Date()) {
  const start = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3 - 3, 1);
  const end = new Date(start.getFullYear(), start.getMonth() + 3, 0);
  const quarter = Math.floor(start.getMonth() / 3) + 1;
  return { from: iso(start), to: iso(end), title: `Portfolio report, Q${quarter} ${start.getFullYear()}` };
}

function table(headings, rows, numeric = []) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, headings.map((text, index) => h("th", { scope: "col", class: numeric.includes(index) ? "numeric" : null }, text)))),
    h("tbody", {}, rows.map((cells) => h("tr", {}, cells.map((cell, index) => h("td", { class: numeric.includes(index) ? "numeric" : null }, cell)))))));
}

function counts(items, heading) {
  return items.length ? table([heading, "Applications"], items.map((item) => [item.label, String(item.count)]), [1]) : h("p", { class: "muted" }, "None.");
}

export function reportList(main) {
  return show(main, {
    title: "Leadership reports",
    load: async () => (await get("/api/v1/reports", null, { fresh: true })).data,
    view: (rows) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Reports", title: "Leadership reports",
        lede: "A report for a period, often a quarter: where the portfolio stood, and what was decided, reviewed, started, finished, and retired in it. Each is worked out once and kept as it was made.",
        actions: can("manage") ? button("Make a report", { kind: "btn-primary", iconName: "plus", onclick: makeOne }) : null }),
      card({ title: plural(rows.length, "report"), flush: rows.length > 0 },
        rows.length ? table(["Report", "Period", "Made"], rows.map((row) => [
          [h("a", { class: "cell-main", href: `/reports/${row.ref}` }, row.title), h("div", { class: "cell-sub" }, row.ref)],
          period(row), [date(row.made_at), h("div", { class: "cell-sub" }, row.made_by)]]))
          : emptyState({ iconName: "chart", title: "No report yet", text: "A manager makes one for a period that has ended. It keeps what it says from then on." })),
    ),
  });
}

function makeOne() {
  const suggested = lastQuarter();
  openOverlay({ title: "Make a leadership report", kind: "dialog", render: (body, footer) => {
    const title = field("Title", { required: true, value: suggested.title });
    const from = field("From", { type: "date", required: true, value: suggested.from });
    const to = field("To", { type: "date", required: true, value: suggested.to, hint: "Today or earlier. The report is worked out now, and kept as it is." });
    const problem = banner();
    const save = button("Make it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, fields: { title, period_from: from, period_to: to }, banner: problem,
        run: () => post("/api/v1/reports", { title: title.input.value, period_from: from.input.value, period_to: to.input.value }) });
      if (done) {
        closeOverlay();
        toast(`${done.data.ref} is made.`);
        navigate(`/reports/${done.data.ref}`);
      }
    });
    body.append(h("div", { class: "stack" }, problem, title.node, h("div", { class: "grid-2" }, from.node, to.node)));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: closeOverlay })));
    footer.hidden = false;
  } });
}

function standing(content) {
  const portfolio = content.portfolio;
  const levels = portfolio.maturity.levels;
  return card({ title: "Where the portfolio stood" }, h("div", { class: "stack" },
    h("p", { class: "muted" }, `${plural(portfolio.total, "application")} in service when the report was made.`,
      portfolio.cost != null ? ` Together they cost ${money(portfolio.cost)} a year.` : ""),
    h("div", { class: "grid-2" },
      h("div", { class: "stack" }, h("h3", { class: "eyebrow" }, "Recommended"),
        segments(portfolio.recommendations.map((item) => ({ label: item.label, value: item.count, tone: TONES[item.key] ?? "" })), { label: "Applications by recommendation" }),
        h("h3", { class: "eyebrow" }, "Decided"), counts(portfolio.decisions, "Decision on record")),
      h("div", { class: "stack" }, h("h3", { class: "eyebrow" }, "Needs attention"), counts(portfolio.headline, "What needs attention"),
        h("h3", { class: "eyebrow" }, "Flags raised"), counts(portfolio.flags, "Flag"),
        h("h3", { class: "eyebrow" }, "Engineering maturity"),
        counts(levels.map(([key, text]) => ({ label: text, count: portfolio.maturity.counts[key] ?? 0 })).filter((item) => item.count), "Level")))));
}

function movement(found) {
  if (!found) return card({ title: "How the scores moved" }, h("p", { class: "muted" }, "No two portfolio snapshots fall in or before the period, so there is nothing to compare."));
  const a = found.before.figures.averages;
  const b = found.after.figures.averages;
  const change = (key) => (a[key] == null || b[key] == null ? "—" : `${b[key] - a[key] > 0 ? "+" : ""}${(b[key] - a[key]).toFixed(2)}`);
  return card({ title: "How the scores moved" },
    h("p", { class: "muted" }, `From the snapshot “${found.before.name}” (${date(found.before.taken_at)}) to “${found.after.name}” (${date(found.after.taken_at)}).`),
    table(["Average", found.before.name, found.after.name, "Change"],
      DIMENSIONS.map(([key, text]) => [text, a[key] == null ? "—" : a[key].toFixed(2), b[key] == null ? "—" : b[key].toFixed(2), change(key)]), [1, 2, 3]),
    h("p", { class: "card-note" }, [
      `${plural(found.recommendation_changed, "application")} changed recommendation`,
      `${found.scores_moved} moved by ${found.threshold} or more on a score`,
      `${plural(found.flags_raised, "flag")} raised and ${found.flags_cleared} cleared`,
      `${found.added} newly scored`].join("; ") + "."));
}

function decided(found) {
  return card({ title: `${plural(found.count, "decision")} in the period`, flush: found.count > 0 },
    found.count ? [h("p", { class: "card-note" }, found.by_disposition.map((item) => `${item.label} ${item.count}`).join(", "),
      found.against_recommendation ? `. ${plural(found.against_recommendation, "decision")} went another way than recommended.` : "."),
    table(["Application", "Decided", "Recommended", "On", "By"], found.items.map((item) => [recordChip(item), item.disposition, item.recommendation ?? "—", date(item.decided_on), item.by]))]
      : h("p", { class: "muted" }, "None recorded in the period."));
}

function planning(content) {
  const { initiatives, requests, retirements, reviews } = content;
  return [
    card({ title: "Reviews closed", flush: reviews.length > 0 },
      reviews.length ? table(["Review", "Held", "On the agenda", "Decided at it"], reviews.map((item) => [recordChip(item), date(item.held_on), String(item.items), String(item.decided)]), [2, 3])
        : h("p", { class: "muted" }, "None closed in the period.")),
    card({ title: "Initiatives", flush: initiatives.under_way.length + initiatives.done.length > 0 },
      initiatives.under_way.length || initiatives.done.length
        ? table(["Initiative", "Kind", "Ends", "Stage"], [
          ...initiatives.under_way.map((item) => [recordChip(item), item.kind, item.ends_on ? date(item.ends_on) : "—", item.late ? pill("Under way, past its end", "danger") : pill("Under way", "info")]),
          ...initiatives.done.map((item) => [recordChip(item), item.kind, item.ends_on ? date(item.ends_on) : "—", pill("Done", "ok")])])
        : h("p", { class: "muted" }, "None under way or done.")),
    card({ title: "Requests for something new" },
      h("div", { class: "grid-3" }, stat(String(requests.opened), "Asked for in the period"), stat(String(requests.approved), "Approved"),
        stat(String(requests.met + requests.declined), "Met by one on record, or declined")),
      h("p", { class: "card-note muted" }, `${plural(requests.open, "request")} still open when the report was made.`)),
    card({ title: "Retired in the period", flush: retirements.completed.length > 0 },
      retirements.completed.length ? [table(["Application", "Retired", "Saves a year"], retirements.completed.map((item) => [recordChip(item), date(item.completed_on), money(item.savings)]), [2]),
        h("p", { class: "card-note" }, `Saved ${money(retirements.savings)} a year, all told.`)]
        : h("p", { class: "muted" }, "Nothing retired through a plan in the period.")),
  ];
}

export function reportPage(main, { ref }) {
  return show(main, {
    title: ref,
    load: async () => (await get(`/api/v1/reports/${ref}`)).data,
    view: (report) => {
      const content = report.content;
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Leadership report", title: report.title, lede: `${period(report)}. ${report.ref}.`,
          actions: button("Print", { onclick: () => window.print() }) }),
        report.intact ? null : alert("danger", "This report no longer matches its digest: what is stored has been changed since it was made."),
        h("div", { class: "grid-3" }, stat(String(content.decided.count), "Decisions in the period"),
          stat(String(content.retirements.completed.length), "Applications retired"),
          stat(String(content.initiatives.under_way.length), `Initiatives under way${content.initiatives.late ? `, ${content.initiatives.late} past their end` : ""}`)),
        standing(content), movement(content.movement), decided(content.decided), ...planning(content),
        h("p", { class: "subtle" }, `Made ${dateTime(report.made_at)} by ${report.made_by}, and kept as it was then. Digest `,
          h("span", { class: "mono" }, report.digest), report.intact ? ", which it still matches." : "."));
    },
  });
}
