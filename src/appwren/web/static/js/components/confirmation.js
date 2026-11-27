// Confirming a record: the people who keep an application say that it is right, on a cadence
// set by its tier. A record past its confirmation is trusted less until someone does.

import { post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date } from "../core/format.js";
import { banner, field, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";

/** Ask for a confirmation, with what it covers and an optional note. */
export function confirmRecord(record, onDone) {
  openOverlay({
    title: "Confirm the record",
    subtitle: `${record.ref} · ${record.name}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const note = field("Note", { type: "textarea", rows: 3, hint: "Optional. What you checked, or anything the next person should know." });
      const problem = banner();
      const save = button("Confirm", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { note },
          run: () => post(`/api/v1/applications/${record.ref}/confirmations`, { note: note.input.value || null }) });
        if (done) {
          close();
          toast("The record is confirmed.");
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", {}, "You confirm that this record is right as of today: its details, the people named on it, its components and what they are built on, what it sends and receives, where it runs, and what it costs."),
        h("p", { class: "muted" }, "If something is wrong, put it right first, then confirm."),
        note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** One line under the scores: when the record was last confirmed and when it is next due. */
export function confirmationLine(state, penalty, onConfirm) {
  if (!state || !state.due_on) return null;
  const last = state.last ? `Confirmed on ${date(state.last.on)} by ${state.last.by}.` : "Not confirmed yet.";
  const action = state.can_confirm ? button("Confirm the record", { kind: state.stale ? "btn-sm btn-primary" : "btn-sm", onclick: onConfirm }) : null;
  if (state.stale) {
    return h("div", { class: "alert alert-warn confirm-line", role: "status" }, icon("alert"),
      h("div", { class: "grow" }, h("strong", {}, `Due to be confirmed by ${date(state.due_on)}. `), last,
        penalty ? ` Until someone confirms it, its data confidence is ${penalty} points lower.` : ""),
      action);
  }
  return h("div", { class: "confirm-line row-sm wrap subtle" }, icon("check", "icon icon-sm"),
    h("span", { class: "grow" }, `${last} Next due by ${date(state.due_on)}.`), action);
}
