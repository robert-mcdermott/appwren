// The optional assistant: ask about the portfolio, with links to the records behind the
// answer; and draft an application from a document, for the person to correct and add.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { navigate } from "../core/router.js";
import { can } from "../core/session.js";
import { unitOptions, units } from "../core/lookups.js";
import { banner, field, select, submit } from "../components/form.js";
import { recordChip } from "../components/record.js";
import { alert, card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

function askCard() {
  const question = field("Your question", { type: "textarea", rows: 3, maxlength: 1000, placeholder: "Which applications handle participant consent, and what was decided about them?" });
  const problem = banner();
  const out = h("div", { class: "stack", "aria-live": "polite" });
  const go = button("Ask", { kind: "btn-primary" });
  go.addEventListener("click", async () => {
    out.replaceChildren(h("p", { class: "muted" }, "Asking…"));
    const said = await submit({ button: go, banner: problem, fields: { question },
      run: () => post("/api/v1/assistant/ask", { question: question.input.value }) });
    if (!said) {
      out.replaceChildren();
      return;
    }
    const found = said.data;
    out.replaceChildren(found.failed ? alert("warn", h("p", {}, found.failed))
      : h("div", { class: "stack" }, h("p", { class: "assistant-answer" }, found.answer),
        found.records.length ? h("div", { class: "row-sm wrap" }, found.records.map((record) => recordChip(record))) : null,
        h("p", { class: "subtle" }, found.note)));
  });
  return card({ title: "Ask about the portfolio" }, h("div", { class: "stack" }, problem, question.node,
    h("div", { class: "row" }, go), out));
}

function draftCard(unitIndex) {
  const text = field("A description of the application", { type: "textarea", rows: 8, maxlength: 12000,
    hint: "Paste from a vendor's page, a proposal, or a design document. Nothing is saved until you add it." });
  const problem = banner();
  const out = h("div", { class: "stack", "aria-live": "polite" });
  const go = button("Draft it", { kind: "btn-primary" });
  go.addEventListener("click", async () => {
    out.replaceChildren(h("p", { class: "muted" }, "Drafting…"));
    const said = await submit({ button: go, banner: problem, fields: { text },
      run: () => post("/api/v1/assistant/draft", { text: text.input.value }) });
    if (!said) {
      out.replaceChildren();
      return;
    }
    const found = said.data;
    if (found.failed) {
      out.replaceChildren(alert("warn", h("p", {}, found.failed)));
      return;
    }
    const unit = select("Its unit", unitOptions(unitIndex.tree, { blank: "Choose a unit" }), { hint: "The unit that answers for it. The assistant does not choose it." });
    const add = button("Add the application", { kind: "btn-primary" });
    const added = banner();
    add.addEventListener("click", async () => {
      const done = await submit({ button: add, banner: added, fields: { org_unit_id: unit },
        run: () => post("/api/v1/applications", { ...found.values, org_unit_id: Number(unit.input.value) || null }) });
      if (done) navigate(`/applications/${done.data.ref}`);
    });
    out.replaceChildren(h("div", { class: "stack" },
      h("p", { class: "subtle" }, found.note),
      h("dl", { class: "dl" }, Object.entries(found.values).map(([key, value]) => [h("dt", {}, key.replaceAll("_", " ")),
        h("dd", {}, Array.isArray(value) ? value.join(", ") : String(value))])),
      found.dropped.length ? h("p", { class: "subtle" }, `Left out, as the form would not take them: ${found.dropped.join(", ")}.`) : null,
      can("keep") ? [added, unit.node, h("div", { class: "row" }, add)]
        : h("p", { class: "muted" }, "Ask a steward of the unit to add it.")));
  });
  return card({ title: "Draft an application from a document" }, h("div", { class: "stack" }, problem, text.node,
    h("div", { class: "row" }, go), out));
}

export function assistantPage(main) {
  return show(main, {
    title: "Assistant",
    load: async () => ({ unitIndex: await units() }),
    view: (data) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Portfolio", title: "Assistant",
        lede: "Ask about the applications you may see, or draft a new one from a document. The assistant reads only what you may, changes nothing, and every exchange is kept." }),
      askCard(), draftCard(data.unitIndex)),
  });
}
