// Admin → Connectors: the tools AppWren can read facts from, each switched on here, one at a
// time, for a named source. A credential stays in the server's environment; only the name of
// its variable is given here. Every run is listed with what it read, changed, and missed.

import { get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { dateTime, plural, relative } from "../core/format.js";
import { banner, field, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

function state(row) {
  if (!row.enabled) return pill("Off");
  if (row.last_status === "failed") return pill("Failed", "danger");
  return row.last_status ? pill("On", "ok") : pill("On, not run yet", "accent");
}

const facts = (rows) => h("dl", { class: "dl" }, rows.filter(Boolean).map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));

function every(hours) {
  if (hours === 24) return "Daily";
  if (hours === 168) return "Weekly";
  return hours % 24 === 0 ? `Every ${hours / 24} days` : `Every ${plural(hours, "hour")}`;
}

function didWhat(item) {
  if (item.status === "failed") return item.error;
  const c = item.counts;
  return `Read ${plural(c.read, "value")}: ${c.changed} changed, ${c.unchanged} the same, ${c.kept} kept by an override. ${c.unmatched} not matched.`;
}

function runs(row) {
  if (!row.runs.length) return null;
  return h("details", {}, h("summary", {}, `Recent runs (${row.runs.length})`),
    h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "When"), h("th", { scope: "col" }, "Result"),
        h("th", { scope: "col" }, "What it did"), h("th", { scope: "col" }, "Not matched"))),
      h("tbody", {}, row.runs.map((item) => h("tr", {},
        h("td", { class: "nowrap" }, dateTime(item.started_at)),
        h("td", {}, item.status === "ok" ? pill("Done", "ok") : pill("Failed, nothing changed", "danger")),
        h("td", {}, didWhat(item)),
        h("td", {}, item.unmatched.length
          ? h("details", {}, h("summary", {}, plural(item.unmatched.length, "item")),
            h("ul", { class: "plain-list" }, item.unmatched.map((miss) => h("li", {}, h("strong", {}, miss.what), `: ${miss.why}`))))
          : h("span", { class: "subtle" }, "None"))))))));
}

function connectorCard(row, kind, reload) {
  const result = h("div", { "aria-live": "polite" });
  const check = button("Check", { kind: "btn-sm btn-ghost", "aria-label": `Check that ${row.name} reaches its source`, onclick: async () => {
    check.disabled = true;
    try {
      const done = (await post(`/api/v1/connectors/${row.key}/check`, {})).data;
      result.replaceChildren(alert("ok", icon("check"), h("div", {}, h("strong", {}, "It answers. "), done.said)));
    } catch (error) {
      const why = Object.values(error.fields ?? {})[0] ?? error.detail ?? error.message;
      result.replaceChildren(alert("danger", icon("alert"), h("div", {}, h("strong", {}, "It could not be reached: "), why)));
    } finally {
      check.disabled = false;
    }
  } });
  const run = button("Run now", { kind: "btn-sm", "aria-label": `Run ${row.name} now`, onclick: async () => {
    run.disabled = true;
    try {
      const done = (await post(`/api/v1/connectors/${row.key}/run`, {})).data;
      toast(done.status === "ok" ? `${row.name}: ${done.summary}.` : `${row.name} failed, and changed nothing: ${done.error}`);
    } catch (error) {
      toast(error.detail ?? "It could not be run.");
    }
    reload();
  } });
  const toggle = button(row.enabled ? "Switch off" : "Switch on", { kind: row.enabled ? "btn-sm btn-ghost" : "btn-sm btn-primary",
    "aria-label": `${row.enabled ? "Switch off" : "Switch on"} ${row.name}`, onclick: async () => {
      await patch(`/api/v1/connectors/${row.key}`, { enabled: !row.enabled });
      toast(row.enabled ? `${row.name} is off. Nothing more is read from it.` : `${row.name} is on. It runs within a quarter of an hour, then ${every(row.every_hours).toLowerCase()}.`);
      reload();
    } });
  const edit = button("Edit", { kind: "btn-sm btn-ghost", "aria-label": `Edit ${row.name}`, onclick: () => connectorForm(kind, row, reload) });
  const settings = (kind?.settings ?? []).map((spec) => [spec.label, row.settings[spec.name] || h("span", { class: "subtle" }, "Not given")]);
  const credential = kind?.credential == null ? ["Credential", "None needed"]
    : ["Credential", h("span", {}, "In ", h("code", {}, row.credential_env), " on the server: ",
      row.credential_set ? h("strong", {}, "set") : h("strong", { class: "text-danger" }, "not set"))];
  return card({ title: h("span", { class: "row-sm wrap" }, row.name, state(row)),
    actions: h("div", { class: "row-sm wrap" }, edit, check, row.enabled ? run : null, toggle) },
  h("div", { class: "stack" },
    h("p", { class: "muted" }, `${kind?.label ?? row.kind}: ${kind?.describes ?? ""}.`),
    row.enabled && !row.credential_set && kind?.credential != null ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, "It cannot run yet. "),
      "Put the credential in ", h("code", {}, row.credential_env), " in the server's environment and restart AppWren.")) : null,
    row.last_status === "failed" ? alert("danger", icon("alert"), h("div", {}, h("strong", {}, "The last run failed and changed nothing. "), row.last_summary)) : null,
    facts([...settings, credential, ["How often", every(row.every_hours)],
      ["Last ran", row.last_run_at ? `${relative(row.last_run_at)}: ${row.last_summary ?? ""}` : "Not yet"],
      ["Next run", row.enabled ? (row.next_run_at ? dateTime(row.next_run_at) : "Soon") : "Off"]]),
    result,
    runs(row)));
}

function connectorForm(kind, row, reload) {
  openOverlay({
    title: row ? `Edit ${row.name}` : `Add: ${kind.label}`,
    subtitle: kind.describes,
    render: (body, footer, close) => {
      const fields = {};
      fields.name = field("Name", { value: row?.name ?? kind.label, hint: "As it is shown beside the values it supplies.", maxlength: 120 });
      if (!row) fields.key = field("Key", { value: kind.key, hint: "A short name for it, in lower-case letters, digits, and dashes. It cannot be changed.", maxlength: 40 });
      const settings = {};
      for (const spec of kind.settings) {
        settings[spec.name] = field(spec.label, { value: row?.settings[spec.name] ?? spec.default, hint: spec.hint || null, required: spec.required });
        fields[`settings.${spec.name}`] = settings[spec.name];
      }
      if (kind.credential != null) {
        fields.credential_env = field("Environment variable for the credential", { value: row?.credential_env ?? kind.credential,
          hint: `The name of the variable on the server that holds it, never the credential itself. It needs: ${kind.access}` });
      }
      fields.every_hours = field("Run every so many hours", { type: "number", value: String(row?.every_hours ?? 24), min: "1", max: "168" });
      const problem = banner();
      const save = button(row ? "Save" : "Add, switched off", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const values = { name: fields.name.input.value, every_hours: Number(fields.every_hours.input.value),
          settings: Object.fromEntries(Object.entries(settings).map(([name, f]) => [name, f.input.value])) };
        if (fields.credential_env) values.credential_env = fields.credential_env.input.value;
        const done = await submit({ button: save, banner: problem, fields,
          run: () => (row ? patch(`/api/v1/connectors/${row.key}`, values)
            : post("/api/v1/connectors", { ...values, kind: kind.key, key: fields.key.input.value })) });
        if (done) {
          close();
          toast(row ? "Saved." : "Added. Check that it reaches its source, then switch it on.");
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        kind.credential == null ? h("p", { class: "muted" }, kind.access)
          : alert("info", icon("info"), h("div", {}, "Give it a credential that can only read, and only what it needs. ", kind.access)),
        Object.values(fields).map((f) => f.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function kindsCard(kinds, reload) {
  return card({ title: "Sources AppWren can read" },
    h("div", { class: "stack" },
      kinds.map((kind) => h("div", { class: "row wrap" },
        h("div", { class: "stack-sm grow" }, h("strong", {}, kind.label), h("span", { class: "muted" }, `${kind.describes}.`),
          h("span", { class: "subtle" }, `Access it needs: ${kind.access}`)),
        button("Add", { kind: "btn-sm", iconName: "plus", "aria-label": `Add a connector: ${kind.label}`, onclick: () => connectorForm(kind, null, reload) })))));
}

export function adminConnectors(main) {
  return show(main, {
    title: "Connectors",
    load: async () => (await get("/api/v1/connectors", null, { fresh: true })).data,
    view: (data, reload) => {
      const kinds = Object.fromEntries(data.kinds.map((kind) => [kind.key, kind]));
      const on = data.connectors.filter((row) => row.enabled);
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Connectors",
          lede: "Facts that other tools already know, read by themselves and marked with where they came from. A connector only reads, and a person's override always wins." }),
        on.length ? null : alert("info", icon("info"), h("div", {}, h("strong", {}, "AppWren makes no connection to anything until a connector here is switched on. "),
          "Each is added switched off, for one named source, and can be checked before it runs.")),
        data.connectors.length ? data.connectors.map((row) => connectorCard(row, kinds[row.kind], reload))
          : emptyState({ iconName: "link", title: "No connectors yet", text: "Add one below for each source you want facts from." }),
        kindsCard(data.kinds, reload));
    },
  });
}
