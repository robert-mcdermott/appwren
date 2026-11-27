// A scenario on its record page: what it would change, what that would do, and turning it
// into an initiative. Loaded only on a scenario's page.

import { post, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { banner, submit } from "./form.js";
import { confirmAction, openOverlay } from "./overlay.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
import { alert, card, stat } from "./ui.js";
import { recordFinder } from "../pages/record.js";

const ACTIONS = [["retire", "Retire it"], ["consolidate", "Consolidate it into"], ["replace", "Replace it with"]];

function table(headings, rows) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, headings.map((text) => h("th", { scope: "col" }, text)))),
    h("tbody", {}, rows.map((cells) => h("tr", {}, cells.map((cell) => h("td", {}, cell)))))));
}

function editChanges(record, reload) {
  const rows = record.changes.map((c) => ({ ref: c.ref, name: c.name, action: c.action, into: c.into?.ref ?? "", note: c.note ?? "" }));
  openOverlay({
    title: "What it would change",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip({ ...row, type: "application" }, { link: false })),
          h("select", { class: "select", "aria-label": `What happens to ${row.name}`, onchange: (event) => {
            row.action = event.target.value;
            draw();
          } }, ACTIONS.map(([key, text]) => h("option", { value: key, selected: key === row.action }, text))),
          row.action === "retire" ? null : h("input", { class: "input", value: row.into, placeholder: "APP-…", "aria-label": `The application ${row.name} ${row.action === "replace" ? "is replaced by" : "moves into"}`,
            oninput: (event) => { row.into = event.target.value.trim(); } }),
          h("input", { class: "input", value: row.note, placeholder: "A note", "aria-label": `A note on ${row.name}`, oninput: (event) => { row.note = event.target.value; } }),
          button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "None yet.")]));
      };
      draw();
      const finder = recordFinder("application", { exclude: (r) => rows.some((row) => row.ref === r.ref), onPick: (r) => {
        rows.push({ ref: r.ref, name: r.name, action: "retire", into: "", note: "" });
        draw();
        finder.refresh();
      } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/scenarios/${record.ref}/changes`, { changes: rows.map((row) => ({ application: row.ref, action: row.action,
            into: row.action === "retire" ? null : row.into || null, note: row.note || null })) }) });
        if (done) {
          close();
          toast("Saved. Nothing else has changed.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "Say what would happen to each: retired, consolidated into another application, or replaced by another. Saving changes no application."),
        list, h("div", { class: "field" }, h("div", { class: "label" }, "Add an application"), finder.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function makeInitiative(record) {
  confirmAction({
    title: "Make an initiative of it",
    text: `A proposed initiative named “${record.name}” is added, retiring the applications this scenario takes away and moving their work onto those that take their place. The scenario then changes no more.`,
    confirmLabel: "Make the initiative",
    run: async () => {
      const made = (await post(`/api/v1/scenarios/${record.ref}/initiative`, {})).data;
      toast(`${made.ref} is proposed.`);
      navigate(`/initiatives/${made.ref}`);
    },
  });
}

/** What the scenario would change, and what that would do. */
export function scenarioPanel(record, ctx) {
  const changes = record.changes;
  const effect = record.effect;
  const money = effect.cost_withheld && !effect.cost_saved ? "Not shown" : Number(effect.cost_saved).toLocaleString();
  const risk = effect.risk;
  return [
    record.initiative ? alert("info", h("p", {}, "It has become the initiative ", recordChip(record.initiative), ", and changes no more.")) : null,
    card({ title: "What it would do" },
      h("div", { class: "stack" },
        h("p", { class: "muted" }, "Worked out from the records as they are now, each time this page is opened. Nothing has changed."),
        h("div", { class: "grid-2" }, stat(money, "Saved a year, before what takes their place"),
          stat(String(effect.people), "People whose application would change"),
          stat(String(effect.interfaces.length), "Interfaces that would stop"),
          stat(String(effect.capabilities.length), "Capabilities left with nothing")),
        effect.cost_withheld ? h("p", { class: "subtle" }, `What ${plural(effect.cost_withheld, "application")} cost is not shown to you, and is left out.`) : null,
        effect.hidden ? h("p", { class: "subtle" }, `${plural(effect.hidden, "application")} it names ${effect.hidden === 1 ? "is" : "are"} not shown to you.`) : null)),
    card({ title: changes.length ? `Would change ${plural(changes.length, "application")}` : "What it would change",
      actions: record.may_keep ? h("div", { class: "row-sm" }, button("Edit the changes", { kind: "btn-sm", onclick: () => editChanges(record, ctx.reload) }),
        changes.length ? button("Make an initiative of it", { kind: "btn-sm", onclick: () => makeInitiative(record) }) : null) : null,
      flush: changes.length > 0 },
    changes.length ? table(["Application", "What would happen", "Note"], changes.map((c) => [
      [recordChip(c), h("div", { class: "cell-sub" }, label(ctx.vocab, "lifecycle", c.lifecycle))],
      c.into ? [c.action_label, " ", recordChip(c.into)] : c.action_label, c.note ?? ""]))
      : h("p", { class: "muted" }, "Nothing yet. Name the applications it would retire, consolidate, or replace.")),
    effect.interfaces.length ? card({ title: "Interfaces that would stop", flush: true },
      table(["Interface", "From what goes", "To what stays"], effect.interfaces.map((i) => [recordChip(i), recordChip(i.leaving), i.staying ? recordChip(i.staying) : "—"]))) : null,
    effect.capabilities.length ? card({ title: "Capabilities left with nothing", flush: true },
      table(["Capability", "Served now only by"], effect.capabilities.map((c) => [recordChip(c), c.served_by.map((a, index) => [index ? ", " : "", recordChip(a)])]))) : null,
    risk.applications.length ? card({ title: "The risk that would go with them", flush: true },
      table(["Application", "Risk exposure", "Flags"], risk.applications.map((a) => [recordChip(a),
        a.risk_exposure == null ? "Not known" : a.risk_exposure.toFixed(1), a.flags.length ? a.flags.join("; ") : h("span", { class: "subtle" }, "None")])),
      risk.flags.length ? h("p", { class: "card-note" }, "Flags cleared: ", risk.flags.map((f) => `${f.text} (${f.count})`).join("; "), ".") : null) : null,
  ];
}
