import assert from "node:assert/strict";
import { test } from "node:test";

import { layout, VIEW } from "../../src/appwren/web/static/js/core/graph-layout.js";

const record = (ref, type = "system") => ({ ref, name: `Record ${ref}`, type });
const graph = (groups) => ({ center: record("APP-0001"), groups });

test("the record is in the middle with a neighbor for each connection", () => {
  const found = layout(graph([{ key: "depends_on:out", label: "Depends on", records: [record("APP-0002"), record("VEN-0001", "vendor")] },
    { key: "components", label: "Its components", records: [record("CMP-0001", "component")] }]));
  assert.equal(found.nodes.length, 4);
  assert.deepEqual([found.nodes[0].x, found.nodes[0].y, found.nodes[0].ring], [VIEW.width / 2, VIEW.height / 2, 0]);
  assert.deepEqual(found.edges.map((edge) => edge.to), ["depends_on:out/APP-0002", "depends_on:out/VEN-0001", "components/CMP-0001"]);
  assert.deepEqual(found.labels.map((label) => label.text), ["Depends on", "Its components"]);
});

test("everything stays inside the picture and nothing sits on anything else", () => {
  const many = (prefix, count) => Array.from({ length: count }, (_, index) => record(`${prefix}-${String(index + 1).padStart(4, "0")}`));
  const base = graph([{ key: "a", label: "A", records: many("APP", 6) }, { key: "b", label: "B", records: many("CMP", 5) }, { key: "c", label: "C", records: many("TEC", 4) }]);
  const opened = Object.fromEntries(["APP-0001", "APP-0002", "CMP-0001", "TEC-0004"].map((ref) => [ref, { center: record(ref), groups: [{ key: "x", label: "X", records: many(`T${ref.slice(-1)}`.padEnd(2, "P"), 5) }] }]));
  const found = layout(base, opened);
  assert.ok(found.nodes.some((node) => node.ring === 2));
  for (const node of found.nodes) {
    assert.ok(node.x >= VIEW.node.width / 2 && node.x <= VIEW.width - VIEW.node.width / 2, `${node.id} is inside across`);
    assert.ok(node.y >= VIEW.node.height / 2 && node.y <= VIEW.height - VIEW.node.height / 2, `${node.id} is inside down`);
  }
  for (const [index, a] of found.nodes.entries()) {
    for (const b of found.nodes.slice(index + 1)) {
      const apart = Math.abs(a.x - b.x) >= VIEW.node.width || Math.abs(a.y - b.y) >= VIEW.node.height;
      assert.ok(apart, `${a.id} and ${b.id} do not overlap`);
    }
  }
});

test("what does not fit is counted, so the list beside it can say the rest", () => {
  const records = Array.from({ length: 9 }, (_, index) => record(`APP-00${index + 10}`));
  const found = layout(graph([{ key: "serves:in", label: "Serves", records }]));
  const more = found.nodes.find((node) => node.more);
  assert.equal(more.more, 3);
  assert.equal(found.nodes.filter((node) => node.ring === 1 && node.record).length, 6);
  // With more groups than there is room for, each shows fewer, and still counts the rest.
  const groups = Array.from({ length: 8 }, (_, index) => ({ key: `g${index}`, label: `Group ${index}`, records }));
  const tight = layout(graph(groups));
  assert.ok(tight.nodes.every((node) => node.y >= VIEW.node.height / 2 && node.y <= VIEW.height - VIEW.node.height / 2));
  assert.ok(tight.nodes.filter((node) => node.more).every((node) => node.more >= 4));
});

test("an opened neighbor shows its own neighbors, and none of them twice", () => {
  const base = graph([{ key: "depends_on:out", label: "Depends on", records: [record("APP-0002")] }]);
  const opened = { "APP-0002": { center: record("APP-0002"), groups: [
    { key: "serves:in", label: "Serves", records: [record("APP-0001"), record("CAP-0001", "capability")] },
    { key: "components", label: "Its components", records: [record("CMP-0001", "component"), record("CAP-0001", "capability")] }] } };
  const found = layout(base, opened);
  const beyond = found.nodes.filter((node) => node.ring === 2);
  assert.deepEqual(beyond.map((node) => node.record.ref), ["CAP-0001", "CMP-0001"]);
  assert.deepEqual(beyond.map((node) => node.via), ["Serves", "Its components"]);
  assert.ok(found.edges.some((edge) => edge.from === "depends_on:out/APP-0002" && edge.to.endsWith(">CMP-0001")));
});

test("a record with no connections is alone in the middle", () => {
  const found = layout(graph([]));
  assert.equal(found.nodes.length, 1);
  assert.equal(found.edges.length, 0);
});
