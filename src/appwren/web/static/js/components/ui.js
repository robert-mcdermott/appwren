// Small pieces used on every page.

import { button, h, icon } from "../core/dom.js";
import { initials, titleCase } from "../core/format.js";

export function pageHeader({ eyebrow = null, title, lede = null, actions = null }) {
  return h("header", { class: "page-header" },
    h("div", { class: "grow" },
      eyebrow ? h("div", { class: "eyebrow" }, eyebrow) : null,
      h("h1", { tabindex: "-1" }, title),
      lede ? h("p", { class: "lede" }, lede) : null),
    actions ? h("div", { class: "row wrap" }, actions) : null);
}

export function card({ title = null, actions = null, footer = null, flush = false }, ...children) {
  return h("section", { class: "card" },
    title ? h("div", { class: "card-header" }, h("h2", { class: "grow" }, title), actions) : null,
    h("div", { class: flush ? "" : "card-body" }, children),
    footer ? h("div", { class: "card-footer" }, footer) : null);
}

export function emptyState({ iconName = "info", title, text = null, action = null }) {
  return h("div", { class: "empty" },
    icon(iconName, "empty-icon"), h("h2", {}, title), text ? h("p", {}, text) : null, action);
}

export function errorState(error, retry) {
  return emptyState({
    iconName: "alert",
    title: error?.status === 403 ? "You do not have access to this" : "Something went wrong",
    text: error?.detail || error?.message || "The page could not be loaded.",
    action: retry && error?.status !== 403 ? button("Try again", { onclick: retry }) : null,
  });
}

export function skeletonPage() {
  return h("div", { "aria-busy": "true", "aria-label": "Loading" },
    h("div", { class: "skeleton skeleton-title" }),
    h("div", { class: "skeleton skeleton-line" }),
    h("div", { class: "skeleton skeleton-line" }),
    h("div", { class: "skeleton skeleton-block" }));
}

export function avatar(name, large = false) {
  return h("span", { class: `avatar${large ? " avatar-lg" : ""}`, "aria-hidden": "true" }, initials(name));
}

const TONES = { active: "ok", invited: "info", disabled: "", closed: "" };

/** A word in a pill, colored by what it means. tone: ok, warn, danger, info, accent, or none. */
export function pill(text, tone = "") {
  return h("span", { class: `pill${tone ? ` pill-${tone}` : ""}` }, text);
}

export function statusPill(status) {
  return pill(titleCase(status), TONES[status] ?? "");
}

/** Where step `position` of `count` sits on the five-step ramp: the ends stay at the ends. */
export function rampLevel(position, count) {
  if (!position) return 0;
  return count <= 1 ? 5 : Math.round(1 + ((position - 1) * 4) / (count - 1));
}

/** A score: its own hue, a bar glyph, and its figure. Never the signal colors. Level 0 is "unknown". */
export function scoreBadge(level, name) {
  return h("span", { class: "score", "data-level": level },
    h("span", { class: "score-bars", "aria-hidden": "true" }, h("i"), h("i"), h("i"), h("i"), h("i")),
    name ?? "Unknown");
}

/** A score figure: the value to one decimal, a short bar, and how much of it was known. */
export function scoreFigure(value, { coverage = 100, label = null } = {}) {
  const level = value == null ? 0 : Math.min(5, Math.max(1, Math.round(value)));
  const thin = coverage < 50;
  const fill = h("span", { class: "score-fill" });
  fill.style.width = `${value == null ? 0 : Math.round((value / 5) * 100)}%`;
  return h("span", { class: "score-figure", "data-level": level, "data-thin": String(thin) },
    h("span", { class: "score-value", "aria-hidden": label ? "true" : null }, value == null ? "—" : Number(value).toFixed(1)),
    h("span", { class: "score-track", "aria-hidden": "true" }, fill),
    label ? h("span", { class: "sr-only" }, `${label}: ${value == null ? "unknown" : `${Number(value).toFixed(1)} of 5`}`) : null,
    coverage < 100 ? h("span", { class: "score-coverage" }, `${coverage}% known`) : null);
}

/** A disposition: its own hue, its icon, and its name. A recommendation is outlined; a decision is filled. */
export function dispositionBadge(key, labelText, { decided = false } = {}) {
  return h("span", { class: "disp", "data-disp": key, "data-kind": decided ? "decided" : "recommended" },
    icon(key, "icon icon-sm"), labelText ?? titleCase(key));
}

const FLAG_ICONS = { danger: "alert", warning: "flag", info: "info" };

/** A flag: something that needs attention whatever the disposition. Always an icon and a sentence. */
export function flag(severity, text) {
  const tone = severity === "warning" ? "warn" : severity;
  return h("span", { class: `flag flag-${tone}` }, icon(FLAG_ICONS[severity] ?? "info", "icon icon-sm"), text);
}

export function stat(value, label) {
  return h("div", { class: "card stat" }, h("div", { class: "stat-value" }, value), h("div", { class: "stat-label" }, label));
}

export function alert(tone, ...children) {
  return h("div", { class: `alert alert-${tone}` }, children);
}
