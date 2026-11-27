// The applications a figure counts: the portfolio narrowed by the figure's own filters, which
// are in the address, so every figure can be shared and every list exported.

import { buildUrl, get } from "../core/api.js";
import { h } from "../core/dom.js";
import { plural } from "../core/format.js";
import { label, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { hrefOf } from "../components/record.js";
import { card, dispositionBadge, emptyState, pageHeader, pill } from "../components/ui.js";
import { viewsButton } from "../components/views.js";
import { show } from "./page.js";

const WORDS = {
  recommendation: "Recommended", decision: "Decided", flag: "Flag", lifecycle: "Stage", sourcing: "Sourcing",
  domain: "Domain", tier: "Tier", eol: "Technology", quality: "Quality", confidence_min: "Confidence from",
  confidence_max: "Confidence to", mismatch: "Mismatch", review_due: "Review due", decided: "Decided",
  unit: "Unit", unit_only: "Unit", in_service: "In service",
};

const QUALITY = { no_accountable: "nobody accountable", no_capability: "no capability", no_assessment: "never assessed",
  assessment_expired: "assessment expired", low_confidence: "low confidence", missing_required: "missing what its stage requires" };

export function portfolioList(main) {
  return show(main, {
    title: "Applications",
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, vocab] = await Promise.all([get("/api/v1/portfolio", params, { fresh: true }), vocabularies()]);
      return { rows: page.data, vocab, params };
    },
    view: ({ rows, vocab, params }) => {
      const said = (key, value) => {
        if (value === "true") return "yes";
        if (value === "false") return "no";
        if (key === "recommendation" || key === "decision") return value === "none" ? "none yet" : label(vocab, "dispositions", value);
        if (["lifecycle", "sourcing"].includes(key)) return label(vocab, key, value);
        if (key === "quality") return QUALITY[value] ?? value;
        if (key === "eol") return value === "past" ? "past end of support" : "support ending within a year";
        return String(value).replace(/_/g, " ");
      };
      const chips = Object.entries(params).filter(([key]) => WORDS[key] && !["unit", "unit_only", "in_service"].includes(key))
        .map(([key, value]) => pill(`${WORDS[key]}: ${said(key, value)}`, "accent"));
      const exportHref = buildUrl("/api/v1/exports/portfolio", { ...params, format: "csv" });
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Reports", title: "Applications",
          lede: "The applications a figure counts. The filters are in the address, so this view can be shared.",
          actions: [viewsButton(), h("a", { class: "btn", href: exportHref, download: "" }, "Export as CSV")] }),
        chips.length ? h("div", { class: "row-sm wrap" }, chips) : null,
        card({ title: plural(rows.length, "application"), flush: rows.length > 0 }, rows.length
          ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, ["Application", "Accountable", "Value", "Health", "Confidence", "Recommended", "Decided"].map((t) => h("th", { scope: "col" }, t)))),
            h("tbody", {}, rows.map((r) => h("tr", {},
              h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name), h("div", { class: "cell-sub" }, [r.ref, label(vocab, "lifecycle", r.lifecycle)].join(" · "))),
              h("td", {}, r.accountable.join(", ") || h("span", { class: "warn-text" }, "Nobody")),
              ["business_value", "technical_health"].map((k) => h("td", { class: "numeric" }, r.scores[k] == null ? "—" : r.scores[k].toFixed(1))),
              h("td", { class: "numeric" }, `${r.confidence}%`),
              h("td", {}, r.recommendation ? dispositionBadge(r.recommendation, label(vocab, "dispositions", r.recommendation)) : "—"),
              h("td", {}, r.decision ? dispositionBadge(r.decision, label(vocab, "dispositions", r.decision), { decided: true }) : h("span", { class: "subtle" }, "None")))))))
          : emptyState({ iconName: "search", title: "None", text: "No application matches." })));
    },
  });
}
