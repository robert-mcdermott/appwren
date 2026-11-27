// The portfolio chart: business value against technical health (or against cost and burden),
// each application a bubble sized by its cost, where the reader may see it, and colored by
// its risk exposure. A table of the same points follows, for reading and for screen readers.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { hrefOf } from "../components/record.js";
import { card, dispositionBadge, emptyState, pageHeader } from "../components/ui.js";
import { filterSelect } from "./records.js";
import { show } from "./page.js";

const NS = "http://www.w3.org/2000/svg";
const W = 760;
const H = 520;
const PAD = { left: 64, right: 24, top: 24, bottom: 56 };
const VIEWS = {
  health: { x: "technical_health", xLabel: "Technical health", quadrants: ["Modernize or replace", "Invest or maintain", "Retire", "Tolerate"] },
  cost: { x: "cost_burden", xLabel: "Cost and burden (5 is light)", quadrants: ["Valuable, but costly", "Valuable, and light to keep", "Costly, and little value", "Light, but little value"] },
};

function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) if (value != null) node.setAttribute(key, String(value));
  for (const child of children.flat()) if (child != null) node.append(child);
  return node;
}

/** A small, steady offset so that applications with the same scores do not hide each other. */
function jitter(ref, axis) {
  let hash = axis;
  for (const char of ref) hash = (hash * 31 + char.charCodeAt(0)) % 9973;
  return ((hash % 100) / 100 - 0.5) * 0.16;
}

function chart(rows, view, thresholds, vocab) {
  const spec = VIEWS[view];
  const sx = (v) => PAD.left + ((v - 1) / 4) * (W - PAD.left - PAD.right);
  const sy = (v) => H - PAD.bottom - ((v - 1) / 4) * (H - PAD.top - PAD.bottom);
  const costs = rows.map((r) => r.annual_cost).filter((c) => typeof c === "number" && c > 0);
  const most = Math.max(1, ...costs);
  const radius = (cost) => (typeof cost === "number" && cost > 0 ? 6 + 22 * Math.sqrt(cost / most) : 8);
  const tx = thresholds[view === "health" ? "health" : "cost"];
  const ty = thresholds.value;
  const grid = [1, 2, 3, 4, 5].flatMap((v) => [
    svg("line", { class: "chart-grid", x1: sx(v), x2: sx(v), y1: sy(1), y2: sy(5) }),
    svg("line", { class: "chart-grid", x1: sx(1), x2: sx(5), y1: sy(v), y2: sy(v) }),
    svg("text", { class: "chart-tick", x: sx(v), y: H - PAD.bottom + 18, "text-anchor": "middle" }, String(v)),
    svg("text", { class: "chart-tick", x: PAD.left - 12, y: sy(v) + 4, "text-anchor": "end" }, String(v)),
  ]);
  const [tl, tr, bl, br] = spec.quadrants;
  const quadrant = (text, x, y, anchor) => svg("text", { class: "chart-quadrant", x, y, "text-anchor": anchor }, text);
  const bubbles = [...rows].sort((a, b) => (b.annual_cost || 0) - (a.annual_cost || 0)).map((r) => {
    const x = r.scores[spec.x] + jitter(r.ref, 1);
    const y = r.scores.business_value + jitter(r.ref, 2);
    const risk = r.scores.risk_exposure;
    const level = risk == null ? 0 : Math.min(5, Math.max(1, Math.round(risk)));
    const words = `${r.name}: value ${r.scores.business_value.toFixed(1)}, ${spec.xLabel.toLowerCase()} ${r.scores[spec.x].toFixed(1)}, risk exposure ${risk == null ? "unknown" : risk.toFixed(1)}, recommended ${r.recommendation ? label(vocab, "dispositions", r.recommendation) : "nothing"}`;
    // A shortcut for the pointer; the table below is the way in for the keyboard and screen readers.
    const detail = `${r.ref} · value ${r.scores.business_value.toFixed(1)} · ${spec.xLabel.toLowerCase()} ${r.scores[spec.x].toFixed(1)} · `
      + `risk exposure ${risk == null ? "unknown" : risk.toFixed(1)} · ${r.recommendation ? label(vocab, "dispositions", r.recommendation) : "no recommendation"}`;
    return svg("a", { href: hrefOf(r.ref), "aria-label": words, tabindex: "-1", "data-name": r.name, "data-detail": detail },
      svg("title", {}, words),
      svg("circle", { class: "bubble", "data-level": level, "data-mismatch": String(r.mismatch), cx: sx(Math.min(5, Math.max(1, x))), cy: sy(Math.min(5, Math.max(1, y))), r: radius(r.annual_cost) }));
  });
  const drawing = svg("svg", { class: "chart portfolio-chart", viewBox: `0 0 ${W} ${H}`, role: "img", "data-equivalent": "portfolio-table", "aria-label": `Business value against ${spec.xLabel.toLowerCase()}, ${rows.length} applications` },
    grid,
    svg("rect", { class: "chart-zone", x: sx(tx), y: sy(5), width: sx(5) - sx(tx), height: sy(ty) - sy(5) }),
    svg("line", { class: "chart-threshold", x1: sx(tx), x2: sx(tx), y1: sy(1), y2: sy(5) }),
    svg("line", { class: "chart-threshold", x1: sx(1), x2: sx(5), y1: sy(ty), y2: sy(ty) }),
    svg("text", { class: "chart-axis", x: (sx(1) + sx(5)) / 2, y: H - 14, "text-anchor": "middle" }, spec.xLabel),
    svg("text", { class: "chart-axis", x: 18, y: (sy(1) + sy(5)) / 2, "text-anchor": "middle", transform: `rotate(-90 18 ${(sy(1) + sy(5)) / 2})` }, "Business value"),
    bubbles,
    // The quarters' names go over the bubbles, so a crowded corner never hides its own name.
    quadrant(tl, sx(1) + 8, sy(5) + 16, "start"), quadrant(tr, sx(5) - 8, sy(5) + 16, "end"),
    quadrant(bl, sx(1) + 8, sy(1) - 10, "start"), quadrant(br, sx(5) - 8, sy(1) - 10, "end"));
  return withTip(drawing);
}

/** A label that follows the pointer over a bubble: which application, and where it stands.
 * For the pointer only; the table beneath the chart says the same for everyone. */
function withTip(drawing) {
  const name = h("strong", {});
  const detail = h("span", { class: "cell-sub" });
  const tip = h("div", { class: "chart-tip", "aria-hidden": "true", hidden: true }, name, detail);
  const wrap = h("div", { class: "chart-wrap" }, drawing, tip);
  const place = (event) => {
    const link = event.target.closest?.("a[data-name]");
    if (!link) {
      tip.hidden = true;
      return;
    }
    name.textContent = link.getAttribute("data-name");
    detail.textContent = link.getAttribute("data-detail");
    tip.hidden = false;
    const box = wrap.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    const flip = x > box.width - 280;
    tip.style.setProperty("left", `${flip ? Math.max(0, x - 16 - tip.offsetWidth) : x + 16}px`);
    tip.style.setProperty("top", `${Math.max(0, y - tip.offsetHeight - 12)}px`);
  };
  drawing.addEventListener("mousemove", place);
  drawing.addEventListener("mouseleave", () => { tip.hidden = true; });
  return wrap;
}

function legend(withheld) {
  return h("div", { class: "row wrap chart-legend" },
    h("span", { class: "muted" }, "Color: risk exposure, from much (1) to little (5)"),
    [1, 2, 3, 4, 5].map((level) => h("span", { class: "legend-key" }, h("span", { class: "legend-swatch", "data-level": level }), String(level))),
    h("span", { class: "muted" }, withheld ? "Size: the same for all; cost is shown only to people with a role over each application." : "Size: annual cost"),
    h("span", { class: "muted" }, "A dashed ring: the decision differs from the recommendation."));
}

export function portfolioChart(main) {
  return show(main, {
    title: "Portfolio chart",
    load: async () => {
      const params = Object.fromEntries(query());
      delete params.view;
      const [page, model, vocab, unitIndex] = await Promise.all([get("/api/v1/portfolio", params, { fresh: true }),
        get("/api/v1/scoring-model"), vocabularies(), units()]);
      return { rows: page.data, thresholds: model.data.thresholds, vocab, units: unitIndex };
    },
    view: (data) => {
      const { vocab } = data;
      const view = query().get("view") === "cost" ? "cost" : "health";
      const spec = VIEWS[view];
      const live = data.rows.filter((r) => !["retired", "archived"].includes(r.lifecycle));
      const placed = live.filter((r) => r.scores.business_value != null && r.scores[spec.x] != null && !r.thin.business_value && !r.thin[spec.x]);
      const unplaced = live.filter((r) => !placed.includes(r));
      const withheld = placed.some((r) => r.annual_cost === "withheld");
      const toggle = h("div", { class: "segmented", role: "group", "aria-label": "Compare value with" },
        Object.entries({ health: "Value and health", cost: "Value and cost" }).map(([key, text]) =>
          h("button", { type: "button", "aria-pressed": String(view === key), onclick: () => setQuery({ view: key === "health" ? null : key }) }, text)));
      const bar = h("div", { class: "filters" }, toggle,
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        filterSelect("domain", options(vocab, "domains", { blank: "Any domain" }), "Domain"),
        filterSelect("sourcing", options(vocab, "sourcing", { blank: "Any sourcing" }), "Sourcing"),
        filterSelect("lifecycle", options(vocab, "lifecycle", { blank: "Any stage" }), "Lifecycle stage"));
      const table = h("div", { class: "table-wrap" }, h("table", { class: "table", id: "portfolio-table" },
        h("caption", { class: "sr-only" }, "The applications on the chart"),
        h("thead", {}, h("tr", {}, ["Application", "Value", "Health", "Cost", "Risk", "Confidence", "Recommended", "Decided"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", {}, placed.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name), h("div", { class: "cell-sub" }, r.ref)),
          ["business_value", "technical_health", "cost_burden", "risk_exposure"].map((k) => h("td", { class: "numeric" }, r.scores[k] == null ? "—" : r.scores[k].toFixed(1))),
          h("td", { class: "numeric" }, `${r.confidence}%`),
          h("td", {}, r.recommendation ? dispositionBadge(r.recommendation, label(vocab, "dispositions", r.recommendation)) : "—"),
          h("td", {}, r.decision ? dispositionBadge(r.decision, label(vocab, "dispositions", r.decision), { decided: true }) : h("span", { class: "subtle" }, "None")))))));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Portfolio", title: "Portfolio chart",
          lede: "Each application where its scores put it. Up is more valuable; right is healthier, or lighter to keep. The shaded corner is where to invest." }),
        bar,
        placed.length ? card({ title: plural(placed.length, "application") + " placed" }, chart(placed, view, data.thresholds, vocab), legend(withheld))
          : emptyState({ iconName: "chart", title: "Nothing to place yet", text: "An application is placed once enough is known about its value and health. Assess some applications first." }),
        unplaced.length ? card({ title: `${plural(unplaced.length, "application")} not placed` },
          h("p", { class: "muted" }, "Too little is known about their value or health to place them. Each opens to what is missing."),
          h("div", { class: "chips" }, unplaced.map((r) => h("a", { class: "chip", "data-record": "application", href: `${hrefOf(r.ref)}?tab=scores` },
            h("span", { class: "truncate" }, r.name), h("span", { class: "ref" }, `${r.confidence}%`))))) : null,
        placed.length ? card({ title: "The same, as a table", flush: true }, table) : null);
    },
  });
}
