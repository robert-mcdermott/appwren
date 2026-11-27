// Planning change on a record's page: a review's agenda. Loaded only on the pages that need it.

import { del, get, post, put } from "../core/api.js";
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

// --- Initiatives ------------------------------------------------------------------------------

const ACTIONS = [["changes", "Changes it"], ["retires", "Retires it"], ["receives", "Moves work onto it"]];

function editApplications(record, reload) {
  const rows = record.applications.map((a) => ({ ref: a.ref, name: a.name, action: a.action, note: a.note ?? "" }));
  openOverlay({
    title: "The applications it changes",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("div", { class: "owner-row" },
          h("div", { class: "grow" }, recordChip({ ...row, type: "application" }, { link: false })),
          h("select", { class: "select", "aria-label": `What it does to ${row.name}`, onchange: (event) => { row.action = event.target.value; } },
            ACTIONS.map(([key, text]) => h("option", { value: key, selected: key === row.action }, text))),
          h("input", { class: "input", value: row.note, placeholder: "A note", "aria-label": `A note on ${row.name}`, oninput: (event) => { row.note = event.target.value; } }),
          button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "None yet.")]));
      };
      draw();
      const finder = recordFinder("application", { exclude: (r) => rows.some((row) => row.ref === r.ref), onPick: (r) => {
        rows.push({ ref: r.ref, name: r.name, action: "changes", note: "" });
        draw();
        finder.refresh();
      } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/initiatives/${record.ref}/applications`, { applications: rows.map((row) => ({ application: row.ref, action: row.action, note: row.note || null })) }) });
        if (done) {
          close();
          toast("Saved.");
          reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "Say what the initiative does to each: changes it, retires it, or moves the work of the others onto it."),
        list, h("div", { class: "field" }, h("div", { class: "label" }, "Add an application"), finder.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** An initiative's applications, what it does to each, and the decision on record for each. */
export function initiativeApplications(record, ctx) {
  const vocab = ctx.vocab;
  const apps = record.applications;
  return card({ title: apps.length ? `Changes ${plural(apps.length, "application")}` : "What it changes",
    actions: record.may_keep ? button("Edit", { kind: "btn-sm", onclick: () => editApplications(record, ctx.reload) }) : null, flush: apps.length > 0 },
  apps.length ? [h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, ["Application", "What it does", "Decision on record"].map((text) => h("th", { scope: "col" }, text)))),
    h("tbody", {}, apps.map((a) => h("tr", {},
      h("td", {}, recordChip(a), h("div", { class: "cell-sub" }, label(vocab, "lifecycle", a.lifecycle))),
      h("td", {}, a.action_label, a.note ? h("div", { class: "cell-sub" }, a.note) : null),
      h("td", {}, a.decision ? h("div", { class: "stack-sm" }, disposition(vocab, a.decision.disposition, true),
        h("span", { class: "cell-sub" }, `${a.decision.by}, ${date(a.decision.decided_on)}`,
          a.decision.target_on ? `; to be done by ${date(a.decision.target_on)}` : "")) : h("span", { class: "subtle" }, "None"))))))),
  record.hidden_applications ? h("p", { class: "card-note subtle" }, `${plural(record.hidden_applications, "other application")} it names ${record.hidden_applications === 1 ? "is" : "are"} not shown to you.`) : null]
    : h("p", { class: "muted" }, "No application is named yet. Say which it changes, retires, or moves work onto."));
}

// --- Requests ---------------------------------------------------------------------------------

const APPROACHES = [["build", "Build it"], ["buy", "Buy it"], ["partner", "Partner for it"], ["reuse", "Reuse what is on record"]];
const REQUEST_TONES = { submitted: "", evaluating: "accent", approved: "ok", met: "ok", declined: "warn" };

export function requestState(record) {
  return pill(record.state_label, REQUEST_TONES[record.state] ?? "");
}

function editOptions(record, reload) {
  const rows = record.options.map((o) => ({ approach: o.approach, name: o.name, vendor: o.vendor?.ref ?? "", application: o.application?.ref ?? "",
    annual_cost: o.annual_cost ?? "", fit: o.fit ?? "", notes: o.notes ?? "" }));
  openOverlay({
    title: "Ways to meet it",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack" });
      const problem = banner();
      const input = (row, key, text, attrs = {}) => h("input", { class: "input", value: row[key], "aria-label": text, placeholder: text, ...attrs,
        oninput: (event) => { row[key] = event.target.value; } });
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("fieldset", { class: "option-row" },
          h("legend", { class: "sr-only" }, `Option ${index + 1}`),
          h("select", { class: "select", "aria-label": `How, option ${index + 1}`, onchange: (event) => { row.approach = event.target.value; } },
            APPROACHES.map(([key, text]) => h("option", { value: key, selected: key === row.approach }, text))),
          input(row, "name", `Name, option ${index + 1}`),
          input(row, "application", `Application on record (APP-…), option ${index + 1}`),
          input(row, "vendor", `Vendor (VEN-…), option ${index + 1}`),
          input(row, "annual_cost", `Cost a year, option ${index + 1}`, { type: "number", min: "0" }),
          input(row, "fit", `Fit, 1 to 5, option ${index + 1}`, { type: "number", min: "1", max: "5" }),
          input(row, "notes", `Why, option ${index + 1}`),
          button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "None yet.")]));
      };
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const none = (value) => (value === "" ? null : value);
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/requests/${record.ref}/options`, { options: rows.map((row) => ({ approach: row.approach, name: none(row.name),
            application: none(row.application), vendor: none(row.vendor), annual_cost: row.annual_cost === "" ? null : Number(row.annual_cost),
            fit: row.fit === "" ? null : Number(row.fit), notes: none(row.notes) })) }) });
        if (done) {
          close();
          toast("Saved. The request is being weighed.");
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, "Each way to meet the need: build it, buy it, partner for it, or reuse an application on record; what it would cost a year, and how well it fits, 1 to 5."),
        list, button("Add an option", { iconName: "plus", kind: "btn-sm", onclick: () => {
          rows.push({ approach: "buy", name: "", vendor: "", application: "", annual_cost: "", fit: "", notes: "" });
          draw();
        } })));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function endRequest(record, how, reload) {
  const words = { approve: ["Approve the request", "Approve", "An application in the proposed stage is added, named for the request, serving its capability. Nothing is built or bought by this."],
    meet: ["Met by an application on record", "Say it is met", "Name the application that already meets the need."],
    decline: ["Decline the request", "Decline", "Say why, for whoever asked."] }[how];
  openOverlay({
    title: words[0],
    subtitle: `${record.ref} · ${record.name}`,
    kind: "dialog",
    render: (body, footer, close) => {
      const fields = { reason: field("Why", { type: "textarea", rows: 3, maxlength: 2000 }) };
      if (how === "approve") fields.name = field("Name of the application", { value: record.name, maxlength: 200 });
      let chosen = null;
      const finder = how === "meet" ? recordFinder("application", { onPick: (app) => {
        chosen = app;
        picked.replaceChildren(h("p", {}, "Chosen: ", recordChip(app, { link: false })));
      } }) : null;
      const picked = h("div", { "aria-live": "polite" });
      const problem = banner();
      const save = button(words[1], { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields,
          run: () => post(`/api/v1/requests/${record.ref}/${how}`, { reason: fields.reason.input.value, name: fields.name?.input.value ?? null, application: chosen?.ref ?? null }) });
        if (done) {
          close();
          toast(how === "approve" ? `Approved. ${done.data.outcome.application.ref} is added, in the proposed stage.` : "The request has ended.");
          reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, h("p", { class: "muted" }, words[2]),
        finder ? h("div", { class: "field" }, h("div", { class: "label" }, "Application"), finder.node) : null, picked,
        fields.name?.node, fields.reason.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

/** A request: what already serves the need, the ways to meet it, and how it ended. */
export function requestPanel(record, ctx) {
  const vocab = ctx.vocab;
  const serving = record.serving;
  const there = card({ title: serving.length ? `${plural(serving.length, "application")} already serve${serving.length === 1 ? "s" : ""} ${record.capability?.name ?? "this"}` : "What already serves the need", flush: serving.length > 0 },
    serving.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["Application", "Stage", "People who use it", "Decision on record"].map((text) => h("th", { scope: "col" }, text)))),
      h("tbody", {}, serving.slice(0, 8).map((a) => h("tr", {}, h("td", {}, recordChip(a), a.is_primary ? h("div", { class: "cell-sub" }, "Primary provider") : null),
        h("td", {}, label(vocab, "lifecycle", a.lifecycle)), h("td", { class: "numeric" }, a.users == null ? "—" : Number(a.users).toLocaleString()),
        h("td", {}, disposition(vocab, a.disposition, true)))))))
      : h("p", { class: "muted" }, "Nothing on record serves this capability yet."),
    serving.length > 8 && record.capability ? h("p", { class: "card-note" }, h("a", { href: `/capabilities/${record.capability.ref}` }, `All ${serving.length}, on the capability's page`)) : null,
    record.similar.length ? h("p", { class: "card-note muted" }, "Named like it: ", record.similar.map((a, i) => [i ? ", " : "", recordChip(a)])) : null);
  const options = card({ title: "Ways to meet it", actions: record.may_work ? button(record.options.length ? "Edit" : "Weigh the options", { kind: "btn-sm", onclick: () => editOptions(record, ctx.reload) }) : null, flush: record.options.length > 0 },
    record.options.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, ["How", "What", "Cost a year", "Fit", "Why"].map((text) => h("th", { scope: "col" }, text)))),
      h("tbody", {}, record.options.map((o) => h("tr", {}, h("td", {}, o.approach_label),
        h("td", {}, o.application ? recordChip(o.application) : o.name, o.vendor ? h("div", { class: "cell-sub" }, recordChip(o.vendor)) : null),
        h("td", { class: "numeric" }, o.annual_cost == null ? "—" : Number(o.annual_cost).toLocaleString()),
        h("td", { class: "numeric" }, o.fit == null ? "—" : `${o.fit} of 5`),
        h("td", {}, o.notes ?? ""))))))
      : h("p", { class: "muted" }, record.may_work ? "Weigh building, buying, partnering, and reusing what is on record." : "Not weighed yet."));
  const outcome = record.outcome
    ? card({ title: record.state_label }, h("div", { class: "stack-sm" }, h("p", {}, record.outcome.reason),
      record.outcome.application ? h("p", {}, "Application: ", recordChip(record.outcome.application)) : null,
      h("p", { class: "subtle" }, `${record.outcome.by}, ${date(record.outcome.at)}`)))
    : record.may_work ? card({ title: "End it", actions: h("div", { class: "row-sm wrap" },
      button("Approve", { kind: "btn-sm btn-primary", onclick: () => endRequest(record, "approve", ctx.reload) }),
      button("Met by one on record", { kind: "btn-sm", onclick: () => endRequest(record, "meet", ctx.reload) }),
      button("Decline", { kind: "btn-sm btn-ghost", onclick: () => endRequest(record, "decline", ctx.reload) })) },
    h("p", { class: "muted" }, "Approving adds an application in the proposed stage, named for the request. A request ends once.")) : null;
  return record.outcome ? [outcome, there, options] : [there, options, outcome];
}
