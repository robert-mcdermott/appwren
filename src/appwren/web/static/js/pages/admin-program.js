// Admin → Program: the lists, the organization's own fields, the wording of the questions, and
// the scoring model with its cadence. A changed model is previewed before it is published:
// every application whose scores, recommendation, or flags would differ is listed.

import { post, put, get } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural, titleCase } from "../core/format.js";
import { query } from "../core/router.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { recordChip } from "../components/record.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { tabBar } from "./record.js";

const TABS = [["lists", "Lists"], ["fields", "Fields"], ["questions", "Questions"], ["scoring", "Scoring and cadence"], ["decisions", "Decisions"]];
const words = (key) => titleCase(String(key).replace(/_/g, " "));
const numberInput = (value, label, attrs = {}) => h("input", { class: "input input-number", type: "number", value: value ?? "", "aria-label": label, ...attrs });

// --- Lists --------------------------------------------------------------------------------

function listsTab(program, reload) {
  const names = Object.keys(program.vocabularies).sort();
  const wanted = query().get("list");
  const chosen = select("List", names.map((name) => [name, words(name)]), { value: names.includes(wanted) ? wanted : names[0] });
  const holder = h("div", {});
  const draw = () => {
    const name = chosen.input.value;
    const fixed = program.fixed.includes(name);
    const rows = program.vocabularies[name].map((item) => ({ ...item }));
    const problem = banner();
    const table = h("tbody", {});
    const paint = () => {
      table.replaceChildren(...rows.map((item, index) => {
        const label = h("input", { class: "input", value: item.label, "aria-label": `Label of ${item.key || "the new value"}`,
          oninput: (event) => { item.label = event.target.value; } });
        const description = h("input", { class: "input", value: item.description ?? "", "aria-label": `Description of ${item.label}`,
          oninput: (event) => { item.description = event.target.value || undefined; } });
        const move = (by) => () => {
          const to = index + by;
          if (to < 0 || to >= rows.length) return;
          [rows[index], rows[to]] = [rows[to], rows[index]];
          paint();
        };
        const retired = fixed ? null : h("input", { type: "checkbox", class: "table-check", checked: Boolean(item.retired), "aria-label": `Retire ${item.label}`,
          onchange: (event) => { item.retired = event.target.checked || undefined; } });
        return h("tr", {},
          h("td", { class: "mono subtle" }, item.key || "new"),
          h("td", {}, label), h("td", {}, description),
          h("td", { class: "row-sm" }, button("Up", { kind: "btn-sm btn-ghost", "aria-label": `Move ${item.label} up`, onclick: move(-1), disabled: index === 0 }),
            button("Down", { kind: "btn-sm btn-ghost", "aria-label": `Move ${item.label} down`, onclick: move(1), disabled: index === rows.length - 1 })),
          fixed ? null : h("td", {}, retired));
      }));
    };
    paint();
    const save = button("Save the list", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: {},
        run: () => put(`/api/v1/program/vocabularies/${name}`, { items: rows.map(({ key, ...rest }) => ({ key: key ?? "", ...rest })) }) });
      if (done) {
        toast(`${words(name)} was saved.`);
        reload();
      }
    });
    holder.replaceChildren(card({ title: words(name), flush: true,
      footer: h("div", { class: "row" }, save, fixed ? null : button("Add a value", { onclick: () => {
        rows.push({ key: "", label: "" });
        paint();
        table.lastElementChild?.querySelector("input")?.focus();
      } })) },
    h("div", { class: "pad stack-sm" }, problem, h("p", { class: "muted" }, fixed
      ? "AppWren's own rules read these values by key, so they can be renamed, described, and reordered, but not added to or retired."
      : "Records keep a value's key, so renaming it changes nothing on record. A value in use is retired rather than removed: it stays on the records that have it and is no longer offered.")),
    h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Key"), h("th", { scope: "col" }, "Label"), h("th", { scope: "col" }, "Description"),
        h("th", { scope: "col" }, "Order"), fixed ? null : h("th", { scope: "col" }, "Retired"))), table))));
  };
  chosen.input.addEventListener("change", draw);
  draw();
  return h("div", { class: "stack-lg" }, h("div", { class: "narrow-field" }, chosen.node), holder);
}

// --- Fields -------------------------------------------------------------------------------

function editField(program, index, reload) {
  const all = program.fields.map((item) => ({ ...item }));
  const item = index == null ? { key: "", label: "", type: "text", section: "about" } : all[index];
  openOverlay({ title: index == null ? "Add a field" : `Edit ${item.label}`, render: (body, footer, close) => {
    const key = field("Key", { value: item.key, disabled: index != null, hint: "Lower-case letters, digits, and underscores. Fixed once made: records keep it." });
    const label = field("Label", { value: item.label, required: true });
    const type = select("Kind", program.field_types.map((each) => [each, words(each)]), { value: item.type });
    const section = select("Section", program.sections.map((each) => [each, words(each)]), { value: item.section ?? "about" });
    const help = field("Help", { value: item.help ?? "", hint: "Shown beneath it on the form." });
    const options = field("Choices", { type: "textarea", rows: 4, value: (item.options ?? []).map(([k, v]) => `${k}: ${v}`).join("\n"),
      hint: "One a line, as key: label. For a choice only." });
    const sensitive = checkbox("Sensitive", { checked: program.sensitive_fields.includes(item.key),
      hint: "Shown only to the people named on an application and those with a role over its unit." });
    const sync = () => { options.node.hidden = type.input.value !== "choice"; };
    type.input.addEventListener("change", sync);
    sync();
    const problem = banner();
    const save = button("Save", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const made = { ...item, key: key.input.value.trim(), label: label.input.value, type: type.input.value, section: section.input.value,
        help: help.input.value || undefined };
      if (made.type === "choice") {
        made.options = options.input.value.split("\n").map((line) => line.trim()).filter(Boolean)
          .map((line) => { const [k, ...rest] = line.split(":"); return [k.trim(), (rest.join(":").trim() || k.trim())]; });
      } else delete made.options;
      if (index == null) all.push(made); else all[index] = made;
      const marked = new Set(program.sensitive_fields.filter((name) => name !== item.key));
      if (sensitive.input.checked) marked.add(made.key);
      const done = await submit({ button: save, banner: problem, fields: { fields: label },
        run: () => put("/api/v1/program/fields", { fields: all, sensitive_fields: [...marked] }) });
      if (done) {
        close();
        toast(`${made.label} was saved.`);
        reload();
      } else if (index == null) all.pop();
    });
    body.append(h("div", { class: "stack" }, problem, key.node, label.node, type.node, section.node, help.node, options.node, sensitive.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function fieldsTab(program, reload) {
  return card({ title: "The organization's own fields", flush: true,
    actions: button("Add a field", { kind: "btn-sm btn-primary", iconName: "plus", onclick: () => editField(program, null, reload) }) },
  h("p", { class: "muted pad" }, "Fields an application carries beyond AppWren's own, in the section of its form they belong to. A field that holds values is kept; its label, help, and section may change."),
  program.fields.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Field"), h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "Section"),
      h("th", { scope: "col" }, "Sensitive"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Edit")))),
    h("tbody", {}, program.fields.map((item, index) => h("tr", {},
      h("td", {}, h("span", { class: "cell-main" }, item.label), h("div", { class: "cell-sub mono" }, item.key)),
      h("td", {}, words(item.type)), h("td", {}, words(item.section ?? "about")),
      h("td", {}, program.sensitive_fields.includes(item.key) ? "Yes" : ""),
      h("td", {}, button("Edit", { kind: "btn-sm btn-ghost", "aria-label": `Edit ${item.label}`, onclick: () => editField(program, index, reload) })))))))
    : h("p", { class: "muted pad" }, "None yet."));
}

// --- Questions ----------------------------------------------------------------------------

function questionsTab(program, reload) {
  const bank = structuredClone(program.questionnaire.definition);
  const problem = banner();
  const save = button("Publish the wording", { kind: "btn-primary" });
  save.addEventListener("click", async () => {
    const done = await submit({ button: save, banner: problem, fields: {}, run: () => put("/api/v1/program/questionnaire", { definition: bank }) });
    if (done) {
      toast(done.data.changed ? `Version ${done.data.version} of the questions is published.` : "Nothing had changed.");
      reload();
    }
  });
  const text = (object, key, label, attrs = {}) => h("input", { class: "input", value: object[key] ?? "", "aria-label": label, ...attrs,
    oninput: (event) => { object[key] = event.target.value; } });
  return h("div", { class: "stack-lg" },
    alert("info", icon("info"), h("div", {}, `Version ${program.questionnaire.version}. Publishing makes a new version; every assessment keeps the version it answered. Adding or removing a question, or moving it to another score, is done with a program pack, together with the scoring model.`)),
    problem,
    bank.sections.map((section) => card({ title: section.title }, h("div", { class: "stack-lg" }, section.questions.map((question) => h("fieldset", { class: "fieldset" },
      h("legend", {}, `${words(question.key)} · ${words(question.dimension)}`),
      text(question, "text", `The question: ${question.key}`),
      text(question, "help", `Help for ${question.key}`, { placeholder: "Help" }),
      h("ol", { class: "levels-edit" }, question.levels.map((_, level) => h("li", {},
        h("input", { class: "input", value: question.levels[level], "aria-label": `Level ${level + 1} of ${question.key}`,
          oninput: (event) => { question.levels[level] = event.target.value; } }))))))))),
    h("div", {}, save));
}

// --- Scoring and cadence ------------------------------------------------------------------

function scoringTab(program, reload) {
  const model = structuredClone(program.scoring.definition);
  const standard = model.profiles.find((profile) => profile.key === "standard");
  const others = model.profiles.filter((profile) => profile.key !== "standard");
  const problem = banner();
  const preview = h("div", { "aria-live": "polite" });
  const sums = [];
  const resolved = (profile, dimension, factor) => (profile === standard ? factor.weight
    : profile.weights?.[dimension]?.[factor.key] ?? factor.weight);
  const setWeight = (profile, dimension, factor, value) => {
    if (profile === standard) {
      factor.weight = value;
      return;
    }
    profile.weights ??= {};
    profile.weights[dimension] ??= {};
    if (value === factor.weight) delete profile.weights[dimension][factor.key];
    else profile.weights[dimension][factor.key] = value;
    if (!Object.keys(profile.weights[dimension]).length) delete profile.weights[dimension];
  };
  const recount = () => sums.forEach((paint) => paint());
  const weights = model.dimensions.map((dimension) => {
    const factors = standard.factors[dimension.key];
    const columns = [standard, ...others];
    const sumCells = columns.map((profile) => {
      const cell = h("td", { class: "nowrap" });
      sums.push(() => {
        // A signal comes on top: it counts only where a source supplies it.
        const total = factors.filter((factor) => factor.kind !== "signal")
          .reduce((sum, factor) => sum + Number(resolved(profile, dimension.key, factor) || 0), 0);
        cell.textContent = `${total}`;
        cell.dataset.wrong = String(total !== 100);
      });
      return cell;
    });
    return card({ title: dimension.label, flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Factor"), columns.map((profile) => h("th", { scope: "col" }, profile.label)))),
      h("tbody", {}, factors.map((factor) => h("tr", {}, h("td", {}, factor.label,
        factor.kind === "signal" ? h("span", { class: "cell-sub" }, " · a signal, on top") : null),
        columns.map((profile) => h("td", {}, numberInput(resolved(profile, dimension.key, factor), `${factor.label}, ${profile.label}`, { min: 0, max: 100,
          oninput: (event) => {
            setWeight(profile, dimension.key, factor, Number(event.target.value || 0));
            recount();
          } }))))),
      h("tr", { class: "sum-row" }, h("th", { scope: "row" }, factors.some((factor) => factor.kind === "signal")
        ? "Adds up to, without the signals (must be 100)" : "Adds up to (must be 100)"), sumCells)))));
  });
  recount();
  const cadence = model.cadence ?? (model.cadence = {});
  const tiers = ["1", "2", "3", "4", "5"];
  const byTier = (key, label) => {
    cadence[key] ??= {};
    return h("tr", {}, h("th", { scope: "row" }, label), tiers.map((tier) => h("td", {},
      numberInput(cadence[key][tier], `${label}, tier ${tier}`, { min: 1, max: 60, oninput: (event) => { cadence[key][tier] = Number(event.target.value); } }))));
  };
  const one = (object, key, label, hint, step = "1") => field(label, { type: "number", step, value: object[key] ?? "", hint,
    oninput: (event) => { object[key] = Number(event.target.value); } }).node;
  cadence.reminders ??= {};
  cadence.triggers ??= {};
  const thresholds = model.thresholds;
  const check = button("See what it would change", { kind: "btn-primary" });
  const publish = button("Publish", { disabled: true });
  check.addEventListener("click", async () => {
    const done = await submit({ button: check, banner: problem, fields: {}, run: () => post("/api/v1/program/scoring/preview", { definition: model }) });
    if (!done) return;
    const found = done.data;
    publish.disabled = found.same;
    preview.replaceChildren(found.same ? alert("info", icon("info"), h("div", {}, "This is the model as it stands: nothing to publish."))
      : card({ title: found.count ? `It would change ${plural(found.count, "application")}` : "It would change no application's scores" },
        found.count ? h("ul", { class: "found-list" }, found.changed.map((item) => h("li", {}, recordChip(item.application),
          h("span", { class: "cell-sub" }, item.changes.map((change) => `${words(change.what)}: ${Array.isArray(change.from) ? change.from.join(", ") || "none" : change.from ?? "none"} → ${Array.isArray(change.to) ? change.to.join(", ") || "none" : change.to ?? "none"}`).join("; ")))))
          : h("p", { class: "muted" }, "Publishing it makes a new version all the same; later assessments and snapshots will name it.")));
  });
  publish.addEventListener("click", async () => {
    const done = await submit({ button: publish, banner: problem, fields: {}, run: () => put("/api/v1/program/scoring", { definition: model }) });
    if (done) {
      toast(`Version ${done.data.version} of the scoring model is published; it changed ${plural(done.data.count, "application")}.`);
      reload();
    }
  });
  return h("div", { class: "stack-lg" },
    alert("info", icon("info"), h("div", {}, `Version ${program.scoring.version}, published by ${program.scoring.published_by}. A change is previewed, then published as a new version: every score says which version it was worked out under, and a decision keeps the scores it saw. The rules, guardrails, and flags are changed with a program pack.`)),
    problem,
    card({ title: "Thresholds" }, h("div", { class: "grid-3" },
      one(thresholds, "value", "Valuable from", "Business value, 1 to 5.", "0.1"), one(thresholds, "health", "Healthy from", "Technical health, 1 to 5.", "0.1"),
      one(thresholds, "cost", "Affordable from", "Cost and burden, 1 to 5.", "0.1"), one(thresholds, "confidence", "Enough is known from", "Data confidence, %."),
      one(thresholds, "thin", "A score is thin below", "Coverage, %."))),
    weights,
    card({ title: "Cadence", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Months, by tier"), tiers.map((tier) => h("th", { scope: "col" }, `Tier ${tier}`)))),
      h("tbody", {}, byTier("assessment_months", "An assessment stays current"), byTier("confirm_months", "A record is confirmed every")))),
    h("div", { class: "pad grid-3" },
      one(cadence, "stale_penalty", "A stale record loses", "Points of confidence, 0 to 50."),
      one(cadence.reminders, "soon_days", "Remind this many days ahead", null),
      one(cadence.reminders, "steward_after_days", "Then the steward, days late", null),
      one(cadence.reminders, "leader_after_days", "Then the leader, days late", null),
      one(cadence.triggers, "contract_notice_days", "Task before a notice date, days", null),
      one(cadence.triggers, "end_of_support_days", "Task before end of support, days", null),
      one(cadence.triggers, "grant_end_days", "Task before a grant ends, days", null))),
    h("div", { class: "row" }, check, publish),
    preview);
}

// --- Who may decide -----------------------------------------------------------------------

function decisionsTab(program, reload) {
  const allowed = checkbox("Let an application's accountable owner record its decision", {
    checked: program.decision_rules.owners_may_decide,
    hint: "Only where they are also a manager, or a leader over its unit. For a team too small for anyone else to decide. Each such decision is marked as recorded by its own owner, on the decision, in the history, and on the Decisions page." });
  const problem = banner();
  const save = button("Save", { kind: "btn-primary" });
  save.addEventListener("click", async () => {
    const done = await submit({ button: save, banner: problem, fields: {},
      run: () => put("/api/v1/program/decision-rules", { owners_may_decide: allowed.input.checked }) });
    if (done) {
      toast(done.data.owners_may_decide ? "Owners may now record their own applications' decisions." : "Someone other than the owner records each decision.");
      reload();
    }
  });
  return card({ title: "Who records a decision", footer: h("div", { class: "row" }, save) }, h("div", { class: "stack" }, problem,
    h("p", {}, "A decision says what the organization will do with an application. A manager records it, or a leader of the application's unit. By default, never the application's own accountable owner: nobody pronounces on their own system."),
    allowed.node));
}

export function adminProgram(main) {
  const wanted = query().get("tab");
  const tab = TABS.some(([key]) => key === wanted) ? wanted : "lists";
  return show(main, {
    title: "Program",
    load: async () => (await get("/api/v1/program", null, { fresh: true })).data,
    view: (program, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Admin", title: "Program", lede: "What the portfolio is judged by: the lists people choose from, the fields they fill in, the questions assessors answer, and the model that turns it all into scores. Every change is in the history." }),
      tabBar(TABS, tab),
      tab === "fields" ? fieldsTab(program, reload)
        : tab === "questions" ? questionsTab(program, reload)
          : tab === "scoring" ? scoringTab(program, reload)
            : tab === "decisions" ? decisionsTab(program, reload)
            : listsTab(program, reload)),
  });
}
