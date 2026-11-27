// Home: what you owe, and, for administrators of a new installation, how to set it up.

import { get } from "../core/api.js";
import { h, icon } from "../core/dom.js";
import { greeting, titleCase } from "../core/format.js";
import { can, session } from "../core/session.js";
import { label, vocabularies } from "../core/lookups.js";
import { avatar, card, dispositionBadge, emptyState, flag, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

function setup(data, meta) {
  const steps = [
    { done: data.units.length > 0, title: "Describe your organization",
      text: "Add your divisions, departments, and labs, or import them from a spreadsheet.",
      href: "/admin/units", action: "Units" },
    { done: data.accounts.length > 1, title: "Add the people who will run the portfolio",
      text: "Give manager, architect, auditor, leader, and steward roles to the right people.",
      href: "/admin/people", action: "People" },
    { done: Boolean(meta.branding.organization_name || meta.branding.logo_light || meta.branding.accent),
      title: "Make it yours", text: "Set your organization's name, logo, and colors.",
      href: "/admin/appearance", action: "Appearance" },
  ];
  const left = steps.filter((step) => !step.done).length;
  return card({ title: left ? "Set up your installation" : "Your installation is set up", flush: true,
    actions: pill(left ? `${steps.length - left} of ${steps.length} done` : "All done", left ? "info" : "ok") },
  h("ul", { class: "checklist" }, steps.map((step) => h("li", { "data-done": String(step.done) },
    h("span", { class: "check-mark" }, icon("check", "icon icon-sm")),
    h("div", { class: "grow" }, h("div", { class: "cell-main" }, step.title), h("div", { class: "cell-sub" }, step.text)),
    h("a", { class: "btn btn-sm", href: step.href }, step.action)))));
}

const ICONS = { assess: "assess", flag: "flag", complete: "edit", orphan: "people" };

function owedList(items) {
  if (!items.length) {
    return emptyState({ iconName: "check", title: "Nothing needs your attention",
      text: "Assessments, missing details, and flags on the applications you are named on will be listed here, most urgent first." });
  }
  return h("ul", { class: "owed" }, items.map((item) => h("li", {},
    h("a", { class: "owed-item", href: item.href },
      h("span", { class: "owed-icon", "data-kind": item.severity === "danger" ? "decide" : item.kind }, icon(ICONS[item.kind] ?? "info")),
      h("span", { class: "grow" }, h("span", { class: "cell-main" }, item.application.name),
        h("span", { class: "owed-detail cell-sub" }, item.text)),
      flag(item.severity, item.severity === "danger" ? "Urgent" : item.severity === "warning" ? "Soon" : "When you can")))));
}

function waitingList(data, vocab) {
  if (!data.waiting.length) return null;
  return card({ title: `Waiting for a decision (${data.waiting_total})`, flush: true,
    actions: h("a", { class: "btn btn-sm", href: "/decisions?show=mismatch" }, "Decisions") },
  h("ul", { class: "owed" }, data.waiting.slice(0, 12).map((item) => h("li", {},
    h("a", { class: "owed-item", href: `/applications/${item.ref}?tab=decisions` },
      h("span", { class: "grow" }, h("span", { class: "cell-main" }, item.name), h("span", { class: "owed-detail cell-sub" }, item.why)),
      item.recommendation ? dispositionBadge(item.recommendation, label(vocab, "dispositions", item.recommendation)) : null)))));
}

export function home(main, meta) {
  const me = session();
  return show(main, {
    title: "Home",
    load: async () => {
      const [owed, vocab, setupData] = await Promise.all([get("/api/v1/home", null, { fresh: true }), vocabularies(),
        can("admin") ? Promise.all([get("/api/v1/units"), get("/api/v1/accounts")]).then(([units, accounts]) => ({ units: units.data.units, accounts: accounts.data })) : null]);
      return { owed: owed.data, vocab, setup: setupData };
    },
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ title: `${greeting()}, ${me.account.name.split(" ")[0]}`,
        lede: meta.branding.organization_name ? `The application portfolio at ${meta.branding.organization_name}.` : null }),
      data.setup ? setup(data.setup, meta) : null,
      h("div", { class: "split" },
        h("div", { class: "stack-lg" },
          card({ title: "Waiting on you", flush: data.owed.items.length > 0 }, owedList(data.owed.items)),
          waitingList(data.owed, data.vocab)),
        h("div", { class: "stack-lg" },
          card({ title: "Your access" },
            h("div", { class: "stack" },
              h("div", { class: "row" }, avatar(me.account.name, true), h("div", {},
                h("div", { class: "cell-main" }, me.account.name), h("div", { class: "cell-sub" }, me.account.email))),
              h("div", { class: "row-sm wrap" }, me.roles.map((role) => pill(titleCase(role), role === "member" ? "" : "accent"))),
              h("p", { class: "muted" }, `You are named on ${data.owed.named} application${data.owed.named === 1 ? "" : "s"}.`),
              h("div", { class: "row-sm wrap" }, h("a", { href: "/applications?mine=true" }, "Your applications"), h("a", { href: "/account" }, "Your account"))))))),
  });
}
