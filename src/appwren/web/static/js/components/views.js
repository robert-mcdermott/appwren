// Saved views: a list as someone filtered it, kept under a name. A view holds the question,
// never the answer: whoever opens a shared one sees only what they may see.

import { del, get, post } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { navigate } from "../core/router.js";
import { can } from "../core/session.js";
import { banner, checkbox, field, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { toast } from "./toast.js";
import { emptyState } from "./ui.js";

const mayShare = () => can("steward") || can("architect") || can("read_all") || can("admin");

function saveOne(path, query, onDone) {
  openOverlay({ title: "Save this view", kind: "dialog", render: (body, footer, close) => {
    const name = field("Name", { required: true, hint: "As it will be listed, such as “Tier 1, not confirmed”." });
    const shared = mayShare() ? checkbox("Share it with everyone", { hint: "Everyone sees it listed, and each sees only what they may." }) : null;
    const problem = banner();
    const save = button("Save", { kind: "btn-primary" });
    save.addEventListener("click", async () => {
      const done = await submit({ button: save, banner: problem, fields: { name },
        run: () => post("/api/v1/views", { name: name.input.value, path, query, shared: shared ? shared.input.checked : false }) });
      if (done) {
        close();
        toast(`Saved as “${done.data.name}”.`);
        onDone?.();
      }
    });
    body.append(h("div", { class: "stack" }, problem, name.node, shared?.node ?? null,
      h("p", { class: "subtle" }, query ? `Keeps these filters: ${decodeURIComponent(query).replace(/&/g, ", ")}` : "Keeps the list as it is, with no filters.")));
    footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
    footer.hidden = false;
  } });
}

/** A button that opens the saved views of this list, and saves the current one. */
export function viewsButton(path = window.location.pathname) {
  return button("Views", { iconName: "list", onclick: () => openOverlay({ title: "Saved views", subtitle: "Of this list", render: async (body, footer, close) => {
    const draw = async () => {
      const rows = (await get("/api/v1/views", { path }, { fresh: true })).data;
      const current = window.location.search.replace(/^\?/, "");
      body.replaceChildren(rows.length ? h("ul", { class: "found-list" }, rows.map((row) => h("li", {},
        h("div", { class: "grow" }, h("a", { class: "cell-main", href: row.href, onclick: (event) => {
          event.preventDefault();
          close();
          navigate(row.href);
        } }, row.name),
        h("div", { class: "cell-sub" }, [row.shared ? "Shared" : "Yours", row.mine ? null : `by ${row.by}`].filter(Boolean).join(" · "))),
        row.can_change ? button("Delete", { kind: "btn-sm btn-ghost", "aria-label": `Delete ${row.name}`, onclick: async () => {
          await del(`/api/v1/views/${row.id}`);
          toast(`“${row.name}” was deleted.`);
          draw();
        } }) : null)))
        : emptyState({ iconName: "list", title: "No saved views yet", text: "Filter the list as you want it, then save it here to come back to it." }));
      footer.replaceChildren(h("div", { class: "row" }, button("Save this view", { kind: "btn-primary", onclick: () => {
        close();
        saveOne(path, current);
      } }), button("Close", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    };
    await draw();
  } }) });
}
