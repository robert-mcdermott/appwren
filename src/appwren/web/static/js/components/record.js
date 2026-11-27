// How records are shown everywhere: their kinds, chips, status, lifecycle, and tier.

import { h, icon } from "../core/dom.js";
import { titleCase } from "../core/format.js";
import { label } from "../core/lookups.js";
import { pill } from "./ui.js";

// Each kind of record: where it lives, what it is called, and what its list says about it.
export const TYPES = {
  application: { prefix: "APP", path: "applications", label: "Application", plural: "Applications", noun: "application", nouns: "applications",
    article: "an application", iconName: "application", section: "Portfolio",
    lede: "The software the organization runs, each with one person who answers for it." },
  component: { prefix: "CMP", path: "components", label: "Component", plural: "Components", noun: "component", nouns: "components",
    article: "a component", iconName: "component", section: "Portfolio", kinds: "component_kinds",
    lede: "The parts of applications that are built, bought, or kept on their own: services, databases, jobs, reports." },
  vendor: { prefix: "VEN", path: "vendors", label: "Vendor", plural: "Vendors", noun: "vendor", nouns: "vendors",
    article: "a vendor", iconName: "vendor", section: "Landscape", kinds: "vendor_kinds",
    lede: "The companies and projects that supply the organization's software and services." },
  technology: { prefix: "TEC", path: "technologies", label: "Technology", plural: "Technologies", noun: "technology", nouns: "technologies",
    article: "a technology", iconName: "technology", section: "Landscape", kinds: "technology_kinds",
    lede: "The languages, frameworks, databases, and platforms applications are built on, with how long each release is supported." },
  capability: { prefix: "CAP", path: "capabilities", label: "Capability", plural: "Capabilities", noun: "capability", nouns: "capabilities",
    article: "a capability", iconName: "capability", section: "Landscape",
    lede: "What the organization does, whatever does it. Each application says which capabilities it serves, and one may be the primary provider." },
  interface: { prefix: "INT", path: "interfaces", label: "Interface", plural: "Interfaces", noun: "interface", nouns: "interfaces",
    article: "an interface", iconName: "interface", section: "Landscape", kinds: null,
    lede: "Data passing from one application to another: how, how often, and of which classes." },
  hosting_platform: { prefix: "HST", path: "hosting-platforms", label: "Hosting platform", plural: "Hosting platforms", noun: "hosting platform", nouns: "hosting platforms",
    article: "a hosting platform", iconName: "platform", section: "Landscape", kinds: "platform_kinds",
    lede: "Where things run: data centers, cloud accounts, clusters, and providers, each with what runs on it." },
  deployment: { prefix: "DEP", path: "deployments", label: "Deployment", plural: "Deployments", noun: "deployment", nouns: "deployments",
    article: "a deployment", iconName: "deployment", section: "Landscape", kinds: null,
    lede: "An application, or one of its components, running in an environment on a platform." },
  contract: { prefix: "CON", path: "contracts", label: "Contract", plural: "Contracts", noun: "contract", nouns: "contracts",
    article: "a contract", iconName: "contract", section: "Portfolio", kinds: null,
    lede: "Agreements with vendors: what each covers, when it ends, and how long before that the vendor must be told. Shown to those who may see what the applications cost." },
  review: { prefix: "REV", path: "reviews", label: "Review", plural: "Reviews", noun: "review", nouns: "reviews",
    article: "a review", iconName: "decision", section: "Portfolio", kinds: null,
    lede: "Portfolio reviews: a unit's applications that need deciding, the decisions taken, and a record of them once closed." },
  initiative: { prefix: "INI", path: "initiatives", label: "Initiative", plural: "Initiatives", noun: "initiative", nouns: "initiatives",
    article: "an initiative", iconName: "lifecycle", section: "Portfolio", kinds: "initiative_kinds",
    lede: "Planned changes: modernizations, migrations, consolidations, replacements, and retirements, each with the applications it changes and its dates." },
  request: { prefix: "REQ", path: "requests", label: "Request", plural: "Requests", noun: "request", nouns: "requests",
    article: "a request", iconName: "plus", section: "Portfolio", kinds: null,
    lede: "Requests for something new: the need, what already serves it, the ways to meet it, and how each ended." },
  scenario: { prefix: "SCN", path: "scenarios", label: "Scenario", plural: "Scenarios", noun: "scenario", nouns: "scenarios",
    article: "a scenario", iconName: "chart", section: "Portfolio", kinds: null,
    lede: "Proposed sets of changes, each with what it would save, whom it would affect, and what would stop, before anyone commits to it. A scenario changes nothing." },
  funding_source: { prefix: "FND", path: "funding-sources", label: "Funding source", plural: "Funding sources", noun: "funding source", nouns: "funding sources",
    article: "a funding source", iconName: "funding", section: "Portfolio", kinds: "funding",
    lede: "What pays: operating budgets, grants, chargebacks, and capital projects. Cost lines say which pays for what." },
};

const BY_PREFIX = Object.fromEntries(Object.entries(TYPES).map(([key, type]) => [type.prefix, key]));

export function typeOfRef(ref) {
  return BY_PREFIX[String(ref).split("-")[0]];
}

export function hrefOf(ref) {
  const type = TYPES[typeOfRef(ref)];
  return type ? `/${type.path}/${ref}` : "/";
}

/** A record as a link: its type's icon, its name, and its reference. */
export function recordChip(record, { link = true } = {}) {
  const type = record.type ?? typeOfRef(record.ref);
  const inner = [icon(TYPES[type]?.iconName ?? "dot"), h("span", { class: "truncate" }, record.name), h("span", { class: "ref" }, record.ref)];
  return link
    ? h("a", { class: "chip", "data-record": type, href: hrefOf(record.ref) }, inner)
    : h("span", { class: "chip", "data-record": type }, inner);
}

// Status: a word, a mark, and a tone. Never a color alone.
const STATUS = {
  active: ["Active", "ok", "●"],
  retired: ["Retired", "", "○"],
};

export function statusLabel(status) {
  return STATUS[status]?.[0] ?? titleCase(status);
}

export function statusPill(status) {
  const [text, tone, mark] = STATUS[status] ?? [titleCase(status), "", "○"];
  const node = pill("", tone);
  node.append(h("span", { "aria-hidden": "true" }, mark), text);
  return node;
}

export function statusOptions(keys, blank) {
  return [["", blank], ...keys.map((key) => [key, statusLabel(key)])];
}

// Where an application is in its life: early stages are information, later ones quieter.
const STAGE_TONES = { proposed: "info", evaluating: "info", phase_in: "info", active: "ok", containment: "warn", phase_out: "warn", retired: "", archived: "" };

export function lifecyclePill(vocab, key) {
  if (!key) return h("span", { class: "subtle" }, "Not said");
  return pill(label(vocab, "lifecycle", key), STAGE_TONES[key] ?? "");
}

/**
 * How critical an application is: a quiet meter of filled squares and the tier's name. It is
 * not a score, and never borrows the score ramp or the colors of flags.
 */
export function tierMeter(vocab, key) {
  const levels = (vocab.tiers ?? []).map((item) => item.key);
  const position = levels.indexOf(key);
  if (position < 0) return h("span", { class: "subtle" }, "No tier set");
  const filled = levels.length - position;
  const item = vocab.tiers.find((tier) => tier.key === key) ?? {};
  return h("span", { class: "meter", title: item.description ?? "" },
    h("span", { class: "meter-marks", "aria-hidden": "true" }, levels.map((_, index) => h("i", { "data-on": String(index < filled) }))),
    item.label ?? key);
}

/** Support state of a technology release, as words and a tone. */
const SUPPORT = {
  supported: ["Supported", "ok"],
  ending: ["Support ending", "warn"],
  extended: ["Extended support", "warn"],
  ended: ["Past end of support", "danger"],
  unknown: ["Dates unknown", ""],
};

export function supportPill(state) {
  const [text, tone] = SUPPORT[state] ?? SUPPORT.unknown;
  return pill(text, tone);
}
