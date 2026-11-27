// The dashboard: where the portfolio stands. Every figure opens the applications it counts.

import { get } from "../core/api.js";
import { h } from "../core/dom.js";
import { options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { bars, listHref, sizeBars, statTile } from "../components/charts.js";
import { card, dispositionBadge, emptyState, flag, pageHeader } from "../components/ui.js";
import { show } from "./page.js";
import { filterSelect } from "./records.js";

const TONES = { Mismatches: "", "Reviews due": "warn", "Low confidence": "warn", "Past end of support": "danger", "Support ending within a year": "warn" };

export function dashboard(main) {
  return show(main, {
    title: "Dashboard",
    load: async () => {
      const [board, vocab, unitIndex] = await Promise.all([
        get("/api/v1/dashboard", Object.fromEntries(query()), { fresh: true }), vocabularies(), units()]);
      return { board: board.data, vocab, units: unitIndex };
    },
    view: ({ board, vocab, units: unitIndex }) => {
      const link = (figure) => listHref("/list", figure.filters);
      const bar = h("div", { class: "filters" },
        filterSelect("unit", unitOptions(unitIndex.tree, { blank: "The whole organization" }), "Unit"),
        filterSelect("domain", options(vocab, "domains", { blank: "Every domain" }), "Domain"));
      if (!board.total.count) {
        return h("div", { class: "stack-lg" }, pageHeader({ eyebrow: "Reports", title: "Dashboard" }), bar,
          card({}, emptyState({ iconName: "dashboard", title: "Nothing to report yet", text: "Once applications are recorded and assessed, this page shows where the portfolio stands." })));
      }
      const tiles = h("div", { class: "tiles" },
        statTile({ value: board.total.count, label: "Applications in service", href: link(board.total) }),
        board.headline.map((figure) => statTile({ value: figure.count, label: figure.label, href: link(figure), tone: TONES[figure.label] ?? "" })));
      const dispositions = (items, decided) => bars(items.map((figure) => ({
        label: figure.label, value: figure.count, href: link(figure),
        badge: figure.key && figure.key !== "none" ? dispositionBadge(figure.key, figure.label, { decided }) : figure.label })));
      const plain = (items) => bars(items.map((figure) => ({ label: figure.label, value: figure.count, href: link(figure) })));
      const body = h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Dashboard",
          lede: "Where the portfolio stands. Every figure opens the applications it counts." }),
        bar, tiles,
        h("div", { class: "split" },
          card({ title: "What the scores recommend" }, dispositions(board.recommendations, false)),
          card({ title: "What has been decided" }, dispositions(board.decisions, true))),
        h("div", { class: "split" },
          card({ title: "Flags" }, board.flags.length ? h("ul", { class: "stack-sm" }, board.flags.map((figure) =>
            h("li", { class: "row" }, h("div", { class: "grow" }, flag(figure.severity, figure.label)),
              h("a", { class: "numeric cell-main", href: link(figure) }, String(figure.count)))))
            : h("p", { class: "muted" }, "No flags are raised.")),
          card({ title: "Data confidence" }, plain(board.confidence))),
        h("div", { class: "split" },
          card({ title: "Lifecycle" }, plain(board.lifecycle)),
          card({ title: "Sourcing" }, plain(board.sourcing))));
      return sizeBars(body);
    },
  });
}
