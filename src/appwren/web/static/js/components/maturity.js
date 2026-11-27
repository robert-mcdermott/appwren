// Engineering maturity: a component's level and its checks, and an application's level as
// its least mature component's, with what each needs for the next level.

import { h } from "../core/dom.js";
import { card, pill } from "./ui.js";

const TONE = { gold: "ok", silver: "accent", bronze: "warn", none: "danger" };
const MARK = { met: "Met", not_met: "Not met", unknown: "Not known", not_applicable: "Does not apply" };

export function levelPill(item) {
  return item?.level ? pill(item.label, TONE[item.level] ?? "") : pill("Not measured");
}

function checks(component) {
  return h("ul", { class: "check-list" }, component.checks.map((check) => h("li", { "data-state": check.state },
    h("span", { class: "check-state" }, MARK[check.state]),
    h("span", {}, check.label, h("span", { class: "cell-sub" }, ` · ${check.why}`)))));
}

function next(component) {
  if (!component.next) return h("p", { class: "subtle" }, "At the highest level.");
  const missing = component.next.missing.map((check) => check.label.toLowerCase());
  return h("p", { class: "subtle" }, `For ${component.next.label.toLowerCase()}: ${missing.join(", ")}.`);
}

/** On a component's page. */
export function componentMaturity(found) {
  const mine = found?.component;
  if (!mine) return null;
  return card({ title: "Engineering maturity", actions: levelPill(mine) },
    h("div", { class: "stack-sm" }, checks(mine), next(mine),
      h("p", { class: "subtle" }, `Its application is at ${found.application.label.toLowerCase()}, the level of its least mature component.`)));
}

/** On an application's Components part. */
export function applicationMaturity(found) {
  if (!found?.components?.length) return null;
  return card({ title: "Engineering maturity", actions: levelPill(found) },
    h("div", { class: "stack" },
      h("p", { class: "muted" }, "Each component's practice, from its record and its repository. The application is at the level of its least mature component."),
      found.components.map((component) => h("details", {},
        h("summary", {}, h("span", { class: "row-sm wrap" }, component.name, levelPill(component))),
        h("div", { class: "stack-sm" }, checks(component), next(component))))));
}
