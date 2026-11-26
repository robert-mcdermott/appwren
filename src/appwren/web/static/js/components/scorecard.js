// Scores, confidence, the recommendation, and flags, and the working behind each.

import { h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { label } from "../core/lookups.js";
import { openOverlay } from "./overlay.js";
import { card, dispositionBadge, flag, scoreFigure } from "./ui.js";

export const DIMENSIONS = [
  ["business_value", "Value"],
  ["technical_health", "Health"],
  ["cost_burden", "Cost"],
  ["risk_exposure", "Risk"],
];

const STATE_WORDS = { known: null, unknown: "Unknown", not_applicable: "Not applicable" };
// Where a person goes to supply what is missing.
const WHERE = {
  assessment: ["Answer the assessment", "?tab=assessment"],
  components: ["Record its components and what they are built on", "?tab=components"],
  capabilities: ["Say which capabilities it serves", "?tab=capabilities"],
};

/** The four scores and confidence, each a button that opens its working. */
export function scorecard(result, { onOpen }) {
  const confidence = result.confidence;
  return h("div", { class: "scorecard", role: "group", "aria-label": "Scores" },
    DIMENSIONS.map(([key, short]) => {
      const dim = result.dimensions[key];
      return h("button", { type: "button", class: "scorecard-item", onclick: () => onOpen(key),
        "aria-label": `${dim.label}: ${dim.score == null ? "unknown" : dim.score.toFixed(1)}. Show the working.` },
      h("span", { class: "scorecard-label" }, short),
      scoreFigure(dim.score, { coverage: dim.coverage }));
    }),
    h("button", { type: "button", class: "scorecard-item", onclick: () => onOpen("confidence"),
      "aria-label": `Data confidence ${confidence}%. Show what is missing.` },
    h("span", { class: "scorecard-label" }, "Confidence"),
    h("span", { class: "confidence", "data-low": String(confidence < result.thresholds.confidence) },
      h("span", { class: "score-value" }, `${confidence}%`))));
}

/** The recommendation, the decision beside it when there is one, and the flags. */
export function verdict(result, vocab, decision = null) {
  const rec = result.recommendation;
  return h("div", { class: "verdict" },
    h("div", { class: "verdict-row" },
      h("span", { class: "verdict-label" }, "Recommended"),
      rec ? dispositionBadge(rec, label(vocab, "dispositions", rec)) : h("span", { class: "subtle" }, "Nothing: not in service"),
      result.rule ? h("span", { class: "subtle" }, `by the rule “${result.rule.label}”`) : null,
      decision ? [h("span", { class: "verdict-label" }, "Decided"), dispositionBadge(decision.disposition, label(vocab, "dispositions", decision.disposition), { decided: true })] : null),
    result.flags.length ? h("div", { class: "row-sm wrap" }, result.flags.map((f) => flag(f.severity, f.text))) : null);
}

function factorRow(factor) {
  const state = STATE_WORDS[factor.state];
  const level = factor.level === "withheld" ? "—" : factor.level ?? "—";
  return h("tr", { "data-state": factor.state },
    h("th", { scope: "row" }, factor.label),
    h("td", { class: "numeric" }, state ? h("span", { class: "subtle" }, state) : String(level)),
    h("td", { class: "numeric" }, String(factor.weight)),
    h("td", {}, factor.why ?? ""));
}

/** One dimension's working: each factor, its level, its weight, and why, then the sum. */
export function working(result, key) {
  const dim = result.dimensions[key];
  const known = dim.factors.filter((f) => f.state === "known");
  const sum = dim.sum != null ? `${dim.sum} ÷ ${dim.known_weight} = ${(dim.raw ?? 0).toFixed(2)}` : null;
  return h("div", { class: "stack" },
    h("p", { class: "muted" }, result.dimensions[key].label, ": ", result.profile.label, " profile, model version ", String(result.model_version)),
    h("div", { class: "table-wrap" }, h("table", { class: "table working" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Factor"), h("th", { scope: "col" }, "Level"),
        h("th", { scope: "col" }, "Weight"), h("th", { scope: "col" }, "Why"))),
      h("tbody", {}, dim.factors.map(factorRow)))),
    h("dl", { class: "dl" },
      h("dt", {}, "Known"), h("dd", {}, `${known.length} of ${dim.factors.filter((f) => f.state !== "not_applicable").length} factors that apply: ${dim.coverage}% of their weight`),
      sum ? [h("dt", {}, "Weighted average"), h("dd", {}, sum)] : null,
      dim.floor ? [h("dt", {}, "Floor"), h("dd", {}, `Raised from ${dim.floor.was.toFixed(1)} to ${dim.floor.level.toFixed(1)}: ${dim.floor.reason}`)] : null,
      h("dt", {}, "Score"), h("dd", { class: "cell-main" }, dim.score == null ? "Unknown" : dim.score.toFixed(1)),
      dim.thin ? [h("dt", {}, "Thin"), h("dd", {}, `Under ${result.thresholds.thin}% is known, so it cannot carry a recommendation.`)] : null),
    result.withheld ? h("p", { class: "subtle" }, "Some values are shown only to people with a role over this application.") : null);
}

/** What would raise confidence, most weight first, with where to go. */
export function missingList(result, ref) {
  if (!result.missing.length) return h("p", { class: "muted" }, "Everything that applies is known.");
  return h("ul", { class: "missing-list" }, result.missing.map((item) => {
    const go = WHERE[item.where];
    return h("li", {},
      h("div", { class: "grow" }, h("span", { class: "cell-main" }, item.label), h("span", { class: "subtle" }, ` · weight ${item.weight}`),
        h("div", { class: "cell-sub" }, item.why)),
      go ? h("a", { class: "btn btn-sm", href: `/applications/${ref}${go[1]}` }, go[0])
        : h("span", { class: "subtle" }, "Edit the application"));
  }));
}

export function recommendationWorking(result, vocab) {
  const rows = [
    ["Data confidence", `${result.confidence}% (at least ${result.thresholds.confidence}% needed)`],
    ["Thresholds", `Value ${result.thresholds.value}, health ${result.thresholds.health}, cost ${result.thresholds.cost}`],
    ["Rule", result.rule ? result.rule.label : "None"],
  ];
  if (result.guardrail) rows.push(["Guardrail", `${result.guardrail.label}: ${label(vocab, "dispositions", result.guardrail.from)} became ${label(vocab, "dispositions", result.guardrail.to)}. ${result.guardrail.reason ?? ""}`]);
  if (result.overlap_with) rows.push(["Overlaps with", `${result.overlap_with.name} (${result.overlap_with.ref}), the primary provider, whose value is ${result.overlap_with.bv?.toFixed(1)}`]);
  return h("dl", { class: "dl" }, rows.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));
}

/** Open the working for one dimension, or for confidence. */
export function openWorking(result, key, { ref, vocab }) {
  openOverlay({
    title: key === "confidence" ? "Data confidence" : result.dimensions[key].label,
    subtitle: key === "confidence" ? "What would raise it, most weight first" : "How the score was worked out",
    render: (body) => {
      body.append(key === "confidence"
        ? h("div", { class: "stack-lg" },
          h("p", {}, `${result.confidence}% of what the scores need is known. Below ${result.thresholds.confidence}%, the recommendation is Assess.`),
          missingList(result, ref))
        : working(result, key));
    },
  });
}

/** The whole picture on the Scores tab. */
export function scoresTab(result, { ref, vocab }) {
  const assessed = result.assessment;
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      DIMENSIONS.map(([key]) => card({ title: `${result.dimensions[key].label}: ${result.dimensions[key].score == null ? "unknown" : result.dimensions[key].score.toFixed(1)}` },
        working(result, key)))),
    h("div", { class: "stack-lg" },
      card({ title: "Recommendation" }, verdict(result, vocab), recommendationWorking(result, vocab)),
      card({ title: "What would raise confidence" }, missingList(result, ref)),
      card({ title: "Answers" }, assessed
        ? h("p", {}, `From ${assessed.ref}, by ${assessed.by} on ${date(assessed.on)}. `,
          assessed.current ? "Current." : h("strong", {}, "Expired: its answers no longer count."))
        : h("p", { class: "muted" }, "Not assessed yet."))));
}

export function confidenceIcon() {
  return icon("quality");
}
