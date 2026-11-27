// Check the places where the keyboard has most to do: the skip link, a record's parts, the
// working behind a score (a dialog that keeps the focus and gives it back), and the portfolio
// chart, whose table holds every point; and the picture of how a record is connected.
// Run with: node scripts/keyboard-check.mjs
import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";

const demo = await startDemo();
const page = await openBrowser();
const fail = (message) => {
  console.error(`✗ ${message}`);
  process.exitCode = 1;
};
const pass = (message) => console.log(`✓ ${message}`);
const active = () => page.evaluate(`(() => { const el = document.activeElement;
  return el ? { tag: el.tagName, cls: el.className?.baseVal ?? el.className, text: (el.getAttribute("aria-label") ?? el.textContent).trim().slice(0, 60),
    inDialog: Boolean(el.closest("[role=dialog]")), current: el.getAttribute("aria-current") } : null; })()`);
const tabUntil = async (test, what, most = 80) => {
  for (let i = 0; i < most; i += 1) {
    await page.press("Tab");
    const el = await active();
    if (el && test(el)) return el;
  }
  throw new Error(`Tab never reached ${what}`);
};
try {
  await page.size(1360, 900);
  await signInAs(page, demo.base, "res_steward");
  const ref = await page.evaluate(`fetch("/api/v1/applications?q=Specimen+Tracker").then((r) => r.json()).then((b) => b.data[0].ref)`);
  await page.goto(`${demo.base}/applications/${ref}`);
  await page.settled();

  // The skip link comes before anything else that takes the focus, and Enter on it puts the
  // focus in the page. (On arrival the app puts the focus on the page's heading.)
  const first = await page.evaluate(`document.querySelector('a[href], button, input, select, textarea, [tabindex="0"]')?.className`);
  if (first !== "skip-link") fail(`the first thing to take the focus is ${first}, not the skip link`);
  else {
    await page.evaluate(`document.querySelector(".skip-link").focus()`);
    await page.press("Enter");
    await page.waitFor(`document.activeElement?.id === "main"`, "the skip link to move the focus");
    pass("the skip link comes first and takes the focus to the page");
  }

  // A record's parts are links, reached in order, and Enter opens one.
  const tab = await tabUntil((el) => el.cls === "tab" && el.text === "Scores", "the Scores part");
  await page.press("Enter");
  await page.waitFor(`location.search.includes("tab=scores")`, "the Scores part to open");
  await page.settled();
  const now = await page.evaluate(`document.querySelector(".tab[aria-current=page]")?.textContent`);
  if (now !== "Scores") fail(`after Enter on ${tab.text}, ${now} is the current part`);
  else pass("a record's parts are reached with Tab and opened with Enter");

  // The working behind a score: Enter opens it, Tab stays inside, Escape gives the focus back.
  await page.goto(`${demo.base}/applications/${ref}`);
  await page.settled();
  const opener = await tabUntil((el) => el.cls === "scorecard-item", "a score");
  await page.press("Enter");
  await page.waitFor(`document.querySelector("[role=dialog]")`, "the working to open");
  await page.waitFor(`document.activeElement?.closest("[role=dialog]")`, "the focus to move into the working");
  const stops = await page.evaluate(`document.querySelector("[role=dialog]").querySelectorAll("a[href], button").length`);
  let escaped = false;
  for (let i = 0; i < stops + 2; i += 1) {
    await page.press("Tab");
    if (!(await active())?.inDialog) escaped = true;
  }
  for (let i = 0; i < 2; i += 1) {
    await page.press("Tab", { shift: true });
    if (!(await active())?.inDialog) escaped = true;
  }
  if (escaped) fail("Tab left the working while it was open");
  await page.press("Escape");
  await page.waitFor(`!document.querySelector("[role=dialog]")`, "the working to close");
  const back = await active();
  if (back?.cls !== "scorecard-item" || back.text !== opener.text) fail(`Escape left the focus on ${back?.text}`);
  else pass(`the working behind "${opener.text.split("\n")[0]}" keeps the focus and gives it back`);

  // The portfolio chart: its points stay out of the way of Tab, and its table lists every one.
  await signInAs(page, demo.base, "portfolio");
  await page.goto(`${demo.base}/portfolio`);
  await page.settled();
  const chart = await page.evaluate(`(() => {
    const points = [...document.querySelectorAll("svg.portfolio-chart a")];
    const rows = document.querySelectorAll("#portfolio-table tbody tr a.cell-main");
    return { points: points.length, rows: rows.length, out: points.every((a) => a.tabIndex === -1) };
  })()`);
  if (!chart.points) fail("the chart drew no points");
  else if (!chart.out) fail("the chart's points are in the Tab order");
  else if (chart.rows !== chart.points) fail(`the chart has ${chart.points} points and its table ${chart.rows}`);
  else pass(`the chart's ${chart.points} points are all in its table, each a link`);

  // The picture of how a record is connected: every record in it can be reached and named,
  // the list beside it is complete, and opening a neighbor keeps the focus where it was.
  await signInAs(page, demo.base, "architect");
  const hub = await page.evaluate(`fetch("/api/v1/applications?q=Research+Data+Warehouse").then((r) => r.json()).then((b) => b.data[0].ref)`);
  const graph = await page.evaluate(`fetch("/api/v1/graph/${hub}").then((r) => r.json()).then((b) => b.data)`);
  await page.goto(`${demo.base}/graph/${hub}`);
  await page.waitFor(`document.querySelector("svg.graph")`, "the picture");
  const listed = await page.evaluate(`document.querySelectorAll(".glist > li").length`);
  if (listed !== graph.count) fail(`the list has ${listed} records and the answer ${graph.count}`);
  const reach = await page.evaluate(`(() => {
    const all = [...document.querySelectorAll('svg.graph [role="link"], svg.graph [role="button"]')];
    return { count: all.length, focusable: all.every((el) => el.tabIndex === 0 && el.getAttribute("aria-label")) };
  })()`);
  if (!reach.count || !reach.focusable) fail("not every record in the picture can be reached and named");
  await page.evaluate(`document.querySelector(".gexpand").focus()`);
  await page.press("Enter");
  await page.waitFor(`document.querySelector('.gexpand[aria-expanded="true"]')`, "the neighbor to open");
  const kept = await page.evaluate(`document.activeElement?.getAttribute("aria-expanded")`);
  if (kept !== "true") fail(`after opening, the focus is not on the button that opened it (${kept})`);
  if (!(await page.evaluate(`Boolean(document.querySelector(".glist-more"))`))) fail("the list did not open with the picture");
  await page.press(" ");
  await page.waitFor(`!document.querySelector('.gexpand[aria-expanded="true"]')`, "the neighbor to close");
  const target = await page.evaluate(`(() => { const el = document.querySelector('svg.graph [role="link"]'); el.focus(); return el.getAttribute("aria-label"); })()`);
  await page.press("Enter");
  await page.waitFor(`location.pathname.startsWith("/graph/") && location.pathname !== "/graph/${hub}"`, "the record to move to the middle");
  // The old picture stays until the new one is drawn: wait for the middle to change.
  const before = JSON.stringify(`Application ${hub}: ${graph.center.name}`);
  await page.waitFor(`(() => { const t = document.querySelector('.gnode[data-ring="0"] title')?.textContent; return t && t !== ${before}; })()`, "the new picture");
  const middle = await page.evaluate(`document.querySelector('.gnode[data-ring="0"] title').textContent`);
  if (!target.startsWith(middle)) fail(`${target} was chosen and ${middle} is in the middle`);
  else pass(`the picture of ${hub}: ${reach.count} things reachable by keyboard, ${listed} records listed`);
} finally {
  await page.close?.();
  await demo.stop?.();
}
