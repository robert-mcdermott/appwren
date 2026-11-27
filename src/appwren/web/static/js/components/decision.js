// Recording a decision, and showing decisions and the scores they were made against.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { label, options } from "../core/lookups.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { recordChip } from "./record.js";
import { scorecard, verdict, working, DIMENSIONS } from "./scorecard.js";
import { toast } from "./toast.js";
import { card, dispositionBadge, pill } from "./ui.js";

function inYear() {
  const day = new Date();
  day.setFullYear(day.getFullYear() + 1);
  return day.toISOString().slice(0, 10);
}

/** Record what to do with an application, with the recommendation and its reasons beside. */
export function recordDecision(record, scores, vocab, onDone) {
  openOverlay({
    title: "Record a decision",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const recommended = scores.recommendation;
      const disposition = select("Disposition", options(vocab, "dispositions"), { value: recommended ?? "maintain",
        hint: recommended ? `Recommended: ${label(vocab, "dispositions", recommended)}. You may decide otherwise; say why.` : null });
      const rationale = field("Why", { type: "textarea", rows: 4, required: true,
        hint: "The reasons, in a few sentences. The next person to look at this will read them." });
      const review = field("Look at it again on", { type: "date", value: inYear() });
      const target = field("To be done by", { type: "date", hint: "Optional. When the change should be complete." });
      const successor = select("Its users move to", [["", "Choose…"]], { hint: "The application that takes over: needed to consolidate." });
      const successorRow = h("div", {}, successor.node);
      const sync = () => {
        successorRow.hidden = !["consolidate", "replace"].includes(disposition.input.value);
      };
      disposition.input.addEventListener("change", sync);
      sync();
      get("/api/v1/applications", { sort: "name", limit: 200, status: "active" }).then((page) => {
        for (const app of page.data.filter((a) => a.ref !== record.ref)) {
          successor.input.append(h("option", { value: app.ref, selected: scores.overlap_with?.ref === app.ref }, `${app.name} (${app.ref})`));
        }
      });
      const problem = banner();
      const save = button("Record the decision", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { disposition, rationale, review_on: review, target_on: target, successor },
          run: () => post(`/api/v1/applications/${record.ref}/decisions`, {
            disposition: disposition.input.value, rationale: rationale.input.value,
            review_on: review.input.value || null, target_on: target.input.value || null,
            successor: successorRow.hidden ? null : successor.input.value || null }) });
        if (done) {
          close();
          toast(`${done.data.ref} was recorded.`);
          onDone?.();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        card({ title: "Today's scores" }, scorecard(scores, { onOpen: () => {} }), verdict(scores, vocab)),
        disposition.node, rationale.node, h("div", { class: "grid-2" }, review.node, target.node), successorRow,
        h("p", { class: "subtle" }, "The scores as they are now are kept with the decision. A decision is never edited; record a new one to change it.")));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** A kept score, as it was when it was kept. */
export async function openSnapshot(snapshotId, vocab) {
  const data = (await get(`/api/v1/score-snapshots/${snapshotId}`)).data;
  openOverlay({
    title: "The scores at the time",
    subtitle: `${data.application.ref} · kept ${date(data.taken_at)}`,
    render: (body) => {
      body.append(h("div", { class: "stack-lg" },
        data.intact ? null : h("div", { class: "alert alert-danger" }, "This snapshot no longer matches what was recorded."),
        scorecard(data.result, { onOpen: () => {} }), verdict(data.result, vocab),
        DIMENSIONS.map(([key]) => card({ title: data.result.dimensions[key].label }, working(data.result, key)))));
    },
  });
}

export function decisionsTab(record, history, vocab, { mayDecide, onDecide }) {
  const now = history.find((d) => !d.superseded);
  const earlier = history.filter((d) => d.superseded);
  const show = (d) => h("div", { class: "stack-sm" },
    h("div", { class: "row-sm wrap" }, dispositionBadge(d.disposition, label(vocab, "dispositions", d.disposition), { decided: true }),
      h("span", { class: "muted" }, `${d.ref} by ${d.decided_by} on ${date(d.decided_on)}`),
      d.self_recorded ? pill("Recorded by its own owner", "warn") : null,
      d.differed ? pill(`Recommended then: ${label(vocab, "dispositions", d.recommendation)}`, "info") : null,
      d.review_due ? pill("Review due", "warn") : null),
    h("p", { class: "prose" }, d.rationale),
    h("dl", { class: "dl" },
      h("dt", {}, "Review"), h("dd", {}, date(d.review_on)),
      d.target_on ? [h("dt", {}, "To be done by"), h("dd", {}, date(d.target_on))] : null,
      d.successor ? [h("dt", {}, "Its users move to"), h("dd", {}, recordChip(d.successor))] : null),
    button("The scores at the time", { kind: "btn-sm btn-ghost", onclick: () => openSnapshot(d.snapshot_id, vocab) }));
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" }, card({ title: "The decision on record",
      actions: mayDecide ? button(now ? "Record a new decision" : "Record a decision", { kind: "btn-sm btn-primary", onclick: onDecide }) : null },
    now ? show(now) : h("p", { class: "muted" }, "No decision yet. A manager, or a leader of its unit, records what to do with it and why."))),
    h("div", { class: "stack-lg" }, card({ title: "Earlier decisions" },
      earlier.length ? h("div", { class: "stack-lg" }, earlier.map(show)) : h("p", { class: "muted" }, "None."))));
}
