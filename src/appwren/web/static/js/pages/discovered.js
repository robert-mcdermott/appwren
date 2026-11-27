// Not on record: applications people sign in to, registered with the identity provider, that
// match no record. Whoever adds applications adds each one the portfolio should keep (its name
// filled in) or dismisses it with a reason. A connector never makes a record by itself.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { unitOptions, units } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { banner, field, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

function addForm(item, unitIndex) {
  openOverlay({
    title: `Add ${item.name}`,
    subtitle: `Registered with ${item.source}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const fields = {
        name: field("Name", { value: item.name, maxlength: 200, hint: "As the portfolio should know it. The provider's identifier, not its name, is what matches it from now on." }),
        org_unit_id: select("Unit", unitOptions(unitIndex.tree, { blank: "Choose the unit that answers for it" }),
          { hint: "You can add it to a unit you look after." }),
      };
      const problem = banner();
      const save = button("Add the application", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields,
          run: () => post(`/api/v1/discovered/${item.id}/add`, { name: fields.name.input.value, org_unit_id: Number(fields.org_unit_id.input.value) || null }) });
        if (done) {
          close();
          toast(`Added as ${done.data.ref}. Fill in the rest of its record when you can.`);
          navigate(`/applications/${done.data.ref}`);
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, "Its identifier at the provider is kept on the record, so the next run gives it its users."),
        fields.name.node, fields.org_unit_id.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function dismissForm(item, reload) {
  openOverlay({
    title: `Dismiss ${item.name}?`,
    subtitle: `Registered with ${item.source}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const reason = field("Why it is not kept on record", { type: "textarea", rows: 3, maxlength: 300,
        hint: "Such as: a test registration, or part of an application already on record." });
      const problem = banner();
      const save = button("Dismiss", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { reason },
          run: () => post(`/api/v1/discovered/${item.id}/dismiss`, { reason: reason.input.value }) });
        if (done) {
          close();
          toast(`${item.name} is dismissed. It can be listed again from Dismissed.`);
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, reason.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function rows(items, view, unitIndex, reload) {
  const head = { new: ["Application", "Registered with", "First seen", ""], dismissed: ["Application", "Why", "Dismissed by", ""],
    added: ["Application", "Registered with", "Added as", ""] }[view];
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, head.map((text) => h("th", { scope: "col" }, text || h("span", { class: "sr-only" }, "Actions"))))),
    h("tbody", {}, items.map((item) => h("tr", {},
      h("td", { class: "cell-main" }, item.name, h("div", { class: "cell-sub" }, item.external_id)),
      view === "dismissed" ? [h("td", {}, item.reason), h("td", {}, item.decided_by, h("div", { class: "cell-sub" }, date(item.decided_at)))]
        : view === "added" ? [h("td", {}, item.source), h("td", {}, item.record_ref ? h("a", { href: `/applications/${item.record_ref}` }, item.record_ref) : "—",
          h("div", { class: "cell-sub" }, item.decided_by ? `by ${item.decided_by}` : "recorded by hand, then matched"))]
          : [h("td", {}, item.source), h("td", { class: "nowrap" }, date(item.first_seen_at))],
      h("td", { class: "cell-actions" }, view === "new" ? h("div", { class: "row-sm" },
        button("Add", { kind: "btn-sm", "aria-label": `Add ${item.name}`, onclick: () => addForm(item, unitIndex) }),
        button("Dismiss", { kind: "btn-sm btn-ghost", "aria-label": `Dismiss ${item.name}`, onclick: () => dismissForm(item, reload) }))
        : view === "dismissed" ? button("List again", { kind: "btn-sm btn-ghost", "aria-label": `List ${item.name} again`, onclick: async () => {
          await post(`/api/v1/discovered/${item.id}/restore`, {});
          toast(`${item.name} is listed again.`);
          reload();
        } }) : null))))));
}

export function discoveredList(main) {
  const wanted = query().get("show");
  const view = ["dismissed", "added"].includes(wanted) ? wanted : "new";
  return show(main, {
    title: "Not on record",
    load: async () => {
      const [found, unitIndex] = await Promise.all([get("/api/v1/discovered", { show: view }, { fresh: true }), units()]);
      return { ...found.data, units: unitIndex };
    },
    view: (data, reload) => {
      const tabs = [["new", `Waiting (${data.counts.new})`], ["dismissed", `Dismissed (${data.counts.dismissed})`], ["added", `Added (${data.counts.added})`]];
      const empty = { new: ["Nothing waiting", "Every application registered with the identity provider is on record, or has been dismissed. A connector an administrator switches on lists any new one here."],
        dismissed: ["Nothing dismissed", "An application dismissed from the list, with the reason, is kept here."],
        added: ["Nothing added from here yet", "An application added from the list, or recorded by hand and then matched, is kept here."] }[view];
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Portfolio", title: "Not on record",
          lede: "Applications people sign in to, registered with the identity provider, that match no record by its identifier there or by name. Add each one the portfolio should keep, or dismiss it." }),
        h("div", { class: "tabs", role: "tablist" }, tabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab",
          "aria-selected": String(view === key), onclick: () => setQuery({ show: key === "new" ? null : key }, { replace: false }) }, text))),
        data.items.length ? card({ title: plural(data.items.length, "application"), flush: true }, rows(data.items, view, data.units, reload))
          : emptyState({ iconName: "search", title: empty[0], text: empty[1] }));
    },
  });
}
