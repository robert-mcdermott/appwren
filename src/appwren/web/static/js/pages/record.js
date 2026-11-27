// One inventory record: what it is, who answers for it, what it is made of and connected to,
// and its history.

import { del, get, patch, post, put } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, plural, relative } from "../core/format.js";
import { catalog, label, units, vocabularies } from "../core/lookups.js";
import { query } from "../core/router.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { confirmAction, openOverlay } from "../components/overlay.js";
import { peoplePicker } from "../components/people-picker.js";
import { lifecyclePill, recordChip, statusPill, supportPill, tierMeter, TYPES } from "../components/record.js";
import { editRecord, SECTIONS } from "../components/record-forms.js";
import { openWorking, scorecard, scoresTab, verdict } from "../components/scorecard.js";
import { decisionsTab, recordDecision } from "../components/decision.js";
import { toast } from "../components/toast.js";
import { alert, avatar, card, emptyState, pill } from "../components/ui.js";
import { show } from "./page.js";
import { dataClasses } from "./records.js";

export function facts(pairs) {
  const shown = pairs.filter(([, value]) => value != null && value !== "" && !(Array.isArray(value) && !value.length));
  if (!shown.length) return h("p", { class: "muted" }, "Nothing recorded yet.");
  return h("dl", { class: "dl" }, shown.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]));
}

export function prose(text) {
  return text ? h("p", { class: "prose" }, text) : null;
}

export function outside(url) {
  return url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, url.replace(/^https?:\/\//, "")) : null;
}

const WITHHELD = "withheld";

/** A field's value as words, from its kind and the vocabularies. */
function shown(spec, record, ctx) {
  const value = record[spec.name];
  if (value === WITHHELD) return h("span", { class: "subtle" }, "Withheld");
  if (value == null || value === "" || (Array.isArray(value) && !value.length)) return null;
  switch (spec.kind) {
    case "choice": return spec.vocab === "tiers" ? tierMeter(ctx.vocab, value) : label(ctx.vocab, spec.vocab, value);
    case "many": return spec.vocab ? value.map((key) => label(ctx.vocab, spec.vocab, key)).join(", ") : value.join(", ");
    case "bool": return value ? "Yes" : "No";
    case "date": return date(value);
    case "url": return outside(value);
    case "int": return spec.name === "annual_cost" ? Number(value).toLocaleString() : String(value);
    case "unit": return ctx.units.byId.get(value)?.name ?? null;
    case "ref": {
      const chip = record[spec.name.replace(/_id$/, "")];
      return chip && typeof chip === "object" ? recordChip(chip) : null;
    }
    case "person": return record[spec.name.replace(/_id$/, "")]?.name ?? null;
    default: return String(value);
  }
}

// --- People in roles -------------------------------------------------------------------------

function editPeople(record, ctx) {
  const people = record.owners.map((owner) => ({ ...owner }));
  openOverlay({
    title: "People",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const roles = ctx.vocab.application_roles.filter((item) => !item.retired).map((item) => [item.key, item.label]);
      const draw = () => {
        list.replaceChildren(...people.map((person, index) => {
          const role = select("Role", roles, { value: person.kind });
          role.input.setAttribute("aria-label", `Role of ${person.name}`);
          role.input.addEventListener("change", () => {
            people[index].kind = role.input.value;
          });
          return h("div", { class: "owner-row" }, avatar(person.name),
            h("div", { class: "grow" }, h("div", { class: "cell-main" }, person.name), h("div", { class: "cell-sub" }, person.email)),
            role.input,
            button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
              people.splice(index, 1);
              draw();
            } }));
        }));
        if (!people.length) list.replaceChildren(h("p", { class: "muted" }, "Nobody yet."));
      };
      draw();
      const picker = peoplePicker({ label: "Add a person",
        exclude: () => false,
        onPick: (account) => {
          people.push({ account_id: account.id, name: account.display_name, email: account.email,
            kind: people.some((p) => p.kind === "accountable") ? "technical_owner" : "accountable" });
          draw();
        } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/applications/${record.ref}/people`,
            { owners: people.map((person) => ({ account_id: person.account_id, kind: person.kind })) }) });
        if (done) {
          close();
          toast("The people were saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "One person is accountable: they answer for the application and its record. Everyone named here may keep it current."),
        list, picker));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function peopleCard(record, ctx) {
  return card({ title: "People", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editPeople(record, ctx) }) : null },
    record.orphaned ? alert("warn", icon("alert"), h("div", {}, record.owners.some((o) => o.kind === "accountable")
      ? "Its accountable owner's account is disabled. Name someone new." : "Nobody is accountable for this application. Name someone.")) : null,
    record.owners.length ? h("div", { class: "stack" }, record.owners.map((person) => h("div", { class: "row" },
      avatar(person.name), h("div", { class: "grow" }, h("div", { class: "cell-main" }, person.name),
        h("div", { class: "cell-sub" }, label(ctx.vocab, "application_roles", person.kind))))))
      : h("p", { class: "muted" }, "Nobody is named."));
}

function editUnits(record, ctx) {
  openOverlay({
    title: "Units that use it",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const chosen = new Set(record.used_by);
      const boxes = ctx.units.list.filter((unit) => unit.status === "active" || chosen.has(unit.id))
        .map((unit) => ({ id: unit.id, box: checkbox(unit.name, { checked: chosen.has(unit.id) }) }));
      const problem = banner();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/applications/${record.ref}/units`, { units: boxes.filter((b) => b.box.input.checked).map((b) => b.id) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, h("div", { class: "unit-checks stack-sm" }, boxes.map((b) => b.box.node))));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

// --- What it is called elsewhere -------------------------------------------------------------

function editExternal(record, ctx) {
  const systems = (ctx.vocab?.external_systems ?? []).filter((item) => !item.retired);
  const rows = record.external_refs.map((item) => ({ system: item.system, value: item.value }));
  openOverlay({
    title: "Known elsewhere as",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("div", { class: "owner-row" },
          h("select", { class: "select", "aria-label": `System ${index + 1}`, onchange: (event) => {
            row.system = event.target.value;
          } }, systems.map((item) => h("option", { value: item.key, selected: item.key === row.system }, item.label))),
          h("input", { class: "input", value: row.value, maxlength: 200, placeholder: "Identifier", "aria-label": `Identifier ${index + 1}`, oninput: (event) => {
            row.value = event.target.value;
          } }),
          button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove identifier ${index + 1}`, onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "Nothing yet: a configuration item, a ticket queue, a repository.")]));
      };
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => patch(`/api/v1/${TYPES[record.type].path}/${record.ref}`, { version: record.version, external_refs: rows.filter((row) => row.value.trim()) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem, list,
        button("Add another", { iconName: "plus", kind: "btn-sm", onclick: () => {
          rows.push({ system: systems[0]?.key ?? "other", value: "" });
          draw();
        } }),
        h("p", { class: "subtle" }, "A record is found by these when searching.")));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function externalCard(record, ctx) {
  const refs = record.external_refs ?? [];
  if (!(refs.length || record.can?.edit)) return null;
  return card({ title: "Known elsewhere as", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editExternal(record, ctx) }) : null },
    refs.length ? h("dl", { class: "dl" }, refs.map((item) => [h("dt", {}, item.label),
      h("dd", {}, item.url ? h("a", { href: item.url, target: "_blank", rel: "noopener noreferrer" }, item.value) : item.value)]))
      : h("p", { class: "muted" }, "No identifier in another system is recorded."));
}

// --- Links -----------------------------------------------------------------------------------

function linkChoices(vocab, type) {
  const out = [];
  for (const kind of vocab.link_kinds ?? []) {
    if (kind.retired) continue;
    for (const [from, to] of kind.between ?? []) {
      if (from === type && TYPES[to]) out.push({ relation: kind.key, to, text: `${kind.label} ${TYPES[to].article}` });
    }
  }
  return out;
}

/** Choose a record of a type by name or reference. */
export function recordFinder(type, { exclude = () => false, onPick, status = "active" }) {
  const search = h("input", { class: "input", type: "search", placeholder: "Name or reference", "aria-label": `Find ${TYPES[type].article}` });
  const results = h("div", { class: "pick-results", role: "listbox", "aria-label": "Records found" });
  let latest = 0;
  const find = async () => {
    const mine = ++latest;
    const found = (await get(`/api/v1/${TYPES[type].path}`, { q: search.value.trim(), sort: "name", limit: 8, status }, { fresh: true })).data;
    if (mine !== latest) return;
    const offered = found.filter((r) => !exclude(r));
    results.replaceChildren(...(offered.length ? offered.map((r) => h("button", { type: "button", class: "pick-item", role: "option", onclick: () => onPick(r) },
      icon(TYPES[type].iconName), h("span", {}, h("span", { class: "cell-main" }, r.name), h("span", { class: "cell-sub" }, ` ${r.ref}`))))
      : [h("div", { class: "subtle pick-none" }, `No ${TYPES[type].nouns} match.`)]));
  };
  let timer = null;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(find, 180);
  });
  find();
  return { node: h("div", { class: "stack-sm" }, search, results), refresh: find };
}

function addLink(record, ctx) {
  const choices = linkChoices(ctx.vocab, record.type);
  openOverlay({
    title: "Add a link",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const problem = banner();
      const how = select(`This ${TYPES[record.type].noun}`, choices.map((choice, index) => [index, choice.text.toLowerCase()]), { value: 0 });
      const note = field("Note", { hint: "Optional. What the link means here, in a few words." });
      const chosen = h("div", {});
      const holder = h("div", {});
      let target = null;
      const makeFinder = () => {
        const choice = choices[Number(how.input.value)];
        const finder = recordFinder(choice.to, { exclude: (r) => r.ref === record.ref, onPick: (r) => {
          target = r;
          chosen.replaceChildren(h("div", { class: "row" }, recordChip(r, { link: false }),
            button("Change", { kind: "btn-ghost btn-sm", onclick: () => {
              target = null;
              chosen.replaceChildren();
              holder.hidden = false;
            } })));
          holder.hidden = true;
        } });
        holder.replaceChildren(finder.node);
      };
      how.input.addEventListener("change", () => {
        target = null;
        chosen.replaceChildren();
        holder.hidden = false;
        makeFinder();
      });
      makeFinder();
      const save = button("Add link", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        if (!target) {
          problem.textContent = "Choose the record to link to.";
          problem.hidden = false;
          return;
        }
        const choice = choices[Number(how.input.value)];
        const done = await submit({ button: save, banner: problem, fields: { note },
          run: () => post(`/api/v1/${TYPES[record.type].path}/${record.ref}/links`,
            { relation: choice.relation, to: target.ref, note: note.input.value || null }) });
        if (done) {
          close();
          toast("The link was added.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem, how.node,
        h("div", { class: "field" }, h("div", { class: "label" }, "Which one"), chosen, holder), note.node));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function linksCard(record, ctx) {
  const canEdit = record.can?.edit;
  const { outgoing, incoming, hidden } = record.links ?? { outgoing: [], incoming: [], hidden: 0 };
  const mayStart = linkChoices(ctx.vocab, record.type).length > 0;
  if (!mayStart && !outgoing.length && !incoming.length) return null;
  const row = (entry) => h("div", { class: "link-row" },
    h("span", { class: "link-label" }, entry.label),
    h("div", { class: "grow" }, recordChip(entry.record), entry.note ? h("div", { class: "cell-sub" }, entry.note) : null),
    canEdit ? button("Remove", { kind: "btn-ghost btn-sm", "aria-label": `Remove the link to ${entry.record.name}`, onclick: () =>
      confirmAction({ title: "Remove this link?", text: `${record.name} will no longer be shown as linked to ${entry.record.name}. The change stays in the history.`,
        confirmLabel: "Remove", run: async () => {
          await del(`/api/v1/${TYPES[record.type].path}/${record.ref}/links/${entry.id}`);
          toast("The link was removed.");
          ctx.reload();
        } }) }) : null);
  const all = [...outgoing, ...incoming];
  return card({ title: "Depends on, and depended on by", actions: canEdit && mayStart ? button("Add a link", { kind: "btn-sm", iconName: "link", onclick: () => addLink(record, ctx) }) : null },
    all.length ? h("div", {}, all.map(row)) : h("p", { class: "muted" }, "Not linked to anything yet. Links show what this depends on, and what depends on it."),
    hidden ? h("p", { class: "subtle" }, `And ${hidden} more that you do not have access to.`) : null);
}

// --- History ---------------------------------------------------------------------------------

export function timeline(entries) {
  if (!entries.length) return emptyState({ iconName: "list", title: "No history yet" });
  return h("ol", { class: "timeline" }, entries.map((entry) => h("li", {},
    h("div", { class: "timeline-dot", "aria-hidden": "true" }),
    h("div", { class: "grow" },
      h("div", { class: "row wrap" }, h("span", { class: "cell-main" }, entry.title),
        h("span", { class: "muted" }, `by ${entry.actor}`),
        h("time", { class: "subtle spacer", datetime: entry.at, title: dateTime(entry.at) }, relative(entry.at))),
      entry.lines.length ? h("dl", { class: "changes" }, entry.lines.map((line) => [
        h("dt", {}, line.label),
        h("dd", {}, line.before != null ? h("del", {}, String(line.before)) : h("span", { class: "subtle" }, "empty"),
          h("span", { "aria-hidden": "true" }, " → "), h("span", { class: "sr-only" }, " became "),
          line.after != null ? h("ins", {}, String(line.after)) : h("span", { class: "subtle" }, "empty")),
      ])) : null))));
}

// --- The page --------------------------------------------------------------------------------

/** The top of every record page: where it came from, what it is, and its badges. */
export function recordHeader(record, { badges = [], actions = null } = {}) {
  const meta = TYPES[record.type];
  return [
    h("a", { class: "back-link", href: `/${meta.path}` }, icon("chevron-left", "icon icon-sm"), meta.plural),
    h("header", { class: "record-header" },
      h("div", { class: "record-icon", "data-record": record.type }, icon(meta.iconName, "icon icon-lg")),
      h("div", { class: "grow" },
        h("div", { class: "eyebrow" }, `${meta.label} · ${record.ref}`),
        h("h1", { tabindex: "-1" }, record.name),
        h("div", { class: "row-sm wrap record-badges" }, badges,
          record.restricted ? h("span", { class: "pill" }, icon("lock"), "Restricted") : null,
          h("span", { class: "subtle" }, `Updated ${relative(record.updated_at)}`))),
      actions),
  ];
}

/** The parts of a record. Each has its own address, so they are links, and the one shown is current. */
export function tabBar(tabs, current) {
  const hrefFor = (key) => {
    const params = query();
    params.delete("tab");
    if (key !== tabs[0][0]) params.set("tab", key);
    const search = params.toString();
    return window.location.pathname + (search ? `?${search}` : "");
  };
  return h("nav", { class: "tabs", "aria-label": "Parts of this record" }, tabs.map(([key, text]) => h("a", { class: "tab", href: hrefFor(key),
    "aria-current": current === key ? "page" : null }, text)));
}

// What a stage requires that is not a field of the application.
const SPECIAL = { accountable: "An accountable owner", capabilities: "The capabilities it serves", components: "Its components",
  technologies: "What its components are built on", assessment: "A current assessment", decision: "A decision about what to do with it" };

function missingCard(record, ctx) {
  const { now, next, next_stage: nextStage } = record.missing ?? { now: [], next: [] };
  if (!now.length && !next.length) return null;
  const name = (key) => SPECIAL[key] ?? ctx.fieldLabels[key] ?? key;
  return card({ title: "What its record still needs" },
    now.length ? h("div", { class: "stack-sm" }, h("p", {}, `For ${label(ctx.vocab, "lifecycle", record.lifecycle)}:`),
      h("ul", { class: "bullets" }, now.map((key) => h("li", {}, name(key))))) : h("p", { class: "muted" }, "Everything its stage requires is recorded."),
    next.length ? h("p", { class: "subtle" }, `Before ${label(ctx.vocab, "lifecycle", nextStage)}: ${next.map(name).join(", ")}.`) : null);
}

function applicationOverview(record, ctx) {
  const specs = ctx.catalog.types.application.fields;
  const bySection = {};
  for (const spec of specs) {
    const value = shown(spec, record, ctx);
    if (value != null) (bySection[spec.section] ??= []).push([spec.label, value]);
  }
  const own = (record.own_fields ?? []).map((spec) => {
    const value = record.fields?.[spec.key];
    if (value == null || value === "") return null;
    const text = spec.type === "choice" ? (spec.options.find(([key]) => key === value)?.[1] ?? value)
      : spec.type === "bool" ? (value ? "Yes" : "No") : spec.type === "url" ? outside(value) : String(value);
    return [spec.label, text];
  }).filter(Boolean);
  const usedBy = record.used_by.map((id) => ctx.units.byId.get(id)?.name).filter(Boolean);
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      record.summary ? card({ title: "About" }, prose(record.summary)) : null,
      Object.entries(SECTIONS).filter(([key]) => bySection[key]?.length).map(([key, title]) => card({ title }, facts(bySection[key]))),
      own.length ? card({ title: "The organization's own fields" }, facts(own)) : null,
      record.withheld?.length ? h("p", { class: "subtle" }, "Some details are shown only to people with a role over this application.") : null),
    h("div", { class: "stack-lg" },
      missingCard(record, ctx),
      peopleCard(record, ctx),
      card({ title: "Used by", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editUnits(record, ctx) }) : null },
        usedBy.length ? h("p", {}, usedBy.join(", ")) : h("p", { class: "muted" }, "No unit is recorded as using it.")),
      record.successor || record.replaces?.length ? card({ title: "Succession" }, facts([
        ["Replaced by", record.successor ? recordChip(record.successor) : null],
        ["Replaces", record.replaces?.length ? h("div", { class: "chips" }, record.replaces.map((r) => recordChip(r))) : null]])) : null,
      linksCard(record, ctx),
      externalCard(record, ctx)));
}

function componentsTab(record, ctx) {
  const add = record.can?.edit ? button("Add a component", { kind: "btn-sm", iconName: "plus", onclick: () =>
    editRecord("component", { preset: { application_id: record.ref }, onDone: () => ctx.reload() }) }) : null;
  return card({ title: plural(record.components.length, "component"), actions: add, flush: record.components.length > 0 },
    record.components.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Component"), h("th", { scope: "col" }, "Kind"), h("th", { scope: "col" }, "Status"))),
      h("tbody", {}, record.components.map((c) => h("tr", {},
        h("td", {}, recordChip(c)), h("td", {}, label(ctx.vocab, "component_kinds", c.kind)), h("td", {}, statusPill(c.status)))))))
      : h("p", { class: "muted" }, "No components recorded. A service, a database, a batch job, or a report that is built, bought, or kept on its own is a component; its technologies are recorded on it."));
}

function editCapabilities(record, ctx) {
  const chosen = record.capabilities.map((c) => ({ ...c }));
  openOverlay({
    title: "Capabilities it serves",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const draw = () => {
        list.replaceChildren(...(chosen.length ? chosen.map((c, index) => {
          const primary = checkbox("Primary provider", { checked: c.is_primary });
          primary.input.addEventListener("change", () => {
            chosen[index].is_primary = primary.input.checked;
          });
          return h("div", { class: "owner-row" }, h("div", { class: "grow" }, recordChip(c, { link: false })), primary.node,
            button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
              chosen.splice(index, 1);
              draw();
            } }));
        }) : [h("p", { class: "muted" }, "None yet.")]));
      };
      draw();
      const finder = recordFinder("capability", { exclude: (r) => chosen.some((c) => c.ref === r.ref), onPick: (r) => {
        chosen.push({ ...r, type: "capability", is_primary: false });
        draw();
        finder.refresh();
      } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/applications/${record.ref}/capabilities`,
            { capabilities: chosen.map((c) => ({ capability: c.ref, is_primary: Boolean(c.is_primary) })) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "The primary provider is the application the organization means to use for that capability. Each capability has at most one."),
        list, h("div", { class: "field" }, h("div", { class: "label" }, "Add a capability"), finder.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function capabilitiesTab(record, ctx) {
  return card({ title: "Capabilities it serves", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editCapabilities(record, ctx) }) : null },
    record.capabilities.length ? h("div", { class: "stack-sm" }, record.capabilities.map((c) => h("div", { class: "row" },
      recordChip(c), c.is_primary ? pill("Primary provider", "accent") : null)))
      : h("p", { class: "muted" }, "No capability recorded. Say what the application does for the organization, so overlaps and gaps can be seen."));
}

function interfaceTable(rows, ctx, { other, heading }) {
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Interface"), h("th", { scope: "col" }, heading), h("th", { scope: "col" }, "Method"),
      h("th", { scope: "col" }, "How often"), h("th", { scope: "col" }, "Data"))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("td", {}, h("a", { class: "cell-main", href: `/interfaces/${r.ref}` }, r.name), h("div", { class: "cell-sub" }, r.ref, r.status === "retired" ? " · retired" : "")),
      h("td", {}, r[other] ? recordChip(r[other]) : ""),
      h("td", {}, label(ctx.vocab, "interface_methods", r.method)),
      h("td", {}, r.frequency ? label(ctx.vocab, "interface_frequencies", r.frequency) : h("span", { class: "subtle" }, "Not said")),
      h("td", {}, dataClasses(ctx.vocab, r.data_classes, r.undeclared)))))));
}

function connectionsTab(record, ctx) {
  const sends = ctx.interfaces.filter((r) => r.source?.ref === record.ref);
  const receives = ctx.interfaces.filter((r) => r.target?.ref === record.ref);
  const add = (end, text) => (record.can?.edit ? button(text, { kind: "btn-sm", iconName: "plus", onclick: () =>
    editRecord("interface", { preset: { [end]: record.ref }, onDone: () => ctx.reload() }) }) : null);
  return h("div", { class: "stack-lg" },
    card({ title: `Sends data to ${plural(new Set(sends.map((r) => r.target?.ref)).size, "application")}`, actions: add("source_id", "It sends data"), flush: sends.length > 0 },
      sends.length ? interfaceTable(sends, ctx, { other: "target", heading: "To" })
        : h("p", { class: "muted" }, "No interface is recorded from it. An application that receives its data depends on it, and counts toward its value.")),
    card({ title: `Receives data from ${plural(new Set(receives.map((r) => r.source?.ref)).size, "application")}`, actions: add("target_id", "It receives data"), flush: receives.length > 0 },
      receives.length ? interfaceTable(receives, ctx, { other: "source", heading: "From" })
        : h("p", { class: "muted" }, "No interface is recorded into it.")),
    linksCard(record, ctx));
}

async function loadRecord(type, ref, tab) {
  const base = `/api/v1/${TYPES[type].path}/${ref}`;
  const [record, vocab, unitIndex, entries, program] = await Promise.all([
    get(base, null, { fresh: true }), vocabularies(), units(),
    tab === "history" ? get(`${base}/history`, null, { fresh: true }) : null, catalog()]);
  return { record: record.data, vocab, units: unitIndex, history: entries?.data ?? [], catalog: program };
}

function context(data, reload) {
  const fieldLabels = Object.fromEntries(Object.values(data.catalog.types).flatMap((t) => t.fields.map((f) => [f.name, f.label])));
  for (const f of data.catalog.fields ?? []) fieldLabels[f.key] = f.label;
  return { vocab: data.vocab, units: data.units, catalog: data.catalog, reload, fieldLabels: { ...fieldLabels, summary: "A summary" } };
}

function assessmentTab(record, ctx) {
  const bank = ctx.questionnaire;
  const current = ctx.assessments.find((a) => !a.superseded);
  const questions = bank.sections.flatMap((s) => s.questions);
  const may = record.can?.edit;
  const answer = (q) => {
    const item = current?.answers?.[q.key];
    if (!item) return h("span", { class: "subtle" }, "Not answered");
    if (item.level == null) return h("span", { class: "subtle" }, "Don't know");
    return h("span", {}, h("strong", {}, String(item.level)), ` · ${q.levels[item.level - 1]}`, item.note ? h("div", { class: "cell-sub" }, item.note) : null);
  };
  return h("div", { class: "split" },
    h("div", { class: "stack-lg" },
      card({ title: current ? `The current answers (${current.ref})` : "Not assessed yet",
        actions: may ? h("a", { class: "btn btn-sm btn-primary", href: `/applications/${record.ref}/assess` }, current ? "Assess again" : "Assess") : null },
      current ? h("div", { class: "stack" }, h("p", { class: "muted" }, `By ${current.assessed_by} on ${date(current.assessed_on)}.`,
        current.note ? ` ${current.note}` : ""), facts(questions.map((q) => [q.text, answer(q)])))
        : h("p", { class: "muted" }, "An assessment is a few questions only a person can answer: how well it fits, how reliable it is, how hard it is to keep. Each answer has a definition, and Don't know is always allowed."))),
    h("div", { class: "stack-lg" },
      card({ title: "Earlier assessments" }, ctx.assessments.filter((a) => a.superseded).length
        ? h("ul", { class: "stack-sm" }, ctx.assessments.filter((a) => a.superseded).map((a) => h("li", {}, `${a.ref} by ${a.assessed_by}, ${date(a.assessed_on)}`)))
        : h("p", { class: "muted" }, "None."))));
}

export function applicationPage(main, params, extraTabs = []) {
  const tabs = [["overview", "Overview"], ["scores", "Scores"], ["assessment", "Assessment"], ["decisions", "Decisions"], ["components", "Components"],
    ["capabilities", "Capabilities"], ["connections", "Connections"], ...extraTabs.map(([key, text]) => [key, text]), ["history", "History"]];
  const wanted = query().get("tab");
  const tab = tabs.some(([key]) => key === wanted) ? wanted : "overview";
  return show(main, {
    title: params.ref,
    load: async () => {
      const base = `/api/v1/applications/${params.ref}`;
      const [data, scores, bank, assessments, decided, joined] = await Promise.all([loadRecord("application", params.ref, tab),
        get(`${base}/scores`, null, { fresh: true }),
        tab === "assessment" ? get("/api/v1/questionnaire") : null,
        tab === "assessment" ? get(`${base}/assessments`, null, { fresh: true }) : null,
        tab === "decisions" ? get(`${base}/decisions`, null, { fresh: true }) : null,
        tab === "connections" ? get("/api/v1/interfaces", { application: params.ref, sort: "name", limit: 200 }, { fresh: true }) : null]);
      return { ...data, scores: scores.data, questionnaire: bank?.data, assessments: assessments?.data ?? [], decisions: decided?.data ?? [],
        interfaces: joined?.data ?? [] };
    },
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const ctx = { ...context(data, reload), questionnaire: data.questionnaire, assessments: data.assessments, interfaces: data.interfaces };
      const edit = record.can?.edit ? button("Edit", { iconName: "edit", onclick: () => editRecord("application", { record, onDone: reload }) }) : null;
      const assessButton = record.can?.assess ? h("a", { class: "btn", href: `/applications/${record.ref}/assess` }, "Assess") : null;
      const decide = () => recordDecision(record, data.scores, data.vocab, reload);
      const decideButton = record.can?.decide ? button("Record a decision", { onclick: decide }) : null;
      const extra = extraTabs.find(([key]) => key === tab);
      const body = tab === "history" ? card({ flush: true }, timeline(data.history))
        : tab === "scores" ? scoresTab(data.scores, { ref: record.ref, vocab: data.vocab })
          : tab === "assessment" ? assessmentTab(record, ctx)
            : tab === "decisions" ? decisionsTab(record, data.decisions, data.vocab, { mayDecide: record.can?.decide, onDecide: decide })
            : tab === "components" ? componentsTab(record, ctx)
              : tab === "capabilities" ? capabilitiesTab(record, ctx)
                : tab === "connections" ? connectionsTab(record, ctx)
                : extra ? extra[2](record, ctx) : applicationOverview(record, ctx);
      const open = (key) => openWorking(data.scores, key, { ref: record.ref, vocab: data.vocab });
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [lifecyclePill(data.vocab, record.lifecycle), tierMeter(data.vocab, record.tier)],
          actions: h("div", { class: "row-sm" }, assessButton, decideButton, edit) }),
        h("div", { class: "app-summary" }, scorecard(data.scores, { onOpen: open }),
          verdict(data.scores, data.vocab, record.decision ?? null)),
        tabBar(tabs.map(([key, text]) => [key, text]), tab),
        body);
    },
  });
}

// --- Components, technologies, vendors, and capabilities ---------------------------------------

function editTechnologies(record, ctx) {
  const rows = record.technologies.map((t) => ({ ref: t.ref, name: t.name, release: t.release ?? "", version: t.version ?? "", releases: null }));
  openOverlay({
    title: "Built on",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const releasesOf = async (row) => {
        if (!row.releases) row.releases = (await get(`/api/v1/technologies/${row.ref}`, null, { fresh: true })).data.releases.map((r) => r.cycle);
        return row.releases;
      };
      const draw = async () => {
        const nodes = await Promise.all(rows.map(async (row, index) => {
          const cycles = await releasesOf(row);
          const release = h("select", { class: "select", "aria-label": `Release of ${row.name}`, onchange: (event) => {
            row.release = event.target.value;
          } }, [["", "Release not known"], ...cycles.map((c) => [c, c])].map(([key, text]) => h("option", { value: key, selected: key === row.release }, text)));
          const version = h("input", { class: "input", value: row.version, placeholder: "Exact version", "aria-label": `Version of ${row.name}`, oninput: (event) => {
            row.version = event.target.value;
          } });
          return h("div", { class: "owner-row" }, h("div", { class: "grow cell-main" }, row.name), release, version,
            button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
              rows.splice(index, 1);
              draw();
            } }));
        }));
        list.replaceChildren(...(nodes.length ? nodes : [h("p", { class: "muted" }, "Nothing yet.")]));
      };
      draw();
      const finder = recordFinder("technology", { exclude: (r) => rows.some((row) => row.ref === r.ref), onPick: (r) => {
        rows.push({ ref: r.ref, name: r.name, release: "", version: "", releases: null });
        draw();
        finder.refresh();
      } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/components/${record.ref}/technologies`,
            { technologies: rows.map((row) => ({ technology: row.ref, release: row.release || null, version: row.version || null })) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "Choose the release where you can: its support dates decide whether the application is on supported technology."),
        list, h("div", { class: "field" }, h("div", { class: "label" }, "Add a technology"), finder.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function editReleases(record, ctx) {
  const rows = record.releases.map((r) => ({ cycle: r.cycle, released_on: r.released_on ?? "", support_ends: r.support_ends ?? "", extended_ends: r.extended_ends ?? "", latest: r.latest ?? "" }));
  openOverlay({
    title: "Releases",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const cell = (row, key, text, type = "text") => h("input", { class: "input", type, value: row[key], "aria-label": text, placeholder: type === "text" ? text : null,
        oninput: (event) => {
          row[key] = event.target.value;
        } });
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => h("div", { class: "release-row" },
          cell(row, "cycle", "Release"), cell(row, "released_on", `Released (${row.cycle || "new"})`, "date"),
          cell(row, "support_ends", `Support ends (${row.cycle || "new"})`, "date"), cell(row, "extended_ends", `Extended support ends (${row.cycle || "new"})`, "date"),
          button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
            rows.splice(index, 1);
            draw();
          } }))) : [h("p", { class: "muted" }, "No releases yet.")]));
      };
      draw();
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/technologies/${record.ref}/releases`, { releases: rows.filter((row) => row.cycle.trim())
            .map((row) => ({ cycle: row.cycle.trim(), released_on: row.released_on || null, support_ends: row.support_ends || null,
              extended_ends: row.extended_ends || null, latest: row.latest || null })) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack" }, problem,
        h("p", { class: "muted" }, "Each release with the date it came out, when its ordinary support ends, and when extended support ends, if there is any."),
        h("div", { class: "release-row release-head", "aria-hidden": "true" }, h("span", {}, "Release"), h("span", {}, "Released"),
          h("span", {}, "Support ends"), h("span", {}, "Extended ends"), h("span", {})),
        list,
        button("Add a release", { iconName: "plus", kind: "btn-sm", onclick: () => {
          rows.unshift({ cycle: "", released_on: "", support_ends: "", extended_ends: "", latest: "" });
          draw();
        } })));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

function sharedOverview(type, record, ctx) {
  const specs = ctx.catalog.types[type].fields;
  const glance = specs.map((spec) => [spec.label, shown(spec, record, ctx)]);
  if (record.tags?.length) glance.push(["Tags", record.tags.join(", ")]);
  const main = [record.summary ? card({ title: "About" }, prose(record.summary)) : null];
  if (type === "component") {
    main.push(card({ title: "Built on", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editTechnologies(record, ctx) }) : null,
      flush: record.technologies.length > 0 },
    record.technologies.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Technology"), h("th", { scope: "col" }, "Release"), h("th", { scope: "col" }, "Support"))),
      h("tbody", {}, record.technologies.map((t) => h("tr", {}, h("td", {}, recordChip(t)),
        h("td", {}, [t.release, t.version].filter(Boolean).join(" · ") || h("span", { class: "subtle" }, "Not known")),
        h("td", {}, h("div", { class: "row-sm" }, supportPill(t.support), t.support_ends ? h("span", { class: "subtle" }, date(t.support_ends)) : null)))))))
      : h("p", { class: "muted" }, "Nothing recorded. Say what it is built on: its language, framework, database, and platform.")));
  }
  if (type === "technology") {
    main.push(card({ title: "Releases and support", actions: record.can?.edit ? button("Edit", { kind: "btn-sm", onclick: () => editReleases(record, ctx) }) : null,
      flush: record.releases.length > 0 },
    record.releases.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Release"), h("th", { scope: "col" }, "Support"), h("th", { scope: "col" }, "Ends"), h("th", { scope: "col" }, "Used by"))),
      h("tbody", {}, record.releases.map((r) => h("tr", {}, h("td", { class: "cell-main" }, r.cycle), h("td", {}, supportPill(r.support)),
        h("td", { class: "nowrap" }, r.support_ends ? date(r.support_ends) : "—", r.extended_ends ? h("div", { class: "cell-sub" }, `Extended to ${date(r.extended_ends)}`) : null),
        h("td", {}, r.used_by.length ? h("div", { class: "chips" }, r.used_by.map((u) => recordChip(u.application))) : h("span", { class: "subtle" }, "None")))))))
      : h("p", { class: "muted" }, "No releases recorded. Add each version line with the date its support ends.")));
    if (record.unpinned?.length) {
      main.push(card({ title: "Used with no release named" }, h("div", { class: "chips" }, record.unpinned.map((u) => recordChip(u.component)))));
    }
  }
  if (type === "vendor") {
    main.push(card({ title: "Applications" }, record.applications.length ? h("div", { class: "chips" }, record.applications.map((r) => recordChip(r))) : h("p", { class: "muted" }, "None recorded.")));
    if (record.technologies.length) main.push(card({ title: "Technologies" }, h("div", { class: "chips" }, record.technologies.map((r) => recordChip(r)))));
  }
  if (type === "capability") {
    main.push(card({ title: "Applications that serve it" }, record.applications.length
      ? h("div", { class: "stack-sm" }, record.applications.map((app) => h("div", { class: "row" }, recordChip(app), app.is_primary ? pill("Primary provider", "accent") : null,
        lifecyclePill(ctx.vocab, app.lifecycle))))
      : h("p", { class: "muted" }, "No application is recorded as serving it.")));
    if (record.children.length) main.push(card({ title: "Narrower capabilities" }, h("div", { class: "chips" }, record.children.map((r) => recordChip(r)))));
    glance.push(["Part of", record.parent ? recordChip(record.parent) : null]);
  }
  if (type === "interface") {
    const missing = record.undeclared ?? [];
    main.push(card({ title: "What passes" },
      h("div", { class: "stack" },
        h("div", { class: "flow-ends" }, record.source ? recordChip(record.source) : null,
          h("span", { class: "flow-arrow" }, icon("chevron-right"), h("span", { class: "sr-only" }, "sends to")),
          record.target ? recordChip(record.target) : null),
        dataClasses(ctx.vocab, record.data_classes, missing),
        missing.length && record.target ? alert("warn", h("p", {}, `The record of ${record.target.name} does not say it handles `,
          missing.map((key) => label(ctx.vocab, "data_classes", key).toLowerCase()).join(", "),
          ". Either this interface carries less than is recorded here, or that record needs the class added: its exposure is worked out from what it lists.")) : null)));
  }
  if (type === "component") glance.unshift(["Application", record.application ? recordChip(record.application) : null]);
  main.push(linksCard(record, ctx));
  return h("div", { class: "split" }, h("div", { class: "stack-lg" }, main),
    h("div", { class: "stack-lg" }, card({ title: "At a glance" }, facts(glance)), externalCard(record, ctx)));
}

export function recordPage(main, type, params) {
  const tab = query().get("tab") === "history" ? "history" : "overview";
  return show(main, {
    title: params.ref,
    load: () => loadRecord(type, params.ref, tab),
    view: (data, reload) => {
      const record = data.record;
      document.title = `${record.name} · ${record.ref}`;
      const ctx = context(data, reload);
      const edit = record.can?.edit ? button("Edit", { iconName: "edit", onclick: () => editRecord(type, { record, onDone: reload }) }) : null;
      return h("div", { class: "stack" },
        recordHeader(record, { badges: [statusPill(record.status)], actions: edit }),
        tabBar([["overview", "Overview"], ["history", "History"]], tab),
        tab === "history" ? card({ flush: true }, timeline(data.history)) : sharedOverview(type, record, ctx));
    },
  });
}
