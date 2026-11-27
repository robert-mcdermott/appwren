// Decisions across the portfolio, mismatches with today's recommendations, and the
// portfolio snapshots kept for reviews.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, field, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { hrefOf } from "../components/record.js";
import { toast } from "../components/toast.js";
import { card, dispositionBadge, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const VIEWS = [["", "All decisions"], ["mismatch", "Mismatches"], ["review_due", "Due for review"], ["undecided", "No decision yet"]];

export function decisionList(main) {
  return show(main, {
    title: "Decisions",
    load: async () => {
      const which = query().get("show") ?? "";
      const params = which === "mismatch" ? { mismatch: true } : which === "review_due" ? { review_due: true }
        : which === "undecided" ? { decided: false } : { decided: true };
      const [page, vocab] = await Promise.all([get("/api/v1/portfolio", params, { fresh: true }), vocabularies()]);
      return { rows: page.data.filter((r) => !["retired", "archived"].includes(r.lifecycle) || r.decision), vocab, which };
    },
    view: (data) => {
      const { vocab } = data;
      const tabs = h("div", { class: "segmented", role: "group", "aria-label": "Which decisions" },
        VIEWS.map(([key, text]) => h("button", { type: "button", "aria-pressed": String(data.which === key), onclick: () => setQuery({ show: key || null }) }, text)));
      const rows = data.rows;
      const body = rows.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, ["Application", "Recommended", "Decided", "Review", "Confidence"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", {}, rows.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `${hrefOf(r.ref)}?tab=decisions` }, r.name), h("div", { class: "cell-sub" }, [r.ref, r.accountable.join(", ")].filter(Boolean).join(" · "))),
          h("td", {}, r.recommendation ? dispositionBadge(r.recommendation, label(vocab, "dispositions", r.recommendation)) : "—"),
          h("td", {}, r.decision ? dispositionBadge(r.decision, label(vocab, "dispositions", r.decision), { decided: true }) : h("span", { class: "subtle" }, "None"),
            r.self_decided ? h("div", { class: "cell-sub" }, "Recorded by its own owner") : null,
            r.mismatch ? h("div", {}, pill("Mismatch", "info")) : null),
          h("td", { class: "nowrap" }, r.review_on ? date(r.review_on) : "—", r.review_on && r.review_on < new Date().toISOString().slice(0, 10) ? h("div", {}, pill("Due", "warn")) : null),
          h("td", { class: "numeric" }, `${r.confidence}%`))))))
        : emptyState({ iconName: "decision", title: "Nothing here", text: "A decision records what to do with an application, by whom, and why. Open an application to record one." });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Portfolio", title: "Decisions",
          lede: "What people decided to do with each application, beside what the scores recommend today. A mismatch is a prompt for the next review, not an error.",
          actions: h("a", { class: "btn", href: "/snapshots" }, "Snapshots") }),
        tabs,
        card({ title: plural(rows.length, "application"), flush: rows.length > 0 }, body));
    },
  });
}

function takeSnapshot(onDone) {
  openOverlay({
    title: "Take a portfolio snapshot",
    subtitle: "Keep every active application's scores together, as they are now",
    kind: "dialog",
    render: (body, footer, close) => {
      const name = field("Name", { required: true, placeholder: "2026 Q4 review" });
      const problem = banner();
      const save = button("Take the snapshot", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem, fields: { name },
          run: () => post("/api/v1/portfolio-snapshots", { name: name.input.value }) });
        if (done) {
          close();
          toast(`${done.data.ref} was taken.`);
          onDone();
        }
      });
      body.append(h("div", { class: "stack" }, problem, name.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function snapshotList(main) {
  return show(main, {
    title: "Portfolio snapshots",
    load: async () => (await get("/api/v1/portfolio-snapshots", null, { fresh: true })).data,
    view: (rows, reload) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Portfolio", title: "Portfolio snapshots",
        lede: "Every application's scores kept together at a moment, for a review or the end of a period. A snapshot reopens unchanged, whatever changes later.",
        actions: can("manage") ? button("Take a snapshot", { kind: "btn-primary", iconName: "plus", onclick: () => takeSnapshot(reload) }) : null }),
      card({ title: plural(rows.length, "snapshot"), flush: rows.length > 0 }, rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Snapshot", "Taken", "By", "Applications"].map((t) => h("th", { scope: "col" }, t)))),
          h("tbody", {}, rows.map((r) => h("tr", {}, h("td", {}, h("a", { class: "cell-main", href: `/snapshots/${r.ref}` }, r.name), h("div", { class: "cell-sub" }, r.ref)),
            h("td", {}, date(r.taken_at)), h("td", {}, r.taken_by), h("td", { class: "numeric" }, String(r.count)))))))
        : h("p", { class: "muted" }, "None yet."))),
  });
}

export function snapshotPage(main, params) {
  return show(main, {
    title: params.ref,
    load: async () => {
      const [snap, vocab] = await Promise.all([get(`/api/v1/portfolio-snapshots/${params.ref}`), vocabularies()]);
      return { snap: snap.data, vocab };
    },
    view: ({ snap, vocab }) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: `Portfolio snapshot · ${snap.ref}`, title: snap.name, lede: `Taken ${date(snap.taken_at)} by ${snap.taken_by}: ${plural(snap.count, "application")}.` }),
      card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, ["Application", "Value", "Health", "Cost", "Risk", "Confidence", "Recommended"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", {}, snap.rows.map((r) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name), h("div", { class: "cell-sub" }, r.ref)),
          ["business_value", "technical_health", "cost_burden", "risk_exposure"].map((k) => h("td", { class: "numeric" }, r.scores[k] == null ? "—" : r.scores[k].toFixed(1))),
          h("td", { class: "numeric" }, `${r.confidence}%`),
          h("td", {}, r.recommendation ? dispositionBadge(r.recommendation, label(vocab, "dispositions", r.recommendation)) : "—")))))))),
  });
}
