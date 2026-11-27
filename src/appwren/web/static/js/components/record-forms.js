// The forms that add and edit inventory records. One form, shaped by the fields the server
// describes for each kind of record, and by the organization's own fields for applications.

import { get, patch, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { catalog, options, unitOptions, units as loadUnits, vocabularies } from "../core/lookups.js";
import { navigate } from "../core/router.js";
import { can, session } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { peoplePicker } from "./people-picker.js";
import { statusLabel, TYPES } from "./record.js";
import { toast } from "./toast.js";

export const SECTIONS = {
  about: "What it is",
  source: "Where it comes from",
  use: "Who uses it",
  support: "Who supports it",
  security: "Security and data",
  operations: "How it is run",
  cost: "Cost and funding",
  research: "Research",
  lifecycle: "Its life",
};

export function section(title, ...children) {
  return h("div", { class: "form-section stack" }, h("h3", {}, title), children);
}

/** The units a person may add applications to: those they keep, or all of them. */
export function ownUnits() {
  const me = session();
  const scopes = [me.units?.steward, me.units?.manager, me.units?.architect].filter((scope) => scope !== undefined);
  if (scopes.some((scope) => scope === null)) return null;
  return new Set(scopes.flat());
}

const YES_NO = [["", "Not said"], ["true", "Yes"], ["false", "No"]];

async function refOptions(target, scope = {}) {
  const type = TYPES[target];
  const page = await get(`/api/v1/${type.path}`, { sort: "name", limit: 200, ...scope });
  return page.data.map((row) => [row.ref, `${row.name} (${row.ref})`]);
}

/** One input for one field, with a way to read its value back. */
function input(spec, value, ctx) {
  const hint = spec.help ?? null;
  switch (spec.kind) {
    case "long": {
      const f = field(spec.label, { type: "textarea", value: value ?? "", hint });
      return { node: f.node, field: f, read: () => f.input.value };
    }
    case "choice": {
      const f = select(spec.label, options(ctx.vocab, spec.vocab, { blank: spec.required ? null : "Not said" }),
        { value: value ?? spec.default ?? "", hint });
      return { node: f.node, field: f, read: () => f.input.value || null };
    }
    case "many": {
      if (!spec.vocab) {
        const f = field(spec.label, { value: (value ?? []).join(", "), hint });
        return { node: f.node, field: f, read: () => f.input.value.split(",").map((s) => s.trim()).filter(Boolean) };
      }
      const chosen = new Set(value ?? []);
      const boxes = (ctx.vocab[spec.vocab] ?? []).filter((item) => !item.retired || chosen.has(item.key))
        .map((item) => ({ key: item.key, box: checkbox(item.label, { checked: chosen.has(item.key), hint: item.description }) }));
      const node = h("fieldset", { class: "stack-sm" }, h("legend", {}, spec.label), hint ? h("p", { class: "hint subtle" }, hint) : null,
        boxes.map((b) => b.box.node));
      return { node, field: null, read: () => boxes.filter((b) => b.box.input.checked).map((b) => b.key) };
    }
    case "int": {
      const f = field(spec.label, { type: "number", min: 0, step: 1, value: value ?? "", hint });
      return { node: f.node, field: f, read: () => (f.input.value === "" ? null : Number(f.input.value)) };
    }
    case "date": {
      const f = field(spec.label, { type: "date", value: value ?? "", hint });
      return { node: f.node, field: f, read: () => f.input.value || null };
    }
    case "bool": {
      const f = select(spec.label, YES_NO, { value: value == null ? "" : String(value), hint });
      return { node: f.node, field: f, read: () => (f.input.value === "" ? null : f.input.value === "true") };
    }
    case "url": {
      const f = field(spec.label, { type: "url", value: value ?? "", placeholder: "https://", hint });
      return { node: f.node, field: f, read: () => f.input.value };
    }
    case "unit": {
      const f = select(spec.label, unitOptions(ctx.units.tree, { blank: "Not said" }), { value: value ?? "", hint });
      return { node: f.node, field: f, read: () => (f.input.value ? Number(f.input.value) : null) };
    }
    case "ref": {
      const f = select(spec.label, [["", spec.required ? "Choose…" : "None"], ...(ctx.refs[spec.target] ?? [])],
        { value: ctx.refValue(spec, value) ?? "", hint });
      return { node: f.node, field: f, read: () => f.input.value || null };
    }
    case "person": {
      let chosen = ctx.person(spec);
      const said = h("div", { class: "row-sm" });
      const draw = () => said.replaceChildren(...(chosen
        ? [h("span", { class: "cell-main" }, chosen.name), button("Clear", { kind: "btn-ghost btn-sm", onclick: () => {
          chosen = null;
          draw();
        } })]
        : [h("span", { class: "subtle" }, "Nobody named")]));
      draw();
      const picker = peoplePicker({ label: "Find a person", onPick: (account) => {
        chosen = { id: account.id, name: account.display_name };
        draw();
      } });
      const node = h("fieldset", { class: "stack-sm" }, h("legend", {}, spec.label), hint ? h("p", { class: "hint subtle" }, hint) : null, said, picker);
      return { node, field: null, read: () => chosen?.id ?? null };
    }
    default: {
      const f = field(spec.label, { value: value ?? "", hint });
      return { node: f.node, field: f, read: () => f.input.value };
    }
  }
}

/** One of the organization's own fields. */
function ownInput(spec, value) {
  const hint = spec.help ?? null;
  if (spec.type === "choice") {
    const f = select(spec.label, [["", "Not said"], ...spec.options], { value: value ?? "", hint });
    return { node: f.node, read: () => f.input.value || null };
  }
  if (spec.type === "bool") {
    const f = select(spec.label, YES_NO, { value: value == null ? "" : String(value), hint });
    return { node: f.node, read: () => (f.input.value === "" ? null : f.input.value === "true") };
  }
  const type = { long: "textarea", number: "number", date: "date", url: "url" }[spec.type] ?? "text";
  const f = field(spec.label, { type, value: value ?? "", hint });
  return { node: f.node, read: () => (spec.type === "number" && f.input.value !== "" ? Number(f.input.value) : f.input.value || null) };
}

/**
 * Add a record of this type, or edit the one given. ``preset`` fills fields of a new record
 * (a component's application). ``only`` limits the form to some sections, for a short edit.
 */
export async function editRecord(type, { record = null, preset = {}, only = null, onDone } = {}) {
  const meta = TYPES[type];
  const [program, vocab, unitIndex] = await Promise.all([catalog(), vocabularies(), loadUnits()]);
  const spec = program.types[type];
  const targets = [...new Set(spec.fields.filter((f) => f.kind === "ref").map((f) => f.target))];
  // A deployment's component is one of its own application's.
  const within = type === "deployment" ? (record?.application?.ref ?? preset.application_id ?? null) : null;
  const scopeOf = (target) => (target === "component" && within ? { application: within } : target === "hosting_platform" ? { status: "active" } : {});
  const refs = Object.fromEntries(await Promise.all(targets.map(async (target) => [target, await refOptions(target, scopeOf(target))])));
  // A record's links to others arrive as chips; the form works in references.
  const refValue = (f, value) => {
    if (value == null) return null;
    const chip = record?.[f.name.replace(/_id$/, "")];
    if (chip && typeof chip === "object" && chip.ref) return chip.ref;
    const listed = (refs[f.target] ?? []).find(([ref]) => ref === value);
    return listed ? listed[0] : (record?.[`${f.name}_ref`] ?? null);
  };
  // A person arrives as { id, name } beside the field that holds their id.
  const person = (f) => record?.[f.name.replace(/_id$/, "")] ?? null;
  const ctx = { vocab, units: unitIndex, refs, refValue, person };
  openOverlay({
    title: record ? `Edit ${meta.noun}` : `Add ${meta.article}`,
    subtitle: record ? `${record.ref} · ${record.name}` : meta.lede,
    render: (body, footer, close) => {
      const withheld = new Set(record?.withheld ?? []);
      const named = type === "deployment"; // named for what runs and where, unless someone names it
      const name = field("Name", { value: record?.name ?? "", required: !named, hint: named && !record ? "Leave empty to name it for what runs and where." : null });
      const summary = field("Summary", { type: "textarea", rows: 3, value: record?.summary ?? "" });
      const header = [name.node, summary.node];
      const fields = { name, summary };
      const readers = { name: () => name.input.value, summary: () => summary.input.value };
      let unit = null;
      if (spec.has_unit) {
        unit = select("Unit", unitOptions(unitIndex.tree, { only: ownUnits(), blank: record ? null : "Choose…" }),
          { value: record?.org_unit_id ?? "", required: true, hint: "The unit that answers for it." });
        header.push(unit.node);
        fields.org_unit_id = unit;
        readers.org_unit_id = () => (unit.input.value ? Number(unit.input.value) : null);
      }
      const bySection = {};
      for (const f of spec.fields) {
        if (withheld.has(f.name)) continue;
        if (record && f.name === "application_id") continue; // a component or deployment stays with its application
        const value = record ? record[f.name] : preset[f.name];
        const made = input(f.name === "annual_cost" && record?.has_cost_lines
          ? { ...f, help: "The sum of its cost lines. Change them on its Cost part." } : f, value, ctx);
        if (f.name === "annual_cost" && record?.has_cost_lines && made.field) made.field.input.disabled = true;
        // What the form was opened for (a component's application, an interface's near end) is fixed.
        if (!record && f.name in preset && made.field) made.field.input.disabled = true;
        if (made.field) fields[f.name] = made.field;
        readers[f.name] = made.read;
        (bySection[f.section] ??= []).push(made.node);
      }
      const own = type === "application"
        ? (program.fields ?? []).filter((f) => !f.applies_to || !record || f.applies_to.includes(record.sourcing))
          .map((f) => ({ key: f.key, ...ownInput(f, record?.fields?.[f.key]) }))
        : [];
      const restricted = spec.has_unit ? checkbox("Restricted", { checked: record?.restricted ?? false,
        hint: "Known only to the people named on it and those with a role over its unit." }) : null;
      const status = record && type !== "application"
        ? select("Status", [["active", statusLabel("active")], ["retired", statusLabel("retired")]], { value: record.status })
        : null;
      const values = () => {
        const out = Object.fromEntries(Object.entries(readers).map(([key, read]) => [key, read()]));
        if (own.length) out.fields = Object.fromEntries(own.map((f) => [f.key, f.read()]));
        if (restricted) out.restricted = restricted.input.checked;
        if (status) out.status = status.input.value;
        if (!record) for (const [key, value] of Object.entries(preset)) out[key] = value;
        return out;
      };
      const problem = banner();
      const saveButton = button(record ? "Save" : "Add", { kind: "btn-primary" });
      const path = `/api/v1/${meta.path}`;
      const save = async () => {
        const done = await submit({ button: saveButton, fields, banner: problem,
          run: () => (record ? patch(`${path}/${record.ref}`, { version: record.version, ...values() }) : post(path, values())) });
        if (!done) return;
        close();
        if (record) {
          toast("Saved.");
          onDone?.(done.data);
        } else {
          toast(`${done.data.ref} was added.`);
          if (onDone) onDone(done.data);
          else navigate(`/${meta.path}/${done.data.ref}`);
        }
      };
      const wanted = (key) => !only || only.includes(key);
      const definition = type === "application" && !record && program.definition
        ? h("details", { class: "disclosure" }, h("summary", {}, "What counts as an application?"),
          h("div", { class: "prose stack-sm" }, h("p", {}, program.definition.text),
            h("p", { class: "cell-sub" }, "For example: ", program.definition.examples.join("; "), "."),
            h("p", { class: "cell-sub" }, "Not: ", program.definition.not_examples.join("; "), ".")))
        : null;
      const form = h("form", { class: "stack-lg", novalidate: true, onsubmit: (event) => {
        event.preventDefault();
        save();
      } }, problem, definition,
      wanted("about") ? section(SECTIONS.about, header, bySection.about ?? []) : null,
      Object.entries(SECTIONS).filter(([key]) => key !== "about" && wanted(key) && bySection[key]?.length)
        .map(([key, title]) => section(title, bySection[key])),
      own.length && wanted("own") ? section("The organization's own fields", own.map((f) => f.node)) : null,
      (restricted || status) && wanted("about") ? section("Who may see it", restricted?.node ?? null, status?.node ?? null) : null,
      withheld.size ? h("p", { class: "subtle" }, "Some fields are only shown to people with a role over this application.") : null);
      saveButton.addEventListener("click", save);
      body.append(form);
      footer.replaceChildren(h("div", { class: "row" }, saveButton, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function mayAdd(type) {
  if (type === "application" || type === "contract") return can("steward") || can("architect");
  if (["component", "interface", "deployment"].includes(type)) return true; // the server asks who keeps the application
  return can("architect");
}
