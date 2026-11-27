// Dialogs on a record's page that few people open: what a component is built on, a
// technology's releases, what a contract covers, the capabilities an application serves, the
// people named on it, and what it is called elsewhere. Loaded when someone opens one.

import { get, patch, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { label } from "../core/lookups.js";
import { can } from "../core/session.js";
import { banner, checkbox, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { peoplePicker } from "./people-picker.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
import { card } from "./ui.js";
import { recordFinder } from "../pages/record.js";

export function editCovered(record, ctx) {
  const rows = record.applications.map((a) => ({ ref: a.ref, name: a.name, licenses_used: a.licenses_used ?? "" }));
  openOverlay({
    title: "What it covers",
    subtitle: `${record.ref} · ${record.name}`,
    render: (body, footer, close) => {
      const list = h("div", { class: "stack-sm" });
      const problem = banner();
      const draw = () => {
        list.replaceChildren(...(rows.length ? rows.map((row, index) => {
          const used = h("input", { class: "input", type: "number", min: 0, step: 1, value: row.licenses_used, placeholder: "Licenses it uses", "aria-label": `Licenses ${row.name} uses` });
          used.addEventListener("input", () => {
            row.licenses_used = used.value;
          });
          return h("div", { class: "owner-row" }, h("div", { class: "grow" }, recordChip({ ...row, type: "application" }, { link: false })), used,
            button("Remove", { kind: "btn-ghost btn-sm", onclick: () => {
              rows.splice(index, 1);
              draw();
            } }));
        }) : [h("p", { class: "muted" }, "Nothing yet.")]));
      };
      draw();
      const finder = recordFinder("application", { exclude: (r) => rows.some((row) => row.ref === r.ref), onPick: (r) => {
        rows.push({ ref: r.ref, name: r.name, licenses_used: "" });
        draw();
        finder.refresh();
      } });
      const save = button("Save", { kind: "btn-primary" });
      save.addEventListener("click", async () => {
        const done = await submit({ button: save, banner: problem,
          run: () => put(`/api/v1/contracts/${record.ref}/applications`, { applications: rows.map((row) => ({ application: row.ref,
            licenses_used: row.licenses_used === "" ? null : Number(row.licenses_used) })) }) });
        if (done) {
          close();
          toast("Saved.");
          ctx.reload();
        }
      });
      body.append(h("div", { class: "stack-lg" }, problem,
        h("p", { class: "muted" }, "Each application the contract covers, and how many of its licenses that application uses. Use against what was bought is one of the things an application's cost is judged by."),
        list, h("div", { class: "field" }, h("div", { class: "label" }, "Add an application"), finder.node)));
      footer.replaceChildren(h("div", { class: "row" }, save, button("Cancel", { kind: "btn-ghost", onclick: close })));
      footer.hidden = false;
    },
  });
}

export function editTechnologies(record, ctx) {
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

export function editReleases(record, ctx) {
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

export function editCapabilities(record, ctx) {
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

export function editPeople(record, ctx) {
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

export function editExternal(record, ctx) {
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
