// Planning change on a record's page: a review's agenda. Loaded only on the pages that need it.

import { del, get, post } from "../core/api.js";
import { button, h, iconButton } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label } from "../core/lookups.js";
import { recordDecision } from "./decision.js";
import { banner, field, submit } from "./form.js";
import { confirmAction, openOverlay } from "./overlay.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
import { card, dispositionBadge, emptyState, pill } from "./ui.js";
import { recordFinder } from "../pages/record.js";

const STATES = { planned: ["Planned", ""], open: ["Open", "accent"], closed: ["Closed", "ok"] };

export function reviewState(state) {
  const [text, tone] = STATES[state] ?? [state, ""];
  return pill(text, tone);
}

function disposition(vocab, key, decided = false) {
  return key ? dispositionBadge(key, label(vocab, "dispositions", key), { decided }) : h("span", { class: "subtle" }, "None");
}

async function decideFrom(item, vocab, reload) {
  const ref = item.application.ref;
  const [app, scores] = await Promise.all([get(`/api/v1/applications/${ref}`, null, { fresh: true }), get(`/api/v1/applications/${ref}/scores`, null, { fresh: true })]);
  recordDecision(app.data, scores.data, vocab, reload);
}

function addItem(record, reload) {
  openOverlay({
    title: "Put an application on the agenda",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      let chosen = null;
      const picked = h("div", { "aria-live": "polite" });
      const finder = recordFinder("application", { onPick: (app) => {
        chosen = app;
        picked.replaceChildren(h("p", {}, "Chosen: ", recordChip(app, { link: false })));
      } });
      const note = field("What to decide", { type: "textarea", rows: 3, maxlength: 2000 });
      const problem = banner();
      const save = button("Put it on the agenda", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!chosen) {
          problem.textContent = "Choose an application first.";
          problem.hidden = false;
          return;
        }
        const done = await submit({ button: save, banner: problem, fields: { note },
          run: () => post(`/api/v1/reviews/${record.ref}/items`, { application: chosen.ref, note: note.input.value }) });
        if (done) {
          close();
          toast(`${chosen.name} is on the agenda.`);
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, h("div", { class: "field" }, h("div", { class: "label" }, "Application"), finder.node), picked, note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** A review's agenda: why each application is there, what is recommended, what is on record,
 * and what the review decided. */
export function reviewAgenda(record, ctx) {
  const agenda = record.agenda;
  const vocab = ctx.vocab;
  const may = record.may_run;
  const act = (text, path, said, kind = "btn-sm") => button(text, { kind, onclick: async () => {
    try {
      const done = await post(`/api/v1/reviews/${record.ref}/${path}`, {});
      toast(said(done));
      ctx.reload();
    } catch (error) {
      toast(error.detail ?? error.message);
    }
  } });
  const actions = may ? h("div", { class: "row-sm wrap" },
    act("Draw the agenda", "draw", (done) => (done.meta.added ? `${plural(done.meta.added, "application")} added.` : "Nothing more needs deciding in its scope.")),
    button("Add an application", { kind: "btn-sm", onclick: () => addItem(record, ctx.reload) }),
    record.state === "planned" ? act("Open the review", "open", () => "The review is open. Decisions recorded now are kept on its agenda.", "btn-sm btn-primary") : null,
    record.state === "open" ? button("Close the review", { kind: "btn-sm btn-primary", onclick: () => confirmAction({
      title: "Close the review?", text: `${plural(agenda.decided, "decision")} taken, ${agenda.waiting} still to decide. Once closed, the review is a record of what was decided and changes no more.`,
      confirmLabel: "Close the review", run: async () => {
        await post(`/api/v1/reviews/${record.ref}/close`, {});
        toast("The review is closed.");
        ctx.reload();
      } }) }) : null) : null;
  const rows = agenda.items.map((item) => h("tr", {},
    h("td", {}, recordChip(item.application), item.tier ? h("div", { class: "cell-sub" }, `Tier ${item.tier}`) : null),
    h("td", {}, item.reason_label, item.note ? h("div", { class: "cell-sub" }, item.note) : null),
    h("td", {}, disposition(vocab, item.recommendation)),
    h("td", {}, disposition(vocab, item.disposition, true)),
    h("td", {}, item.taken ? h("div", { class: "stack-sm" }, disposition(vocab, item.taken.disposition, true),
      h("span", { class: "cell-sub" }, `${item.taken.by}, ${date(item.taken.on)}`))
      : record.state === "open" && may ? button("Record a decision", { kind: "btn-sm", "aria-label": `Record a decision for ${item.application.name}`, onclick: () => decideFrom(item, vocab, ctx.reload) })
        : h("span", { class: "subtle" }, record.state === "closed" ? "Not decided" : "Not yet")),
    may ? h("td", { class: "cell-actions" }, iconButton("trash", `Take ${item.application.name} off the agenda`, { onclick: async () => {
      await del(`/api/v1/reviews/${record.ref}/items/${item.id}`);
      toast(`${item.application.name} is off the agenda.`);
      ctx.reload();
    } })) : null));
  const said = [`${plural(agenda.items.length, "application")} on the agenda`, `${agenda.decided} decided`, `${agenda.waiting} to decide`];
  return card({ title: h("span", { class: "row-sm wrap" }, "Agenda", reviewState(record.state)), actions, flush: agenda.items.length > 0 },
    agenda.items.length ? [h("p", { class: "card-note muted" }, `${said.join(" · ")}.`,
      agenda.hidden ? ` ${plural(agenda.hidden, "application")} on it ${agenda.hidden === 1 ? "is" : "are"} not shown to you.` : ""),
    h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["Application", "Why it is here", "Recommended", "Decided before", "Decided in this review"].map((text) => h("th", { scope: "col" }, text)),
        may ? h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Remove")) : null)),
      h("tbody", {}, rows)))]
      : emptyState({ iconName: "list", title: "Nothing on the agenda yet",
        text: may ? "Draw the agenda to add what needs deciding in its scope: decisions that differ from today's recommendation, decisions due for review, and applications with none." : "Whoever runs the review has not drawn its agenda yet." }));
}
