// Answer the assessment for an application: each question a row of defined levels, and the
// scores that would result beside the form, worked out by the same engine as the record.

import { get, post } from "../core/api.js";
import { button, h, uid } from "../core/dom.js";
import { navigate } from "../core/router.js";
import { vocabularies } from "../core/lookups.js";
import { banner, field, submit } from "../components/form.js";
import { recordChip } from "../components/record.js";
import { scorecard, verdict } from "../components/scorecard.js";
import { toast } from "../components/toast.js";
import { card, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const VENDOR_SOURCED = ["saas", "commercial", "vendor_custom"];

/** Whether a question applies to this application. The only condition the default bank
 * uses is whether the application is vendor sourced; others always apply here. */
function applies(question, app) {
  const when = question.applies;
  if (!when) return true;
  if (when.field === "vendor_sourced") return VENDOR_SOURCED.includes(app.sourcing) === when.value;
  return true;
}

function levelPicker(question, chosen, onChange) {
  const name = uid(question.key);
  const about = h("p", { class: "level-about", "aria-live": "polite" });
  const describe = (value) => {
    about.textContent = value == null ? "Don't know: this answer will count as unknown." : question.levels[value - 1] ?? "";
  };
  const choice = (value, text) => {
    const input = h("input", { type: "radio", name, value: String(value ?? "unknown"), checked: chosen === value,
      "aria-label": value == null ? "Don't know" : `${value}: ${question.levels[value - 1]}`,
      onchange: () => {
        describe(value);
        onChange(value);
      },
      onfocus: () => describe(value) });
    return h("label", { class: "level" }, input, h("span", {}, text));
  };
  describe(chosen === undefined ? undefined : chosen);
  if (chosen === undefined) about.textContent = "Choose a level. Each one says what it means.";
  return h("fieldset", { class: "level-picker" },
    h("legend", { class: "cell-main" }, question.text),
    question.help ? h("p", { class: "hint subtle" }, question.help) : null,
    h("div", { class: "levels" },
      [1, 2, 3, 4, 5].map((value) => choice(value, h("b", {}, String(value)))),
      choice(null, "Don't know")),
    about);
}

export function assess(main, params) {
  return show(main, {
    title: `Assess ${params.ref}`,
    load: async () => {
      const [app, bank, past, scores, vocab] = await Promise.all([
        get(`/api/v1/applications/${params.ref}`, null, { fresh: true }),
        get("/api/v1/questionnaire"),
        get(`/api/v1/applications/${params.ref}/assessments`, null, { fresh: true }),
        get(`/api/v1/applications/${params.ref}/scores`, null, { fresh: true }),
        vocabularies()]);
      return { app: app.data, bank: bank.data, past: past.data.find((a) => !a.superseded) ?? null, scores: scores.data, vocab };
    },
    view: (data) => {
      const { app, bank, vocab } = data;
      const answers = {};
      const notes = {};
      for (const [key, item] of Object.entries(data.past?.answers ?? {})) {
        answers[key] = item.level;
        notes[key] = item.note ?? "";
      }
      const live = h("div", { class: "stack" });
      const drawLive = (result) => live.replaceChildren(
        scorecard(result, { onOpen: () => {} }), verdict(result, vocab));
      drawLive(data.scores);
      let timer = null;
      let latest = 0;
      const refresh = () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
          const mine = ++latest;
          try {
            const result = (await post(`/api/v1/applications/${app.ref}/score-preview`, { answers: payload() })).data;
            if (mine === latest) drawLive(result);
          } catch {
            // The preview is a convenience; saving reports any problem.
          }
        }, 250);
      };
      const payload = () => Object.fromEntries(Object.entries(answers).map(([key, level]) =>
        [key, { level, note: notes[key] || null }]));
      const sections = bank.sections.map((section) => card({ title: section.title },
        h("div", { class: "stack-lg" }, section.questions.filter((q) => applies(q, app)).map((question) => {
          const note = h("textarea", { class: "textarea", rows: 2, "aria-label": `Note on: ${question.text}`, placeholder: "A note, if it helps the next person",
            oninput: (event) => {
              notes[question.key] = event.target.value;
            } });
          note.value = notes[question.key] ?? "";
          return h("div", { class: "stack-sm" },
            levelPicker(question, answers[question.key], (value) => {
              answers[question.key] = value;
              refresh();
            }),
            h("details", { class: "disclosure", open: notes[question.key] ? "" : null }, h("summary", {}, "Add a note"), note));
        }))));
      const overall = field("A note on the whole assessment", { type: "textarea", rows: 2, value: "" });
      const problem = banner();
      const save = button("Save the assessment", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => post(`/api/v1/applications/${app.ref}/assessments`, { answers: payload(), note: overall.input.value || null }) });
        if (done) {
          toast(`${done.data.assessment.ref} was saved.`);
          navigate(`/applications/${app.ref}?tab=scores`);
        }
      });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Assessment", title: `Assess ${app.name}`,
          lede: data.past ? "The last answers are filled in. Change what is no longer true, and save: the new assessment takes over from the old." : "Answer what you can. Don't know is always an answer: it counts as unknown, never as a guess.",
          actions: recordChip(app) }),
        h("div", { class: "assess-layout" },
          h("div", { class: "stack-lg" }, problem, sections, card({}, overall.node),
            h("div", { class: "form-actions" }, save, h("a", { class: "btn btn-ghost", href: `/applications/${app.ref}` }, "Cancel"))),
          h("aside", { class: "assess-live", "aria-label": "What the scores would be" },
            card({ title: "What the scores would be" }, live,
              h("p", { class: "subtle" }, "Worked out as you answer, by the same rules as the record. Nothing is saved until you save.")))));
    },
  });
}
