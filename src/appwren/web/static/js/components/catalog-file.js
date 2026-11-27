// Importing a catalog file into an application and its components: checked first, with
// what would change shown, then imported. Loaded only when someone asks to import one.

import { upload } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { banner, field, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";

export function importCatalog(record, ctx) {
  openOverlay({
    title: "Import a catalog file",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const text = field("The file", { type: "textarea", rows: 12, spellcheck: "false", class: "textarea code-input",
        hint: "Paste a catalog-info.yaml kept beside the code: a System document for the application, and a Component or Resource document for each part." });
      const chooser = h("input", { type: "file", accept: ".yaml,.yml,text/yaml", "aria-label": "Choose a catalog file" });
      chooser.addEventListener("change", async () => {
        const file = chooser.files?.[0];
        if (file) text.input.value = await file.text();
      });
      const problem = banner();
      const result = h("div", { class: "stack", "aria-live": "polite" });
      const check = button("Check what would change", { kind: "btn-primary" });
      const apply = button("Import", { kind: "btn-primary", hidden: true });
      const send = (dryRun) => upload(`/api/v1/applications/${record.ref}/catalog`, new Blob([text.input.value], { type: "application/yaml" }), { dry_run: dryRun });
      const said = (report) => {
        const lines = [...report.application.changes.map((c) => `${record.name}: ${c.label.toLowerCase()} becomes ${Array.isArray(c.to) ? c.to.join(", ") : c.to}`),
          ...report.components.filter((c) => c.action === "add").map((c) => `A new component: ${c.name}`),
          ...report.components.filter((c) => c.action === "change").flatMap((c) => c.changes.map((x) => `${c.name}: ${x.label.toLowerCase()} becomes ${x.to}`))];
        return h("div", { class: "stack-sm" },
          lines.length ? h("ul", { class: "plain-list" }, lines.map((line) => h("li", {}, line))) : h("p", {}, "Nothing would change: the record already says what the file says."),
          report.ignored.length ? h("p", { class: "subtle" }, `Not read: ${report.ignored.map((i) => `${i.what} (${i.why})`).join("; ")}.`) : null);
      };
      check.addEventListener("click", async () => {
        const done = await submit({ button: check, banner: problem, run: () => send(true) });
        if (!done) return;
        result.replaceChildren(h("h3", {}, "What would change"), said(done.data));
        apply.hidden = !done.data.changed;
      });
      apply.addEventListener("click", async () => {
        const done = await submit({ button: apply, banner: problem, run: () => send(false) });
        if (done) {
          close();
          toast("Imported. Nothing the file does not mention was changed.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, chooser, text.node, result));
      footer.replaceChildren(h("div", { class: "row" }, check, apply, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
