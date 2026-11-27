// The technology lifecycle: which releases fall out of support and when, with what runs on
// each; the radar of what is in use; and support dates brought in from a file.

import { get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { hrefOf, lifecyclePill, recordChip, supportPill } from "../components/record.js";
import { toast } from "../components/toast.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const DAY = 86400000;
const BEFORE = 365 * 2; // the timeline starts two years back
const AHEAD = 365 * 3; // and runs three years on
const VIEWS = [["", "In use"], ["ended", "Past end of support"], ["ending", "Ending within a year"], ["supported", "Supported"]];

/** Where a day falls on the timeline, as a share of its width, kept within it. */
function place(day, start) {
  const share = ((new Date(day) - start) / DAY) / (BEFORE + AHEAD);
  return Math.min(1, Math.max(0, share)) * 100;
}

function track(release, start, today) {
  const from = place(release.released_on ?? start, start);
  const to = release.support_ends ? place(release.support_ends, start) : 100;
  const bar = h("i", { class: "life-bar", "data-state": release.support });
  bar.style.setProperty("left", `${from}%`);
  bar.style.setProperty("width", `${Math.max(1, to - from)}%`);
  const more = release.extended_ends && release.support_ends ? h("i", { class: "life-bar life-extended" }) : null;
  if (more) {
    more.style.setProperty("left", `${to}%`);
    more.style.setProperty("width", `${Math.max(0, place(release.extended_ends, start) - to)}%`);
  }
  const now = h("i", { class: "life-today" });
  now.style.setProperty("left", `${place(today, start)}%`);
  return h("div", { class: "life-track", "aria-hidden": "true" }, bar, more, now);
}

export function lifecyclePage(main) {
  return show(main, {
    title: "Lifecycle",
    load: async () => {
      const every = query().get("every") === "true";
      const [found, vocab] = await Promise.all([get("/api/v1/lifecycle", every ? { every: "true" } : null, { fresh: true }), vocabularies()]);
      return { ...found.data, vocab };
    },
    view: (found) => {
      const which = query().get("support") ?? "";
      const every = query().get("every") === "true";
      const today = new Date(found.today);
      const start = new Date(today.getTime() - BEFORE * DAY);
      const rows = found.releases.filter((r) => !which || r.support === which || (which === "ended" && r.support === "extended"));
      const years = [-1, 0, 1, 2, 3].map((n) => today.getFullYear() + n);
      const counts = found.by_support;
      const picker = h("div", { class: "segmented wrap", role: "group", "aria-label": "Which releases" }, VIEWS.map(([key, text]) =>
        h("button", { type: "button", "aria-pressed": String(key === which), onclick: () => setQuery({ support: key || null }) },
          key ? `${text} (${(counts[key] ?? 0) + (key === "ended" ? (counts.extended ?? 0) : 0)})` : text)));
      const scale = h("div", { class: "life-row life-scale", "aria-hidden": "true" }, h("span", {}), h("div", { class: "life-track life-years" }, years.map((year) => {
        const mark = h("span", {}, String(year));
        mark.style.setProperty("left", `${place(`${year}-01-01`, start)}%`);
        return mark;
      })), h("span", {}));
      const list = rows.length ? h("div", { class: "life-list" }, scale, rows.map((r) => h("div", { class: "life-row" },
        h("div", { class: "life-name" }, h("a", { class: "cell-main", href: hrefOf(r.technology.ref) }, `${r.technology.name} ${r.cycle}`),
          h("div", { class: "cell-sub" }, r.components ? `${plural(r.components, "component")} in ${plural(r.applications, "application")}` : "Nothing runs on it")),
        track(r, start, found.today),
        h("div", { class: "life-end" }, supportPill(r.support),
          h("div", { class: "cell-sub" }, r.support_ends ? `${new Date(r.support_ends) < today ? "Ended" : "Ends"} ${date(r.support_ends)}` : "No end date recorded",
            r.extended_ends ? `; extended to ${date(r.extended_ends)}` : "")))))
        : h("p", { class: "muted" }, "No release matches.");
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Lifecycle",
          lede: "The technology releases applications run on, soonest end of support first, and how much is on each.",
          actions: [h("a", { class: "btn", href: "/technologies" }, "Technologies"), h("a", { class: "btn", href: "/radar" }, "Radar")] }),
        found.releases.length || every ? [
          h("div", { class: "row wrap" }, picker,
            button(every ? "Only releases in use" : "Every release on record", { kind: "btn-ghost", onclick: () => setQuery({ every: every ? null : "true" }) })),
          card({ title: plural(rows.length, "release") }, list,
            h("p", { class: "subtle life-key" }, "Each bar runs from a release's first day to the end of its support; a lighter stretch is extended support. The line is today.")),
        ] : card({}, emptyState({ iconName: "technology", title: "No release in use has support dates yet",
          text: "Record the release each component runs on, and each release's end of support, on the technology's page; or bring the dates in from a file." })),
        card({ title: found.retiring.length ? `${plural(found.retiring.length, "application has", "applications have")} a planned retirement` : "Planned retirements", flush: found.retiring.length > 0 },
          found.retiring.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Application"), h("th", { scope: "col" }, "Stage"), h("th", { scope: "col" }, "Planned retirement"))),
            h("tbody", {}, found.retiring.map((app) => h("tr", {}, h("td", {}, recordChip(app)), h("td", {}, lifecyclePill(found.vocab, app.lifecycle)),
              h("td", { class: "nowrap" }, date(app.retire_planned)))))))
            : h("p", { class: "muted" }, "No application in service has a planned retirement date.")));
    },
  });
}

export function radarPage(main) {
  return show(main, {
    title: "Radar",
    load: async () => {
      const [found, vocab] = await Promise.all([get("/api/v1/radar", null, { fresh: true }), vocabularies()]);
      return { found: found.data, vocab };
    },
    view: ({ found, vocab }) => {
      const listed = (items) => (items.length ? h("ul", { class: "radar-list" }, items.map((t) => h("li", {},
        h("a", { class: "cell-main", href: hrefOf(t.ref) }, t.name),
        h("span", { class: "cell-sub" }, `${label(vocab, "technology_kinds", t.kind)} · ${t.components ? plural(t.components, "component") : "not in use"}`))))
        : h("p", { class: "muted" }, "Nothing here."));
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Landscape", title: "Radar",
          lede: "The organization's view of each technology for new work, and how much already runs on it.",
          actions: [h("a", { class: "btn", href: "/technologies" }, "Technologies"), h("a", { class: "btn", href: "/lifecycle" }, "Lifecycle")] }),
        h("div", { class: "radar" }, found.rings.map((ring) => card({ title: `${ring.label} (${ring.technologies.length})` },
          ring.description ? h("p", { class: "subtle" }, ring.description) : null, listed(ring.technologies)))),
        found.unplaced.length ? card({ title: `In use, with no ring: ${found.unplaced.length}` },
          h("p", { class: "muted" }, "Components run on these, and nobody has said whether new work should."), listed(found.unplaced)) : null,
        found.unused ? h("p", { class: "subtle" }, `${plural(found.unused, "technology is", "technologies are")} on record with no ring and nothing running on ${found.unused === 1 ? "it" : "them"}.`) : null);
    },
  });
}

/** Bring releases and support dates in from a file: check it, read what would change, then apply. */
export function importSupportDates(onDone) {
  if (!can("architect")) return;
  openOverlay({
    title: "Support dates from a file",
    subtitle: "Releases are added and dates updated. Nothing is removed.",
    render: (body, footer, close) => {
      const file = h("input", { type: "file", class: "input", accept: ".json,application/json", "aria-label": "End-of-life file" });
      const problem = banner();
      const said = h("div", { class: "stack", role: "status" });
      let data = null;
      const check = button("Check the file", { kind: "btn-primary" });
      const apply = button("Import", { kind: "btn-primary", hidden: true });
      const run = async (dry, node) => {
        if (dry) {
          try {
            data = file.files[0] ? JSON.parse(await file.files[0].text()) : null;
          } catch {
            data = undefined;
          }
          if (data == null) {
            problem.textContent = data === undefined ? "That file is not JSON." : "Choose a file first.";
            problem.hidden = false;
            return null;
          }
        }
        return submit({ button: node, banner: problem, run: () => post(`/api/v1/imports/end-of-life?dry_run=${dry}`, data) });
      };
      const report = (r, dry) => {
        const would = dry ? "would be " : "";
        said.replaceChildren(
          h("p", { class: "cell-main" }, `${plural(r.matched.length, "technology", "technologies")} matched: ${plural(r.added.length, "release")} ${would}added, ${plural(r.changed.length, "date")} ${would}changed.`),
          r.changed.length ? h("ul", { class: "bullets" }, r.changed.slice(0, 40).map((c) => h("li", {},
            `${c.technology} ${c.cycle}: ${c.field.replace(/_/g, " ")} ${c.from ? date(c.from) : "not set"} → ${date(c.to)}`))) : null,
          r.problems.length ? h("ul", { class: "bullets" }, r.problems.map((text) => h("li", {}, `Skipped: ${text}`))) : null,
          r.without_key ? h("p", { class: "subtle" }, `${plural(r.without_key, "technology has", "technologies have")} no end-of-life key, so no file can match ${r.without_key === 1 ? "it" : "them"}. Set the key on the technology.`) : null,
          r.unmatched.length ? h("p", { class: "subtle" }, `${plural(r.unmatched.length, "product")} in the file ${r.unmatched.length === 1 ? "matches" : "match"} no technology here.`) : null);
      };
      check.addEventListener("click", async () => {
        const done = await run(true, check);
        if (!done) return;
        report(done.data, true);
        apply.hidden = !(done.data.added.length || done.data.changed.length);
      });
      apply.addEventListener("click", async () => {
        const done = await run(false, apply);
        if (!done) return;
        close();
        toast(`${plural(done.data.added.length, "release")} added, ${plural(done.data.changed.length, "date")} changed.`);
        onDone?.();
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "A JSON file of end-of-life data: each product's key, with its list of releases and the dates their support ends. A product is matched to the technology whose end-of-life key it is. AppWren does not fetch the file; you bring it."),
        h("div", { class: "field" }, file), said));
      footer.replaceChildren(h("div", { class: "row" }, check, apply, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}
