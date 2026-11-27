// Changes proposed to an application, waiting for someone who keeps it. Loaded only on an
// application's page when some wait.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { dateTime } from "../core/format.js";
import { toast } from "./toast.js";
import { card } from "./ui.js";

function shown(value) {
  if (value == null || value === "") return h("span", { class: "subtle" }, "Empty");
  return Array.isArray(value) ? value.join(", ") : String(value);
}

/** The proposals, each with what it would set, who proposed it and why, and, for someone who keeps it, Accept and Dismiss. */
export function suggestionsCard(record, found, reload) {
  const decide = async (item, how) => {
    try {
      await post(`/api/v1/suggestions/${item.id}/${how}`);
      toast(how === "accept" ? `${item.field_label} was changed.` : "The suggestion was dismissed.");
    } catch (error) {
      toast(Object.values(error.fields ?? {}).join(" ") || error.detail || "That could not be done.");
    }
    reload();
  };
  return card({ title: `${found.pending.length === 1 ? "A change is" : `${found.pending.length} changes are`} proposed` },
    h("div", { class: "stack" },
      h("p", { class: "muted" }, "Nothing has changed yet. Someone who keeps this application accepts a proposal, which is their own edit, or dismisses it."),
      h("ul", { class: "plain-list stack-sm" }, found.pending.map((item) => h("li", { class: "row wrap" },
        h("div", { class: "grow" },
          h("div", {}, h("strong", {}, item.field_label), ": ", shown(item.value)),
          h("div", { class: "cell-sub" }, `Proposed by ${item.source}, ${dateTime(item.created_at)}`, item.note ? `. ${item.note}` : "")),
        found.may_decide ? h("div", { class: "row-sm" },
          button("Accept", { kind: "btn-sm", "aria-label": `Accept the proposed ${item.field_label.toLowerCase()}`, onclick: () => decide(item, "accept") }),
          button("Dismiss", { kind: "btn-sm btn-ghost", "aria-label": `Dismiss the proposed ${item.field_label.toLowerCase()}`, onclick: () => decide(item, "dismiss") })) : null)))));
}
