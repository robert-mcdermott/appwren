// Campaigns: the owners of the applications in a unit asked to confirm their records, or to
// assess their applications, by a date. Whoever runs one sees who has done it, unit by unit;
// whoever is asked sees what is theirs, and does it on the application's own page.

import { get, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, plural } from "../core/format.js";
import { options, unitOptions, units, vocabularies } from "../core/lookups.js";
import { navigate, query, setQuery } from "../core/router.js";
import { can } from "../core/session.js";
import { segments } from "../components/charts.js";
import { recordChip } from "../components/record.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { closeOverlay, confirmAction, openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

const STATUS = { open: ["Open", "info"], closed: ["Closed", ""], cancelled: ["Cancelled", ""] };
const ITEM = { pending: ["To do", "warn"], done: ["Done", "ok"], excused: ["Excused", ""] };
const ASKS = { confirm: "Confirm each record", assess: "Assess each application" };
const statusPill = (campaign) => (campaign.late ? pill("Past its date", "danger") : pill(...STATUS[campaign.status]));

function bar(percent, label) {
  const fill = h("i");
  fill.style.setProperty("width", `${percent}%`);
  return h("span", { class: "coverage-bar", role: "img", "aria-label": label }, fill);
}

function scopeText(campaign) {
  const where = campaign.unit ? `${campaign.unit.name} and beneath it` : "the whole organization";
  const limits = [campaign.tiers.length ? `tiers ${campaign.tiers.join(", ")}` : null,
    campaign.stages.length ? `${plural(campaign.stages.length, "stage")}` : null].filter(Boolean);
  return limits.length ? `${where}, ${limits.join(" and ")}` : where;
}

export function campaignList(main) {
  return show(main, {
    title: "Campaigns",
    load: async () => (await get("/api/v1/campaigns", null, { fresh: true })).data,
    view: (rows) => h("div", { class: "stack-lg" },
      pageHeader({ eyebrow: "Portfolio", title: "Campaigns",
        lede: "Ask the owners of the applications in a unit to confirm their records, or to assess their applications, by a date. Each is done on the application's own page, and the campaign sees it.",
        actions: can("steward") ? button("Start a campaign", { kind: "btn-primary", iconName: "plus", onclick: startOne }) : null }),
      rows.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Campaign"), h("th", { scope: "col" }, "Asks"), h("th", { scope: "col" }, "Due"),
          h("th", { scope: "col" }, "Done"), h("th", { scope: "col" }, "Status"))),
        h("tbody", {}, rows.map((item) => h("tr", {},
          h("td", {}, h("a", { class: "cell-main", href: `/campaigns/${item.ref}` }, item.name),
            h("div", { class: "cell-sub" }, `${item.ref} · ${scopeText(item)}`)),
          h("td", {}, ASKS[item.kind]),
          h("td", {}, date(item.due_on)),
          h("td", {}, h("div", { class: "stack-sm" }, `${item.progress.done} of ${item.progress.total - item.progress.excused}`,
            bar(item.progress.percent, `${item.progress.percent}% done`))),
          h("td", {}, statusPill(item))))))))
        : card({}, emptyState({ iconName: "bell", title: "No campaigns yet",
          text: can("steward") ? "Start one to ask the owners in a unit to confirm or assess by a date, and see coverage by unit as they do."
            : "What you have been asked to do is on your Home page." }))),
  });
}

function startOne() {
  openOverlay({ title: "Start a campaign", render: async (body, footer) => {
    const [unitIndex, vocab] = await Promise.all([units(), vocabularies()]);
    const kind = select("What to ask", [["confirm", "Confirm that each record is right"], ["assess", "Assess each application"]]);
    const name = field("Name", { required: true, hint: "As people will see it, such as “Record confirmation, spring 2027”." });
    const due = field("Due by", { type: "date", required: true });
    const unit = select("The applications of", unitOptions(unitIndex.tree, { blank: can("manage") ? "The whole organization" : "Choose a unit" }),
      { hint: "The unit and everything beneath it." });
    const tiers = (vocab.tiers ?? []).map((tier) => ({ key: tier.key, box: checkbox(tier.label) }));
    const stages = (vocab.lifecycle ?? []).filter((stage) => !["retired", "archived"].includes(stage.key))
      .map((stage) => ({ key: stage.key, box: checkbox(stage.label) }));
    const message = field("A note to those asked", { type: "textarea", rows: 2, hint: "Optional. Why now, or what to look at." });
    const who = h("div", { class: "muted", "aria-live": "polite" });
    const problem = banner();
    const save = button("Start, and tell those asked", { kind: "btn-primary" });
    const values = () => ({ kind: kind.input.value, name: name.input.value, due_on: due.input.value, message: message.input.value || null,
      org_unit_id: Number(unit.input.value) || null,
      tiers: tiers.filter((each) => each.box.input.checked).map((each) => each.key),
      stages: stages.filter((each) => each.box.input.checked).map((each) => each.key) });
    const sync = async () => {
      try {
        const found = (await post("/api/v1/campaigns/preview", { ...values(), name: "preview", due_on: "2999-01-01" })).data;
        who.replaceChildren(found.applications
          ? h("p", {}, `This would ask ${plural(found.people, "person", "people")} about ${plural(found.applications, "application")}.`,
            found.nobody.length ? ` ${plural(found.nobody.length, "application")} ${found.nobody.length === 1 ? "has" : "have"} nobody to ask: ` : "",
            found.nobody.map((app, index) => [index ? ", " : "", h("a", { href: `/applications/${app.ref}` }, app.name)]))
          : h("p", {}, "No application in service matches."));
      } catch (error) {
        who.replaceChildren(h("p", {}, error.fields?.org_unit_id ?? error.detail ?? ""));
      }
    };
    for (const each of [kind.input, unit.input, ...tiers.map((t) => t.box.input), ...stages.map((s) => s.box.input)]) each.addEventListener("change", sync);
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, fields: { kind, name, due_on: due, org_unit_id: unit }, banner: problem,
        run: () => post("/api/v1/campaigns", values()) });
      if (done) {
        closeOverlay();
        toast(`${done.data.ref} is started.`);
        navigate(`/campaigns/${done.data.ref}`);
      }
    });
    body.append(h("div", { class: "stack" }, problem, kind.node, name.node, due.node, unit.node,
      h("fieldset", { class: "fieldset" }, h("legend", {}, "Only these tiers"), h("div", { class: "row wrap" }, tiers.map((each) => each.box.node)),
        h("div", { class: "hint subtle" }, "None ticked means every tier.")),
      h("fieldset", { class: "fieldset" }, h("legend", {}, "Only these stages"), h("div", { class: "row wrap" }, stages.map((each) => each.box.node)),
        h("div", { class: "hint subtle" }, "None ticked means every stage in service.")),
      message.node, who));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: closeOverlay })));
    footer.hidden = false;
    await sync();
  } });
}

function excuseOne(campaign, item, reload) {
  openOverlay({ title: "Excuse it from this campaign", subtitle: `${item.application.ref} · ${item.application.name}`, kind: "dialog", render: (body, footer, close) => {
    const reason = field("Why", { type: "textarea", rows: 3, required: true, hint: "Kept with the campaign. Say why it need not be done, such as that it is about to be retired." });
    const problem = banner();
    const save = button("Excuse it", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { reason },
        run: () => post(`/api/v1/campaigns/${campaign.ref}/items/${item.id}/excuse`, { reason: reason.input.value }) });
      if (done) {
        close();
        toast("Excused.");
        reload();
      }
    });
    body.append(h("div", { class: "stack" }, problem, reason.node));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

function itemsTable(campaign, reload) {
  const rows = campaign.items;
  if (!rows.length) return h("p", { class: "muted pad" }, "Nothing here.");
  const doIt = (item) => (campaign.kind === "assess" ? h("a", { class: "btn btn-sm", href: `/applications/${item.application.ref}/assess` }, "Assess it")
    : h("a", { class: "btn btn-sm", href: `/applications/${item.application.ref}` }, "Confirm it"));
  return h("div", { class: "table-wrap" }, h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Application"), h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Asked"),
      h("th", { scope: "col" }, "Status"), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Action")))),
    h("tbody", {}, rows.map((item) => h("tr", {},
      h("td", {}, recordChip(item.application)),
      h("td", {}, item.unit ?? ""),
      h("td", {}, item.asked ? item.asked.name : h("span", { class: "text-danger" }, "Nobody to ask")),
      h("td", {}, h("div", { class: "stack-sm" }, pill(...ITEM[item.status]),
        item.status === "done" ? h("span", { class: "cell-sub" }, `${item.done_by ?? ""}, ${date(item.done_on)}`) : null,
        item.status === "excused" ? h("span", { class: "cell-sub" }, item.excuse) : null)),
      h("td", { class: "row-sm" }, item.status === "pending" && campaign.status === "open"
        ? [item.mine ? doIt(item) : null,
          campaign.can_run ? button("Excuse", { kind: "btn-sm btn-ghost", "aria-label": `Excuse ${item.application.name}`, onclick: () => excuseOne(campaign, item, reload) }) : null]
        : null))))));
}

export function campaignPage(main, params) {
  const params2 = query();
  const filters = { unit: params2.get("unit") || null, status: params2.get("status") || null, mine: params2.get("mine") === "1" };
  return show(main, {
    title: params.ref,
    load: async () => (await get(`/api/v1/campaigns/${params.ref}`, { unit: filters.unit, status: filters.status, mine: filters.mine || null }, { fresh: true })).data,
    view: (campaign, reload) => {
      const act = (path, done) => async () => {
        await post(`/api/v1/campaigns/${campaign.ref}/${path}`, {});
        toast(done);
        reload();
      };
      const remind = button("Remind those still to do it", { onclick: async () => {
        const told = (await post(`/api/v1/campaigns/${campaign.ref}/remind`, {})).data.told;
        toast(told ? `Reminded ${plural(told, "person", "people")}.` : "There is nobody left to remind.");
      } });
      const progress = campaign.progress;
      const nobody = campaign.items.filter((item) => !item.asked && item.status === "pending").length;
      const unitName = filters.unit ? campaign.coverage.find((row) => String(row.unit.id) === String(filters.unit))?.unit.name : null;
      const statusTabs = [["", "Everything"], ["pending", "To do"], ["done", "Done"], ["excused", "Excused"]];
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/campaigns" }, icon("chevron-left", "icon icon-sm"), "Campaigns"),
        pageHeader({ eyebrow: `${ASKS[campaign.kind]} · ${campaign.ref}`, title: campaign.name, lede: campaign.message,
          actions: campaign.can_run && campaign.status === "open" ? h("div", { class: "row-sm wrap" }, remind,
            button("Close", { onclick: () => confirmAction({ title: "Close this campaign?", text: "What has been done is kept. Nobody else is asked or reminded.", confirmLabel: "Close it", run: act("close", "Closed.") }) }),
            button("Cancel it", { kind: "btn-ghost", onclick: () => confirmAction({ title: "Cancel this campaign?", text: "For one started in error. What has been done stays on each application's record.", confirmLabel: "Cancel it", danger: true, run: act("cancel", "Cancelled.") }) })) : null }),
        h("div", { class: "row-sm wrap" }, statusPill(campaign), h("span", { class: "muted" },
          `${scopeText(campaign)} · due ${date(campaign.due_on)} · started by ${campaign.started_by} on ${date(campaign.started_on)}`,
          campaign.ended_on ? ` · ended ${date(campaign.ended_on)}` : "")),
        nobody && campaign.can_run ? alert("warn", icon("alert"), h("div", {}, h("strong", {}, `${plural(nobody, "application")} ${nobody === 1 ? "has" : "have"} nobody to ask. `),
          "Name who is accountable for each, or excuse it from the campaign.")) : null,
        card({ title: `${progress.percent}% done` }, segments([
          { label: "done", value: progress.done, tone: "ok" }, { label: "to do", value: progress.pending, tone: "warn" },
          { label: "excused", value: progress.excused, tone: "none" }], { label: `${progress.done} of ${progress.total - progress.excused} done` })),
        card({ title: "Coverage by unit", flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table table-compact" },
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Unit"), h("th", { scope: "col" }, "Asked"), h("th", { scope: "col" }, "Done"), h("th", { scope: "col" }, "Coverage"))),
          h("tbody", {}, campaign.coverage.map((row) => h("tr", {},
            h("td", {}, h("a", { href: `/campaigns/${campaign.ref}?unit=${row.unit.id ?? "none"}` }, row.unit.name)),
            h("td", {}, String(row.total - row.excused)), h("td", {}, String(row.done)),
            h("td", {}, h("div", { class: "row-sm" }, bar(row.percent, `${row.percent}% of ${row.unit.name} done`), `${row.percent}%`)))))))),
        card({ title: unitName ? `In ${unitName}` : filters.mine ? "Asked of you" : "Every application", flush: true,
          actions: filters.unit || filters.mine ? h("a", { class: "btn btn-sm btn-ghost", href: `/campaigns/${campaign.ref}` }, "Show everything") : null },
        h("div", { class: "tabs pad-x", role: "tablist" }, statusTabs.map(([key, text]) => h("button", { type: "button", class: "tab", role: "tab",
          "aria-selected": String((filters.status ?? "") === key), onclick: () => setQuery({ status: key || null }, { replace: false }) }, text))),
        itemsTable(campaign, reload)));
    },
  });
}
