// Values that came from other systems: each with its source and when it was read, and a
// person's override with their reason, which wins until they remove it.

import { del, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, relative } from "../core/format.js";
import { banner, checkbox, field, submit } from "./form.js";
import { confirmAction, openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { card, pill } from "./ui.js";

function words(item, value) {
  if (value == null || value === "") return "";
  if (item.kind === "date") return date(value);
  if (item.kind === "yes") return value ? "Yes" : "No";
  if (item.kind === "words") return value.join(", ");
  if (item.kind === "counts") return Object.entries(value).filter(([, count]) => count).map(([key, count]) => `${count} ${key}`).join(", ");
  if (item.kind === "count") return Number(value).toLocaleString();
  return String(value);
}

/** A value as people read it, by the kind of field it fills. */
export function sourcedValue(item, value = item.shown) {
  return words(item, value) || h("span", { class: "subtle" }, "None");
}

/** The short line beside a field in a table: where its value came from. */
export function sourcedMark(item) {
  if (!item) return null;
  return item.overridden
    ? h("div", { class: "cell-sub" }, pill("Overridden", "warn"))
    : h("div", { class: "cell-sub" }, `From ${item.source_name}`);
}

function overrideForm(item, { ref, release, reload }) {
  openOverlay({
    title: `Override: ${item.label}`,
    subtitle: release ? `${ref} · release ${release}` : ref,
    kind: "dialog",
    render: (body, footer, close) => {
      const current = item.shown;
      let value;
      if (item.kind === "yes") {
        value = checkbox("Yes", { checked: Boolean(current) });
      } else {
        const type = item.kind === "date" ? "date" : item.kind === "count" ? "number" : "text";
        const shown = item.kind === "words" ? (current ?? []).join(", ") : (current ?? "");
        value = field(item.label, { type, value: String(shown), min: type === "number" ? "0" : null,
          hint: item.kind === "words" ? "Separate them with commas." : null });
      }
      const reason = field("Why the source is wrong", { type: "textarea", rows: 3, required: true,
        hint: "Kept with the override and in the history. The source's readings wait beside it." });
      const problem = banner();
      const read = () => {
        if (item.kind === "yes") return value.input.checked;
        const raw = value.input.value.trim();
        if (!raw) return null;
        if (item.kind === "count") return Number(raw);
        if (item.kind === "words") return raw.split(",").map((word) => word.trim()).filter(Boolean);
        return raw;
      };
      const save = button("Override", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { value, reason },
          run: () => post(`/api/v1/sourced/${ref}/${item.field}/override`, { value: read(), reason: reason.input.value, release }) });
        if (done) {
          close();
          toast("Overridden. Your value holds until you use the source's again.");
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, `${item.source_name} read `, h("strong", {}, sourcedValue(item, item.value)), `, ${relative(item.read_at)}.`),
        value.node, reason.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function restore(item, { ref, release, reload }) {
  confirmAction({
    title: `Use the source's value for ${item.label.toLowerCase()}?`,
    text: `The override is removed, and ${item.source_name}'s reading, ${words(item, item.value) || "none"}, holds again.`,
    confirmLabel: "Use the source's value",
    run: async () => {
      await del(`/api/v1/sourced/${ref}/${item.field}/override${release ? `?release=${encodeURIComponent(release)}` : ""}`);
      toast("The source's value holds again.");
      reload();
    },
  });
}

function entry(item, { canEdit, quiet = false, ...where }) {
  const what = where.release ? `${item.label.toLowerCase()} of ${where.release}` : item.label.toLowerCase();
  const actions = canEdit ? h("div", { class: "row-sm" }, item.overridden
    ? button("Use the source's value", { kind: "btn-sm btn-ghost", "aria-label": `Use the source's value for ${what}`, onclick: () => restore(item, where) })
    : button("Override", { kind: "btn-sm btn-ghost", "aria-label": `Override ${what}`, onclick: () => overrideForm(item, where) })) : null;
  const note = item.overridden
    ? h("div", { class: "cell-sub" }, `Overridden by ${item.override_by ?? "a change by hand"}: ${item.override_reason}. ${item.source_name} says `,
      sourcedValue(item, item.value), ".")
    : quiet ? null : h("div", { class: "cell-sub" }, `From ${item.source_name}, read ${relative(item.read_at)}`);
  return [h("dt", {}, where.release ? `${where.release} · ${item.label}` : item.label),
    h("dd", {}, h("div", { class: "row-sm wrap" }, h("span", {}, sourcedValue(item)), item.overridden ? pill("Overridden", "warn") : null), note, actions)];
}

/** The card of what other systems supply for a record, or nothing if none does. Overrides
 * come first; a long list of values that hold folds away. */
export function sourcedCard(ref, sourced, { canEdit = false, reload }) {
  const all = [...(sourced?.values ?? []).map((item) => [item, null]),
    ...(sourced?.releases ?? []).flatMap((release) => release.values.map((item) => [item, release.cycle]))];
  if (!all.length) return null;
  const named = [...new Set(all.map(([item]) => item.source_name))];
  const sources = named.join(", ");
  // With one source, the line above the list says where every value came from.
  const list = (items) => h("dl", { class: "dl dl-stacked" }, items.map(([item, release]) => entry(item, { ref, release, canEdit, reload, quiet: named.length === 1 })));
  const overridden = all.filter(([item]) => item.overridden);
  const holding = all.filter(([item]) => !item.overridden);
  const latest = all.map(([item]) => item.read_at).sort().at(-1);
  return card({ title: "From other systems" },
    h("div", { class: "stack" },
      h("p", { class: "subtle" }, `${all.length === 1 ? "One value" : `${all.length} values`} from ${sources}, last read ${relative(latest)}. A connector only reads; an override wins until it is removed.`),
      overridden.length ? list(overridden) : null,
      holding.length > 10 ? h("details", {}, h("summary", {}, overridden.length ? `The other ${holding.length}` : `All ${holding.length}`), list(holding))
        : holding.length ? list(holding) : null));
}

/** For a technology's releases table: each release's sourced values, by cycle and field. */
export function byRelease(sourced) {
  const out = {};
  for (const release of sourced?.releases ?? []) out[release.cycle] = Object.fromEntries(release.values.map((item) => [item.field, item]));
  return out;
}
