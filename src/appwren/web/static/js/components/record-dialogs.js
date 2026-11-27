// Dialogs on a record's page that few people open: what a component is built on, a
// technology's releases, and what a contract covers. Loaded when someone opens one.

import { get, put } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { date } from "../core/format.js";
import { label } from "../core/lookups.js";
import { banner, field, select, submit } from "./form.js";
import { openOverlay } from "./overlay.js";
import { recordChip } from "./record.js";
import { toast } from "./toast.js";
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
