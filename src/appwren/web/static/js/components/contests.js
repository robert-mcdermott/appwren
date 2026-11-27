// Contesting a score: an owner says one factor is wrong, what it should be, and why, with a
// link to the evidence; the portfolio team accepts or answers it. Both stay on the record.

import { post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { card, pill } from "./ui.js";

const STATUS = { open: ["Waiting for an answer", "warn"], accepted: ["Accepted", "ok"], answered: ["Answered", ""] };

function raise(ref, scores, onDone) {
  openOverlay({ title: "Contest a factor", subtitle: ref, render: (body, footer, close) => {
    const factors = Object.values(scores.dimensions).flatMap((dimension) => dimension.factors
      .filter((factor) => factor.state !== "not_applicable")
      .map((factor) => [factor.key, `${dimension.label}: ${factor.label}${factor.level ? ` (level ${factor.level})` : " (unknown)"}`]));
    const factor = select("Which factor is wrong", [["", "Choose…"], ...factors]);
    const level = select("What it should be", [["", "Not sure"], ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"], ["5", "5"]]);
    const note = field("Why", { type: "textarea", rows: 4, required: true, hint: "What the scores do not know. The manager or architect who answers will read it." });
    const evidence = field("Where the evidence is", { type: "url", hint: "Optional. A link to a document, a dashboard, a ticket." });
    const problem = banner();
    const save = button("Contest it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { factor, level_claimed: level, note, evidence_url: evidence },
        run: () => post(`/api/v1/applications/${ref}/contests`, { factor: factor.input.value, note: note.input.value,
          level_claimed: level.input.value ? Number(level.input.value) : null, evidence_url: evidence.input.value || null }) });
      if (done) {
        close();
        toast("Contested. The portfolio team has been told.");
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem,
      h("p", { class: "muted" }, "A contest does not change the score. If it is accepted, the record or an assessment is put right, and the score follows."),
      factor.node, level.node, note.node, evidence.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function answerOne(contest, onDone) {
  openOverlay({ title: "Answer the contest", subtitle: `${contest.factor_label} · ${contest.application.name}`, kind: "dialog", render: (body, footer, close) => {
    const accept = checkbox("Accept it", { hint: "It is right: say what will be changed, and where." });
    const text = field("Answer", { type: "textarea", rows: 4, required: true });
    const problem = banner();
    const save = button("Record the answer", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { answer: text },
        run: () => post(`/api/v1/contests/${contest.id}/answer`, { accept: accept.input.checked, answer: text.input.value }) });
      if (done) {
        close();
        toast("The answer is recorded, and the owner has been told.");
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem, h("blockquote", { class: "quote" }, contest.note), accept.node, text.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

/** The contests of an application's scores, with the means to raise or answer one. */
export function contestsCard(ref, scores, data, onDone) {
  const rows = data?.contests ?? [];
  return card({ title: "Contests", actions: data?.can_raise ? button("Contest a factor", { kind: "btn-sm", onclick: () => raise(ref, scores, onDone) }) : null },
    rows.length ? h("ul", { class: "found-list" }, rows.map((contest) => h("li", { class: "contest" },
      h("div", { class: "grow stack-sm" },
        h("div", { class: "row-sm wrap" }, h("span", { class: "cell-main" }, contest.factor_label), pill(...STATUS[contest.status])),
        h("div", { class: "cell-sub" }, `${contest.raised_by}, ${date(contest.raised_on)}: shown at ${contest.level_shown ?? "unknown"}`,
          contest.level_claimed ? `, should be ${contest.level_claimed}` : ""),
        h("p", {}, contest.note),
        contest.evidence_url ? h("a", { href: contest.evidence_url, target: "_blank", rel: "noopener noreferrer" }, "The evidence") : null,
        contest.answer ? h("p", { class: "muted" }, `${contest.answered_by}, ${date(contest.answered_on)}: ${contest.answer}`) : null),
      contest.can_answer ? button("Answer", { kind: "btn-sm", onclick: () => answerOne(contest, onDone) }) : null)))
      : h("p", { class: "muted" }, "Nobody has contested these scores. If a factor is wrong, say so with the evidence: the portfolio team answers."));
}
