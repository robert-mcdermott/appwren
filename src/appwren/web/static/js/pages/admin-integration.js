// What other systems use. An administrator issues API tokens for a role and registers the
// addresses AppWren tells when something happens; a person makes tokens of their own.

import { del, get, patch, post } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { date, dateTime, relative, titleCase } from "../core/format.js";
import { unitOptions, units } from "../core/lookups.js";
import { banner, checkbox, field, select, submit } from "../components/form.js";
import { openOverlay } from "../components/overlay.js";
import { toast } from "../components/toast.js";
import { alert, card, emptyState, pageHeader, pill } from "../components/ui.js";
import { show } from "./page.js";

/** A secret shown once: what it is, the value to copy, and a warning that it will not be shown again. */
function once(title, label, secret, note) {
  openOverlay({
    title, kind: "dialog",
    render: (body, footer, shut) => {
      const value = h("input", { class: "input mono", readonly: true, value: secret, "aria-label": label, onfocus: (event) => event.target.select() });
      body.append(h("div", { class: "stack" },
        alert("warn", icon("alert"), h("div", {}, h("strong", {}, "Copy it now. "), "It is shown this once and cannot be read again.")),
        value, h("p", { class: "muted" }, note)));
      footer.replaceChildren(h("div", { class: "row" },
        button("Copy", { kind: "btn-primary", onclick: async () => {
          value.select();
          try {
            await navigator.clipboard.writeText(secret);
            toast("Copied.");
          } catch {
            toast("Select the text and copy it.");
          }
        } }),
        button("Done", { kind: "btn-ghost", onclick: shut })));
      footer.hidden = false;
    },
  });
}

export function adminTokens(main) {
  return show(main, {
    title: "API tokens",
    load: async () => {
      const [found, unitIndex] = await Promise.all([get("/api/v1/admin/tokens", null, { fresh: true }), units()]);
      return { ...found.data, unitIndex };
    },
    view: (data, reload) => {
      const issue = () => {
        const name = field("What it is for", { maxlength: 80, placeholder: "The reporting warehouse" });
        const role = select("Acts as", data.roles.map((key) => [key, titleCase(key)]), { value: "auditor",
          hint: "The role it holds. A token never administers." });
        const unit = select("For the unit", unitOptions(data.unitIndex.tree, { blank: "The whole organization" }),
          { hint: "A steward's or a leader's token is for one unit and those beneath it." });
        const reading = checkbox("Reading only", { checked: true, hint: "It may read what its role may, and change nothing." });
        const expires = field("Stops working on", { type: "date", hint: "Ninety days from today unless you choose another day, up to a year. Every token ends, so none is forgotten." });
        openOverlay({
          title: "Issue a token", subtitle: "Another system presents it instead of signing in. What it changes is recorded against its name.", kind: "dialog",
          render: (body, footer, shut) => {
            const problem = banner();
            const go = button("Issue it", { kind: "btn-primary" });
            go.addEventListener("click", async () => {
              const made = await submit({ button: go, banner: problem, fields: { name, role, org_unit_id: unit, expires_on: expires },
                run: () => post("/api/v1/admin/tokens", { name: name.input.value, role: role.input.value,
                  org_unit_id: Number(unit.input.value) || null, read_only: reading.input.checked, expires_on: expires.input.value || null }) });
              if (made) {
                shut();
                reload();
                once("The new token", "The token", made.data.token, "Send it with each request as the header: Authorization: Bearer, a space, and the token.");
              }
            });
            body.append(h("div", { class: "stack" }, problem, name.node, role.node, unit.node, reading.node, expires.node));
            footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: shut })));
            footer.hidden = false;
          },
        });
      };
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "API tokens", lede: "A token lets another system call the API with one role, for one unit if you choose, and for reading only unless you say otherwise. Give each the least it needs, and revoke it when it is no longer used.",
          actions: button("Issue a token", { kind: "btn-primary", iconName: "plus", onclick: issue }) }),
        data.tokens.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Token", "Acts as", "Last used", "Standing", ""].map((heading) => h("th", { scope: "col" }, heading || h("span", { class: "sr-only" }, "Actions"))))),
          h("tbody", {}, data.tokens.map((token) => h("tr", {},
            h("td", {}, h("span", { class: "cell-main" }, token.name), h("div", { class: "cell-sub mono" }, `${token.prefix}…`)),
            h("td", {}, titleCase(token.role), token.unit ? h("div", { class: "cell-sub" }, token.unit) : null,
              h("div", { class: "cell-sub" }, token.read_only ? "Reading only" : "Reads and changes")),
            h("td", { class: "nowrap" }, token.last_used_at ? relative(token.last_used_at) : h("span", { class: "subtle" }, "Never")),
            h("td", {}, token.revoked_at ? pill("Revoked") : token.expired ? pill("Expired", "warn")
              : h("div", { class: "row-sm wrap" }, pill("Working", "ok"), h("span", { class: "subtle" }, `until ${date(token.expires_on)}`))),
            h("td", {}, token.live ? button("Revoke", { kind: "btn-sm btn-ghost", "aria-label": `Revoke ${token.name}`, onclick: async () => {
              await del(`/api/v1/admin/tokens/${token.id}`);
              toast("The token was revoked. It no longer works.");
              reload();
            } }) : null)))))))
          : emptyState({ iconName: "key", title: "No token has been issued", text: "Issue one when a script or another system needs to read the portfolio, or keep records in it." }));
    },
  });
}

export function adminWebhooks(main) {
  return show(main, {
    title: "Webhooks",
    load: async () => (await get("/api/v1/admin/webhooks", null, { fresh: true })).data,
    view: (data, reload) => {
      const edit = (hook) => {
        const name = field("Name", { value: hook?.name ?? "", maxlength: 80, placeholder: "The service desk" });
        const url = field("Address", { type: "url", value: hook?.url ?? "", placeholder: "https://desk.example.org/hooks/appwren", hint: "It must start with https://." });
        const boxes = data.topics.map((topic) => ({ key: topic.key, box: checkbox(topic.label, { checked: hook ? hook.topics.includes(topic.key) : false }) }));
        const topicsProblem = h("div", { class: "error", role: "alert", hidden: true });
        const topics = { input: boxes[0].box.input, setError: (text) => {
          topicsProblem.hidden = !text;
          topicsProblem.textContent = text ?? "";
        } };
        openOverlay({
          title: hook ? "Change a webhook" : "Add a webhook", subtitle: "AppWren sends a small signed message to this address when something of the kind you choose happens.", kind: "drawer",
          render: (body, footer, shut) => {
            const problem = banner();
            const go = button(hook ? "Save" : "Add it", { kind: "btn-primary" });
            go.addEventListener("click", async () => {
              const values = { name: name.input.value, url: url.input.value, topics: boxes.filter((item) => item.box.input.checked).map((item) => item.key) };
              const saved = await submit({ button: go, banner: problem, fields: { name, url, topics },
                run: () => hook ? patch(`/api/v1/admin/webhooks/${hook.id}`, values) : post("/api/v1/admin/webhooks", values) });
              if (saved) {
                shut();
                reload();
                if (!hook) once("The signing secret", "The signing secret", saved.data.secret, "Give it to whoever runs the receiving system. They use it to check that each message came from here.");
              }
            });
            body.append(h("div", { class: "stack" }, problem, name.node, url.node,
              h("fieldset", {}, h("legend", {}, "Tell it when"), h("div", { class: "stack-sm" }, boxes.map((item) => item.box.node)), topicsProblem)));
            footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: shut })));
            footer.hidden = false;
          },
        });
      };
      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Webhooks", lede: "Tell another system when something happens here: a ticket when a record goes unconfirmed, a note in a channel when a decision is recorded. Messages say what changed, never what a record holds.",
          actions: button("Add a webhook", { kind: "btn-primary", iconName: "plus", onclick: () => edit(null) }) }),
        data.webhooks.length ? h("div", { class: "stack" }, data.webhooks.map((hook) => card({
          title: hook.name,
          actions: h("div", { class: "row-sm wrap" },
            button("Send a test", { kind: "btn-sm", "aria-label": `Send a test to ${hook.name}`, onclick: async (event) => {
              event.currentTarget.disabled = true;
              const sent = await post(`/api/v1/admin/webhooks/${hook.id}/test`);
              toast(sent.data.result === "Delivered" ? "The test was delivered." : `The test was not delivered. ${sent.data.result}`);
              reload();
            } }),
            button("Change", { kind: "btn-sm", "aria-label": `Change ${hook.name}`, onclick: () => edit(hook) }),
            button(hook.active && !hook.paused ? "Switch off" : "Switch on", { kind: "btn-sm btn-ghost", "aria-label": `${hook.active && !hook.paused ? "Switch off" : "Switch on"} ${hook.name}`, onclick: async () => {
              await patch(`/api/v1/admin/webhooks/${hook.id}`, { active: !(hook.active && !hook.paused) });
              reload();
            } }),
            button("Remove", { kind: "btn-sm btn-ghost", "aria-label": `Remove ${hook.name}`, onclick: async () => {
              await del(`/api/v1/admin/webhooks/${hook.id}`);
              toast("The webhook was removed.");
              reload();
            } })),
        }, h("div", { class: "stack" },
          h("div", { class: "row-sm wrap" }, !hook.active ? pill("Switched off") : hook.paused ? pill("Paused", "danger") : pill("On", "ok"),
            h("span", { class: "mono muted" }, hook.url)),
          h("p", { class: "subtle" }, `Told when: ${hook.topics.map((key) => data.topics.find((topic) => topic.key === key)?.label ?? key).join("; ")}.`),
          hook.last_status ? h("p", { class: hook.last_status === "Delivered" ? "muted" : "error" },
            hook.last_status === "Delivered" ? `Last delivered ${relative(hook.last_delivered_at)}.` : hook.last_status) : h("p", { class: "muted" }, "Nothing has been sent yet."),
          hook.deliveries.length ? h("div", { class: "table-wrap" }, h("table", { class: "table" },
            h("thead", {}, h("tr", {}, ["Event", "When", "Standing", "Tries"].map((heading) => h("th", { scope: "col" }, heading)))),
            h("tbody", {}, hook.deliveries.map((item) => h("tr", {},
              h("td", { class: "mono" }, item.topic), h("td", { class: "nowrap" }, dateTime(item.created_at)),
              h("td", {}, item.status === "sent" ? pill("Delivered", "ok") : item.status === "failed" ? pill("Given up", "danger") : pill("Waiting", "warn"),
                item.last_error ? h("div", { class: "cell-sub" }, item.last_error) : null),
              h("td", { class: "numeric" }, String(item.attempts))))))) : null))))
          : emptyState({ iconName: "link", title: "No webhook is set up", text: "Add one when another system should hear about decisions, stage changes, or lapses as they happen." }));
    },
  });
}

export function myTokens(main) {
  return show(main, {
    title: "Your API tokens",
    narrow: true,
    load: async () => (await get("/api/v1/tokens", null, { fresh: true })).data,
    view: (data, reload) => {
      const make = () => {
        const name = field("What it is for", { maxlength: 80, placeholder: "My assistant" });
        const expires = field("Stops working on", { type: "date", hint: "Ninety days from today unless you choose another day, up to a year." });
        openOverlay({
          title: "Make a token", subtitle: "It acts as you: it reads what you may, and proposes changes for someone who keeps the application to accept. It changes nothing itself.", kind: "dialog",
          render: (body, footer, shut) => {
            const problem = banner();
            const go = button("Make it", { kind: "btn-primary" });
            go.addEventListener("click", async () => {
              const made = await submit({ button: go, banner: problem, fields: { name, expires_on: expires },
                run: () => post("/api/v1/tokens", { name: name.input.value, expires_on: expires.input.value || null }) });
              if (made) {
                shut();
                reload();
                once("Your new token", "The token", made.data.token, "Give it to the assistant or script, for example as APPWREN_TOKEN for appwren tools serve. It is sent as the header: Authorization: Bearer, a space, and the token.");
              }
            });
            body.append(h("div", { class: "stack" }, problem, name.node, expires.node));
            footer.replaceChildren(h("div", { class: "row" }, go, button("Cancel", { kind: "btn-ghost", onclick: shut })));
            footer.hidden = false;
          },
        });
      };
      return h("div", { class: "stack-lg" },
        h("a", { class: "back-link", href: "/account" }, icon("chevron-left", "icon icon-sm"), "Your account"),
        pageHeader({ title: "Your API tokens", lede: "A token of your own lets an AI assistant or a script of yours read AppWren as you, and propose changes. Revoke it when it is no longer used.",
          actions: button("Make a token", { kind: "btn-primary", iconName: "plus", onclick: make }) }),
        data.tokens.length ? card({ flush: true }, h("div", { class: "table-wrap" }, h("table", { class: "table" },
          h("thead", {}, h("tr", {}, ["Token", "Last used", "Standing", ""].map((heading) => h("th", { scope: "col" }, heading || h("span", { class: "sr-only" }, "Actions"))))),
          h("tbody", {}, data.tokens.map((token) => h("tr", {},
            h("td", {}, h("span", { class: "cell-main" }, token.name), h("div", { class: "cell-sub mono" }, `${token.prefix}…`)),
            h("td", { class: "nowrap" }, token.last_used_at ? relative(token.last_used_at) : h("span", { class: "subtle" }, "Never")),
            h("td", {}, token.revoked_at ? pill("Revoked") : token.expired ? pill("Expired", "warn")
              : h("div", { class: "row-sm wrap" }, pill("Working", "ok"), h("span", { class: "subtle" }, `until ${date(token.expires_on)}`))),
            h("td", {}, token.live ? button("Revoke", { kind: "btn-sm btn-ghost", "aria-label": `Revoke ${token.name}`, onclick: async () => {
              await del(`/api/v1/tokens/${token.id}`);
              toast("The token was revoked. It no longer works.");
              reload();
            } }) : null)))))))
          : emptyState({ iconName: "key", title: "You have no tokens", text: "Make one when an assistant or a script of yours needs to read AppWren." }));
    },
  });
}
