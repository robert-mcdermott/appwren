// The inventory's list pages. Filters, sort, and page all live in the URL.

import { buildUrl, get } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date, plural, relative } from "../core/format.js";
import { label, options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { hrefOf, lifecyclePill, recordChip, statusOptions, statusPill, supportPill, tierMeter, TYPES } from "../components/record.js";
import { editRecord, mayAdd } from "../components/record-forms.js";
import { openImport } from "../components/importer.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { importSupportDates } from "./lifecycle.js";
import { viewsButton } from "../components/views.js";
import { show } from "./page.js";

/** Download the list as it is filtered now. */
export function exportLink(path) {
  const params = Object.fromEntries([...query()].filter(([key]) => !["cursor", "sort"].includes(key)));
  return h("a", { class: "btn", href: buildUrl(`/api/v1/exports/${path}`, { ...params, format: "csv" }), download: "" }, "Export");
}

function importApplications(onDone) {
  openImport({
    kind: "applications",
    title: "Import applications",
    intro: "Add applications from a spreadsheet, or update those it names by reference. The file is checked first, and nothing is loaded unless every row is good.",
    sample: "Reference,Name,Unit,Accountable owner,Sourcing,Tier,Vendor,Users,Data classes",
    onDone,
  });
}

export function filterSelect(name, choices, labelText) {
  const node = h("select", { class: "select", "aria-label": labelText, onchange: () => setQuery({ [name]: node.value, cursor: null }) },
    choices.map(([key, text]) => h("option", { value: key, selected: String(key) === (query().get(name) ?? "") }, text)));
  return node;
}

export function sortHeader(text, field, fallback = "-updated_at") {
  const current = query().get("sort") ?? fallback;
  const active = current.replace(/^-/, "") === field;
  const descending = active && current.startsWith("-");
  return h("th", { scope: "col", "aria-sort": active ? (descending ? "descending" : "ascending") : null },
    h("button", { type: "button", class: "sort-button", onclick: () => setQuery({ sort: active && !descending ? `-${field}` : field, cursor: null }) },
      text, active ? h("span", { "aria-hidden": "true" }, descending ? " ↓" : " ↑") : null));
}

/** A search box that writes to the URL a moment after typing stops. */
export function searchBox(placeholder) {
  const search = h("input", { class: "input", type: "search", value: query().get("q") ?? "", placeholder, "aria-label": "Search" });
  let timer = null;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => setQuery({ q: search.value, cursor: null }), 250);
  });
  return search;
}

export function mineToggle() {
  const mine = query().get("mine") === "true";
  return h("button", { type: "button", class: `btn${mine ? " btn-primary" : ""}`, "aria-pressed": String(mine),
    onclick: () => setQuery({ mine: mine ? null : "true", cursor: null }) }, "Mine");
}

/** Keep the caret in the search box when the list redraws under it. */
export function keepSearchFocus(search) {
  if (document.activeElement?.getAttribute?.("aria-label") !== "Search") return;
  queueMicrotask(() => {
    search.focus();
    search.setSelectionRange(search.value.length, search.value.length);
  });
}

export function pager(meta, shown) {
  const { total, offset, next_cursor: next, prev_cursor: prev } = meta;
  if (total <= shown) return null;
  return h("div", { class: "row" },
    h("span", { class: "muted numeric" }, `${offset + 1}–${offset + shown} of ${total}`),
    h("div", { class: "spacer row-sm" },
      button("Previous", { kind: "btn-sm", disabled: prev == null, onclick: () => setQuery({ cursor: prev }, { replace: false }) }),
      button("Next", { kind: "btn-sm", disabled: !next, onclick: () => setQuery({ cursor: next }, { replace: false }) })));
}

export function clearFilters() {
  setQuery(Object.fromEntries([...query().keys()].map((key) => [key, null])));
}

export function isFiltering() {
  return [...query().keys()].some((key) => !["sort", "cursor"].includes(key));
}

export function ownerCell(record) {
  return h("td", {}, record.owners.map((owner) => owner.name).join(", "),
    record.orphaned ? h("div", { class: "cell-sub warn-text" }, record.owners.length ? "Owner has left" : "Nobody is accountable") : null);
}

function nothing(meta, add) {
  return emptyState(isFiltering()
    ? { iconName: "search", title: "Nothing matches", text: "Try fewer words, or clear a filter.",
      action: button("Clear filters", { onclick: clearFilters }) }
    : { iconName: meta.iconName, title: `No ${meta.nouns} yet`, text: meta.lede,
      action: add ? button(`Add ${meta.article}`, { kind: "btn-primary", onclick: add }) : null });
}

/** The applications: the portfolio as a list. */
export function applicationList(main) {
  const meta = TYPES.application;
  return show(main, {
    title: meta.plural,
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, vocab, unitIndex] = await Promise.all([
        get("/api/v1/applications", { sort: "name", ...params }, { fresh: true }), vocabularies(), units()]);
      return { page, vocab, units: unitIndex };
    },
    view: (data, reload) => {
      const { vocab } = data;
      const rows = data.page.data;
      const add = mayAdd("application") ? () => editRecord("application", { onDone: null }) : null;
      const search = searchBox("Search applications");
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        filterSelect("lifecycle", options(vocab, "lifecycle", { blank: "Any stage" }), "Lifecycle stage"),
        filterSelect("sourcing", options(vocab, "sourcing", { blank: "Any sourcing" }), "Sourcing"),
        filterSelect("tier", options(vocab, "tiers", { blank: "Any tier" }), "Criticality tier"),
        filterSelect("domain", options(vocab, "domains", { blank: "Any domain" }), "Domain"),
        filterSelect("unit", unitOptions(data.units.tree, { blank: "Any unit" }), "Unit"),
        mineToggle());
      const body = rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, sortHeader("Application", "name", "name"), h("th", { scope: "col" }, "Unit"),
            h("th", { scope: "col" }, "Accountable"), sortHeader("Stage", "lifecycle", "name"),
            sortHeader("Tier", "tier", "name"), sortHeader("Sourcing", "sourcing", "name"), sortHeader("Updated", "updated_at", "name"))),
          h("tbody", {}, rows.map((r) => h("tr", {},
            h("td", {}, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name),
              h("div", { class: "cell-sub" }, [r.ref, r.vendor?.name, r.restricted ? "Restricted" : null].filter(Boolean).join(" · "))),
            h("td", {}, data.units.byId.get(r.org_unit_id)?.name ?? ""),
            ownerCell(r),
            h("td", {}, lifecyclePill(vocab, r.lifecycle)),
            h("td", {}, tierMeter(vocab, r.tier)),
            h("td", {}, r.sourcing ? label(vocab, "sourcing", r.sourcing) : h("span", { class: "subtle" }, "Not said")),
            h("td", { class: "nowrap muted" }, relative(r.updated_at)))))))
        : nothing(meta, add);
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: meta.section, title: meta.plural, lede: meta.lede,
          actions: [add ? button("Add an application", { kind: "btn-primary", iconName: "plus", onclick: add }) : null,
            add ? button("Import", { iconName: "upload", onclick: () => importApplications(reload) }) : null,
            viewsButton(), exportLink("applications")] }),
        bar,
        card({ title: plural(data.page.meta.total, meta.noun, meta.nouns), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}

// What each shared list shows beyond its name.
const COLUMNS = {
  component: [["Application", (r) => (r.application ? recordChip(r.application) : "")], ["Kind", (r, v) => label(v, "component_kinds", r.kind)]],
  vendor: [["Kind", (r, v) => label(v, "vendor_kinds", r.kind)]],
  hosting_platform: [
    ["Kind", (r, v) => label(v, "platform_kinds", r.kind)],
    ["Provider", (r) => (r.vendor ? recordChip(r.vendor) : h("span", { class: "subtle" }, "Ourselves"))],
    ["Where", (r) => r.location ?? ""],
    ["Runs", (r) => (r.deployment_count ? `${plural(r.application_count, "application")} in ${plural(r.deployment_count, "deployment")}` : h("span", { class: "subtle" }, "Nothing recorded"))],
  ],
  deployment: [
    ["Application", (r) => (r.application ? recordChip(r.application) : "")],
    ["Part", (r) => (r.component ? recordChip(r.component) : h("span", { class: "subtle" }, "All of it"))],
    ["Environment", (r, v) => label(v, "environments", r.environment)],
    ["Platform", (r) => (r.platform ? recordChip(r.platform) : "")],
  ],
  contract: [
    ["Vendor", (r) => (r.vendor ? recordChip(r.vendor) : "")],
    ["Covers", (r) => (r.applications.length ? h("div", { class: "chips" }, r.applications.slice(0, 2).map((a) => recordChip(a)),
      r.applications.length > 2 ? h("span", { class: "subtle" }, `and ${r.applications.length - 2} more`) : null) : h("span", { class: "subtle" }, "Nothing yet"))],
    ["Ends", (r) => (r.ends_on ? h("span", { class: "nowrap" }, date(r.ends_on)) : h("span", { class: "subtle" }, "Not said"))],
    ["Notice", (r) => noticePill(r)],
    ["Data agreement", (r, v) => agreementPill(v, r.data_agreement)],
  ],
  funding_source: [
    ["Kind", (r, v) => label(v, "funding", r.kind)],
    ["Code", (r) => r.code ?? ""],
    ["Ends", (r) => (r.ends_on ? h("span", { class: "row-sm" }, date(r.ends_on), r.days_to_end != null && r.days_to_end >= 0 && r.days_to_end <= 365 ? h("span", { class: "pill pill-warn" }, "Within a year") : null) : h("span", { class: "subtle" }, "—"))],
    ["Pays for", (r) => plural(r.application_count, "application")],
    ["A year", (r) => (r.total == null ? h("span", { class: "subtle" }, "Withheld") : Number(r.total).toLocaleString())],
  ],
  interface: [
    ["From", (r) => (r.source ? recordChip(r.source) : "")],
    ["To", (r) => (r.target ? recordChip(r.target) : "")],
    ["Method", (r, v) => label(v, "interface_methods", r.method)],
    ["How often", (r, v) => (r.frequency ? label(v, "interface_frequencies", r.frequency) : h("span", { class: "subtle" }, "Not said"))],
    ["Data", (r, v) => dataClasses(v, r.data_classes, r.undeclared)],
  ],
  technology: [
    ["Kind", (r, v) => label(v, "technology_kinds", r.kind)],
    ["Radar", (r, v) => (r.radar ? label(v, "radar", r.radar) : h("span", { class: "subtle" }, "Not said"))],
    ["In use", (r) => plural(r.use_count, "component")],
    ["Soonest end of support", (r) => (r.soonest_end ? h("span", { class: "row-sm" }, supportPill(r.soonest_support), date(r.soonest_end)) : h("span", { class: "subtle" }, "—"))],
  ],
  capability: [
    ["Domain", (r, v) => (r.domain ? label(v, "domains", r.domain) : "")],
    ["Applications", (r) => String(r.application_count)],
    ["Primary", (r) => (r.primary ? recordChip(r.primary) : h("span", { class: "subtle" }, "None named"))],
  ],
};

/** When the vendor must be told, if a contract is not to renew: a date, and how near it is. */
export function noticePill(contract) {
  if (contract.notice_by == null) return h("span", { class: "subtle" }, "No end date");
  const days = contract.days_to_notice;
  if (contract.days_to_end != null && contract.days_to_end < 0) return h("span", { class: "pill" }, "Ended");
  if (days < 0) return h("span", { class: "pill pill-danger" }, contract.auto_renews ? "Notice date passed: it renews" : "Notice date passed");
  if (days <= 90) return h("span", { class: "pill pill-warn" }, `Notice due in ${plural(days, "day")}`);
  return h("span", { class: "nowrap" }, `By ${date(contract.notice_by)}`);
}

export function agreementPill(vocab, key) {
  if (!key) return h("span", { class: "subtle" }, "Not said");
  return h("span", { class: `pill${key === "missing" ? " pill-danger" : key === "in_place" ? " pill-ok" : ""}` }, label(vocab, "agreement_states", key));
}

/** The classes of data something holds or carries, with a mark on any the receiver's record lacks. */
export function dataClasses(vocab, keys, undeclared = []) {
  if (!keys?.length) return h("span", { class: "subtle" }, "Not said");
  return h("span", { class: "chips" }, keys.map((key) => (undeclared.includes(key)
    ? h("span", { class: "pill pill-warn", title: "The receiving application's record does not list this class" }, label(vocab, "data_classes", key), " · not on its record")
    : h("span", { class: "pill" }, label(vocab, "data_classes", key)))));
}

/** Components, vendors, technologies, capabilities, and interfaces. */
export function recordList(main, type) {
  const meta = TYPES[type];
  return show(main, {
    title: meta.plural,
    load: async () => {
      const params = Object.fromEntries(query());
      const [page, vocab] = await Promise.all([get(`/api/v1/${meta.path}`, { sort: "name", ...params }, { fresh: true }), vocabularies()]);
      return { page, vocab };
    },
    view: (data, reload) => {
      const { vocab } = data;
      const rows = data.page.data;
      // A component and a deployment are added from their application's page.
      const add = !["component", "deployment"].includes(type) && mayAdd(type) ? () => editRecord(type, {}) : null;
      const search = searchBox(`Search ${meta.nouns}`);
      keepSearchFocus(search);
      const bar = h("div", { class: "filters" }, h("div", { class: "filter-search" }, search),
        meta.kinds ? filterSelect("kind", options(vocab, meta.kinds, { blank: "Any kind" }), "Kind") : null,
        type === "technology" ? filterSelect("radar", options(vocab, "radar", { blank: "Any ring" }), "Radar") : null,
        type === "contract" ? filterSelect("ending_within", [["", "Ending whenever"], ["90", "Ending within 90 days"], ["180", "Ending within 6 months"], ["365", "Ending within a year"]], "Ending") : null,
        type === "contract" ? filterSelect("data_agreement", options(vocab, "agreement_states", { blank: "Any agreement" }), "Data agreement") : null,
        type === "deployment" ? filterSelect("environment", options(vocab, "environments", { blank: "Any environment" }), "Environment") : null,
        type === "interface" ? filterSelect("method", options(vocab, "interface_methods", { blank: "Any method" }), "Method") : null,
        type === "interface" ? filterSelect("data_class", options(vocab, "data_classes", { blank: "Any data" }), "Data it carries") : null,
        type === "capability" ? filterSelect("domain", options(vocab, "domains", { blank: "Any domain" }), "Domain") : null,
        filterSelect("status", statusOptions(["active", "retired"], "Any status"), "Status"));
      const columns = COLUMNS[type] ?? [];
      const body = rows.length
        ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, sortHeader(meta.label, "name", "name"), columns.map(([title]) => h("th", { scope: "col" }, title)),
            sortHeader("Status", "status", "name"))),
          h("tbody", {}, rows.map((r) => h("tr", {},
            h("td", { class: "cell-name" }, h("a", { class: "cell-main", href: hrefOf(r.ref) }, r.name), h("div", { class: "cell-sub" }, r.ref)),
            columns.map(([, cell]) => h("td", {}, cell(r, vocab))),
            h("td", {}, statusPill(r.status)))))))
        : nothing(meta, add);
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: meta.section, title: meta.plural, lede: meta.lede,
          actions: [viewsButton(), type === "capability" ? h("a", { class: "btn", href: "/capability-map" }, "The map") : null,
            type === "technology" ? h("a", { class: "btn", href: "/lifecycle" }, "Lifecycle") : null,
            type === "technology" ? h("a", { class: "btn", href: "/radar" }, "Radar") : null,
            type === "technology" && mayAdd(type) ? button("Import support dates", { iconName: "upload", onclick: () => importSupportDates(reload) }) : null,
            type === "interface" ? h("a", { class: "btn", href: "/data-flows" }, "Data flows") : null,
            type === "contract" ? h("a", { class: "btn", href: "/funding-sources" }, "Funding sources") : null,
            type === "funding_source" ? h("a", { class: "btn", href: "/contracts" }, "Contracts") : null,
            add ? button(`Add ${meta.article}`, { kind: "btn-primary", iconName: "plus", onclick: add }) : null,
            exportLink(meta.path)] }),
        bar,
        card({ title: plural(data.page.meta.total, meta.noun, meta.nouns), flush: true, footer: pager(data.page.meta, rows.length) }, body));
    },
  });
}
