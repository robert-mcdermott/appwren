// Tasks: raised by what happens (a contract's notice date near, a release reaching end of
// support, a grant ending, an owner leaving) for whoever must act. And what a person holds,
// passed on in one step.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { query, setQuery } from "../core/router.js";
import { can, session } from "../core/session.js";
import { banner, field, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { personField } from "../components/people-picker.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const STATUS = { open: ["Open", "info"], done: ["Done", "ok"], dismissed: ["Dismissed", ""] };
const taskPill = (task) => (task.late ? pill("Past its date", "danger") : pill(...STATUS[task.status]));

function closeTask(task, how, onDone) {
  openOverlay({ title: how === "done" ? "Mark it done" : "Dismiss it", subtitle: task.title, kind: "dialog", render: (body, footer, close) => {
    const note = field(how === "done" ? "What was done" : "Why it need not be done", { type: "textarea", rows: 3, required: true,
      hint: "Kept with the task, for whoever looks next." });
    const problem = banner();
    const save = button(how === "done" ? "Mark it done" : "Dismiss it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { note },
        run: () => post(`/api/v1/tasks/${task.id}/close`, { how, note: note.input.value }) });
      if (done) {
        close();
        toast(how === "done" ? "Marked done." : "Dismissed.");
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem, note.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function actions(task, reload) {
  if (!task.can_close) return null;
  return h("div", { class: "row-sm" },
    button("Mark done", { kind: "btn-sm", "aria-label": `Mark done: ${task.title}`, onclick: () => closeTask(task, "done", reload) }),
    button("Dismiss", { kind: "btn-sm btn-ghost", "aria-label": `Dismiss: ${task.title}`, onclick: () => closeTask(task, "dismissed", reload) }));
}

export function taskList(main) {
  const params = query();
  const view = ["mine", "open", "unassigned", "closed"].includes(params.get("show")) ? params.get("show") : "mine";
  const filters = { mine: { mine: true }, open: {}, unassigned: { unassigned: true }, closed: { status: "all" } }[view];
  return show(main, {
    title: "Tasks",
    load: async () => (await get("/api/v1/tasks", filters, { fresh: true })).data,
    view: (rows, reload) => {
      const shown = view === "closed" ? rows.filter((task) => task.status !== "open") : rows;
      const tabs = [["mine", "Yours"], ["open", "Everything open"], ...(can("steward") || can("read_all") ? [["unassigned", "Nobody to do it"]] : []), ["closed", "Closed"]];
      return h("div", { class: "stack-lg" },
        pageHeader({ title: "Tasks", lede: "Raised by what happens: a contract's notice date near, a release reaching the end of its support, a grant ending, an owner leaving. Each closes by itself once its cause is settled." }),
        h("div", { class: "tabs", role: "tablist" }, tabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab",
          "aria-selected": String(view === key), onclick: () => setQuery({ show: key === "mine" ? null : key }, { replace: false }) }, text))),
        shown.length ? card({ flush: true }, h("ul", { class: "task-list" }, shown.map((task) => h("li", { class: "task-row" },
          h("div", { class: "grow stack-sm" },
            h("div", { class: "row-sm wrap" }, h("a", { class: "cell-main", href: `/tasks/${task.id}` }, task.title), taskPill(task)),
            h("div", { class: "cell-sub" }, `${task.kind_label} · due ${date(task.due_on)} · `,
              task.assignee ? `for ${task.assignee.name}` : h("span", { class: "text-danger" }, "nobody to do it")),
            task.status !== "open" ? h("div", { class: "cell-sub" }, `${task.closed_by}, ${date(task.closed_on)}: ${task.note ?? ""}`) : null),
          h("div", {}, task.about ? recordChip(task.about) : null),
          h("div", {}, task.status === "open" ? actions(task, reload) : null)))))
          : card({}, emptyState({ iconName: "check", title: view === "mine" ? "Nothing for you" : "Nothing here",
            text: "When a contract's notice date is near, a release you run on nears its end of support, a grant ends, or an owner leaves, the task is listed here." })));
    },
  });
}

export function taskPage(main, params) {
  return show(main, {
    title: "Task",
    narrow: true,
    load: async () => (await get(`/api/v1/tasks/${params.id}`, null, { fresh: true })).data,
    view: (task, reload) => h("div", { class: "stack-lg" },
      h("a", { class: "back-link", href: "/tasks" }, icon("chevron-left", "icon icon-sm"), "Tasks"),
      pageHeader({ eyebrow: task.kind_label, title: task.title, actions: task.status === "open" ? actions(task, reload) : null }),
      h("div", { class: "row-sm wrap" }, taskPill(task), h("span", { class: "muted" },
        `Due ${date(task.due_on)} · raised ${date(task.raised_on)} · `, task.assignee ? `for ${task.assignee.name}` : "nobody to do it")),
      card({ title: "Why" }, h("div", { class: "stack" }, h("p", {}, task.reason),
        task.about ? h("div", { class: "row-sm" }, recordChip(task.about), h("a", { class: "btn btn-sm", href: task.href }, "Open it")) : null)),
      task.status !== "open" ? card({ title: task.status === "done" ? "Done" : "Dismissed" },
        h("p", {}, `${task.closed_by}, ${date(task.closed_on)}: ${task.note ?? ""}`)) : null),
  });
}

// --- What a person holds -------------------------------------------------------------------

function passOn(personId, name, onDone) {
  openOverlay({ title: "Pass it all on", subtitle: `Everything ${name} holds`, kind: "dialog", render: (body, footer, close) => {
    const to = personField("To", { hint: "Each role on each record, each contract and interface, each open task, and each campaign item goes to them." });
    const problem = banner();
    const save = button("Pass it all on", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const chosen = to.value();
      const done = await submit({ button: save, banner: problem, fields: { to },
        run: () => post(`/api/v1/accounts/${personId}/hand-over`, { to: chosen ?? 0 }) });
      if (done) {
        close();
        const moved = Object.values(done.data.moved).reduce((sum, count) => sum + count, 0);
        toast(`Passed on ${plural(moved, "thing")}.`);
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem, to.node,
      h("p", { class: "subtle" }, "Assessments and decisions are not passed on: each stays the statement of whoever made it.")));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

export function holdingsPage(main, params) {
  return show(main, {
    title: "What they hold",
    load: async () => {
      const [person, held] = await Promise.all([get(`/api/v1/accounts/${params.id}`, null, { fresh: true }),
        get(`/api/v1/accounts/${params.id}/holdings`, null, { fresh: true })]);
      return { person: person.data, held: held.data };
    },
    view: ({ person, held }, reload) => {
      const mayPass = can("admin") || can("manage");
      const own = session().account.id === person.id;
      const table = (rows) => h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Record"), h("th", { scope: "col" }, "As"))),
        h("tbody", {}, rows.map((row) => h("tr", {}, h("td", {}, recordChip(row.record)), h("td", {}, row.role))))));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: own ? "You" : "People", title: `What ${own ? "you hold" : `${person.display_name} holds`}`,
          lede: "The records they are named on, the contracts and interfaces they own, their open tasks, and what campaigns still ask of them.",
          actions: mayPass && held.total ? button("Pass it all on", { kind: "btn-primary", onclick: () => passOn(person.id, person.display_name, reload) }) : null }),
        person.status === "disabled" && held.total ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, `${person.display_name} has left. `),
          "What they held is still theirs until it is passed on.")) : null,
        held.total ? null : card({}, emptyState({ iconName: "check", title: "Nothing held", text: "Nothing on record waits on this person." })),
        held.named.length ? card({ title: `Named on ${plural(held.named.length, "record")}`, flush: true }, table(held.named)) : null,
        held.owned.length ? card({ title: `Owns ${plural(held.owned.length, "record")}`, flush: true }, table(held.owned)) : null,
        held.tasks.length ? card({ title: plural(held.tasks.length, "open task") }, h("ul", { class: "plain-list" },
          held.tasks.map((task) => h("li", {}, h("a", { href: `/tasks/${task.id}` }, task.title), ` · due ${date(task.due_on)}`)))) : null,
        held.asked.length ? card({ title: `Asked by ${plural(held.asked.length, "campaign item")}` }, h("ul", { class: "plain-list" },
          held.asked.map((item) => h("li", {}, h("a", { href: `/campaigns/${item.campaign.ref}` }, item.campaign.name))))) : null);
    },
  });
}
