// Finding anything on record: the command palette's records, and a page of results.

import { get } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { plural, titleCase } from "../core/format.js";
import { units } from "../core/lookups.js";
import { query, setQuery } from "../core/router.js";
import { hrefOf, statusPill, TYPES } from "../components/record.js";
import { card, emptyState, pageHeader } from "../components/ui.js";
import { show } from "./page.js";

const meta = (type) => TYPES[type] ?? { label: titleCase(type), plural: titleCase(type), iconName: "dot" };

/** Records found by words, for the command palette. */
export async function quickFind(text) {
  const found = (await get("/api/v1/search", { q: text, limit: 4 }, { fresh: true })).data;
  return found.groups.flatMap((group) => group.items.map((item) => ({
    label: item.name, hint: `${meta(item.type).label} · ${item.ref}`, iconName: meta(item.type).iconName, href: hrefOf(item.ref),
  })));
}

export function searchPage(main) {
  const asked = query().get("q") ?? "";
  const only = query().get("type");
  return show(main, {
    title: "Search",
    load: async () => {
      const [found, unitIndex] = await Promise.all([
        asked.trim().length > 1 ? get("/api/v1/search", { q: asked, type: only || undefined, limit: only ? 50 : 6 }, { fresh: true }) : null, units()]);
      return { found: found?.data ?? null, units: unitIndex };
    },
    view: (data) => {
      const box = h("input", { class: "input", type: "search", value: asked, placeholder: "A name, a reference, or a few words", "aria-label": "Search" });
      let timer = null;
      box.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => setQuery({ q: box.value || null, type: null }), 300);
      });
      queueMicrotask(() => {
        box.focus();
        box.setSelectionRange(box.value.length, box.value.length);
      });
      const found = data.found;
      const groups = found?.groups ?? [];
      const results = !found
        ? emptyState({ iconName: "search", title: "Search everything on record", text: "Applications, capabilities, components, technologies, vendors, interfaces, contracts, and the rest, by name, reference, summary, or what something is called in another system. You find only what you may open." })
        : !groups.length
          ? emptyState({ iconName: "search", title: `Nothing matches “${asked}”`, text: "Every word has to be on the record. Try fewer words, or part of one." })
          : groups.map((group) => card({ title: `${titleCase(group.label)} · ${group.total}`, flush: true,
            actions: group.total > group.items.length ? h("a", { href: `/search?q=${encodeURIComponent(asked)}&type=${group.type}` }, `All ${group.total}`) : null },
          h("ul", { class: "found-list" }, group.items.map((item) => h("li", {},
            h("div", { class: "record-icon small", "data-record": item.type, "aria-hidden": "true" }, icon(meta(item.type).iconName, "icon icon-sm")),
            h("div", { class: "grow" },
              h("a", { class: "cell-main", href: hrefOf(item.ref) }, item.name),
              h("div", { class: "cell-sub" }, [item.ref, data.units.byId.get(item.org_unit_id)?.name, item.summary].filter(Boolean).join(" · "))),
            item.status && !["active", "open"].includes(item.status) ? statusPill(item.status) : null)))));
      return h("div", { class: "stack-lg" },
        pageHeader({ title: "Search", lede: found && groups.length ? `${plural(found.total, "record")} for “${found.query}”${only ? `, ${meta(only).plural.toLowerCase()} only` : ""}.` : null }),
        h("div", { class: "row wrap" }, h("div", { class: "grow" }, box),
          only ? button("Every kind", { onclick: () => setQuery({ type: null }) }) : null),
        results);
    },
  });
}
