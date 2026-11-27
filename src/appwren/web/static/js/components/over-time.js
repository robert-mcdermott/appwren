// An application's scores over time: a line for each score across its snapshots, and a table
// that says the same.

import { h } from "../core/dom.js";
import { date } from "../core/format.js";
import { card } from "./ui.js";

const LINES = [["business_value", "Value"], ["technical_health", "Health"], ["cost_burden", "Cost"], ["risk_exposure", "Risk"]];
const SVG = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function chart(points) {
  const width = 560;
  const height = 160;
  const x = (i) => 30 + (points.length === 1 ? 0 : (i * (width - 60)) / (points.length - 1));
  const y = (v) => height - 20 - ((v - 1) / 4) * (height - 40);
  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "over-time", "aria-hidden": "true" });
  for (const level of [1, 2, 3, 4, 5]) {
    root.append(svg("line", { x1: 30, x2: width - 30, y1: y(level), y2: y(level), class: "over-grid" }));
    const tick = svg("text", { x: 8, y: y(level) + 4, class: "over-tick" });
    tick.textContent = String(level);
    root.append(tick);
  }
  LINES.forEach(([key], index) => {
    const known = points.map((p, i) => [i, p.scores[key]]).filter(([, v]) => v != null);
    if (!known.length) return;
    root.append(svg("polyline", { points: known.map(([i, v]) => `${x(i)},${y(v)}`).join(" "), class: `over-line over-${index}` }));
  });
  return root;
}

/** On an application's Scores part. */
export function overTime(points) {
  if (!points?.length) return null;
  return card({ title: "Its scores over time", flush: true },
    h("div", { class: "card-note" }, chart(points),
      h("p", { class: "subtle over-key" }, LINES.map(([, text], index) => h("span", { class: `over-key-${index}` }, text)))),
    h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "When"), h("th", { scope: "col" }, "Kept for"), LINES.map(([, text]) => h("th", { scope: "col", class: "numeric" }, text)), h("th", { scope: "col", class: "numeric" }, "Confidence"))),
      h("tbody", {}, points.slice().reverse().map((p) => h("tr", {}, h("td", { class: "nowrap" }, date(p.taken_at)), h("td", {}, p.reason === "decision" ? "A decision" : p.reason === "portfolio" ? "A portfolio snapshot" : p.reason),
        LINES.map(([key]) => h("td", { class: "numeric" }, p.scores[key] == null ? "—" : p.scores[key].toFixed(1))), h("td", { class: "numeric" }, `${p.confidence}%`)))))));
}
