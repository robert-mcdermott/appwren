#!/usr/bin/env node
// The picture shown when a link to the repository or the product site is shared: AppWren's
// mark and name, what it is, and the demo's portfolio chart. 1280 by 640 pixels, as GitHub
// asks for a repository's social preview.
//
// It builds a demo organization, signs in as its portfolio manager, and takes the portfolio
// chart as the app draws it. The chart is laid out beside the words on a page of its own that
// carries the app's stylesheets, so it keeps the app's colors and stays sharp. (The app serves
// them for its own pages only, so they are read here and written into the page.)
//
//   node scripts/social-preview.mjs          writes .github/social-preview.png
//
// Upload the picture on GitHub under Settings, General, Social preview. The product site
// copies it and names it in each page's preview. Run it again when the chart or the brand changes.
//
// Development use only: the demo is built in a temporary directory and removed afterwards.

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { openBrowser } from "./lib/browser.mjs";
import { signInAs, startDemo } from "./lib/demo-server.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, ".github", "social-preview.png");
const [WIDTH, HEIGHT] = [1280, 640];
const wordmark = readFileSync(join(root, "src/appwren/web/static/img/wren-wordmark.svg"), "utf8")
  .replace(/^<svg /, '<svg class="og-wordmark" aria-hidden="true" ');

const SHEETS = ["tokens", "palettes", "base", "components", "pages"];

const page = (styles, chart) => `<!doctype html>
<html lang="en" data-palette="wren">
<head>
<meta charset="utf-8">
<style>${styles}</style>
<style>
  :root { color-scheme: light; }
  html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; overflow: hidden; }
  body { background: var(--bg); font-family: var(--font); color: var(--text); }
  .og { box-sizing: border-box; height: 100%; display: grid; grid-template-columns: 500px 1fr; gap: 36px;
        align-items: center; padding: 0 40px 0 64px; border-top: 10px solid var(--accent); }
  .og-words { display: flex; flex-direction: column; gap: 26px; }
  .og-wordmark { height: 76px; width: calc(76px * 250 / 64); display: block; align-self: flex-start; margin-left: -8px; }
  .og h1 { margin: 0; font-size: 48px; line-height: 1.1; font-weight: 680; letter-spacing: -0.02em; }
  .og p { margin: 0; font-size: 24px; line-height: 1.38; color: var(--text-muted); }
  .og-facts { display: flex; gap: 10px; margin: 4px 0 0; padding: 0; list-style: none; }
  .og-facts li { font-size: 17px; font-weight: 600; color: var(--accent); background: var(--accent-soft);
                 padding: 6px 14px; border-radius: 999px; white-space: nowrap; }
  .og-chart { margin: 0; background: var(--surface-1); border: 1px solid var(--border); border-radius: 22px;
              padding: 18px 14px 6px; box-shadow: 0 18px 50px oklch(0.25 0.02 260 / 0.14); }
  .og-chart svg { display: block; width: 100%; height: auto; }
</style>
</head>
<body>
<main class="og">
  <section class="og-words">
    ${wordmark}
    <h1>Open-source application portfolio management</h1>
    <p>Know every application your organization runs, who answers for it, and what to do with it next.</p>
    <ul class="og-facts"><li>Explainable scores</li><li>Decisions on record</li><li>Self-hosted</li></ul>
  </section>
  <figure class="og-chart">${chart}</figure>
</main>
</body>
</html>`;

const demo = await startDemo({ port: 8027 });
const browser = await openBrowser();
const scratch = mkdtempSync(join(tmpdir(), "appwren-preview-"));
try {
  await browser.size(WIDTH, HEIGHT, 1);
  await browser.scheme("light");
  await signInAs(browser, demo.base, "portfolio");
  await browser.goto(`${demo.base}/portfolio`);
  await browser.settled();
  await browser.waitFor(`document.querySelector("svg.portfolio-chart circle")`, "the portfolio chart");
  // The chart as drawn, without what is there for a pointer or a screen reader.
  const chart = await browser.evaluate(`(() => {
    const drawn = document.querySelector("svg.portfolio-chart").cloneNode(true);
    drawn.querySelectorAll("title").forEach((node) => node.remove());
    drawn.setAttribute("aria-hidden", "true");
    return drawn.outerHTML;
  })()`);
  const styles = (await Promise.all(SHEETS.map(async (name) => {
    const answer = await fetch(`${demo.base}/css/${name}.css`);
    if (!answer.ok) throw new Error(`The app's ${name}.css could not be read`);
    return answer.text();
  }))).join("\n");
  const file = join(scratch, "preview.html");
  writeFileSync(file, page(styles, chart));
  await browser.goto(pathToFileURL(file).href);
  await browser.waitFor(`document.fonts.status === "loaded" && getComputedStyle(document.body).backgroundColor !== "rgba(0, 0, 0, 0)"`,
    "the app's stylesheets");
  await new Promise((done) => setTimeout(done, 300));
  await browser.screenshot(out);
  console.log(`Wrote ${out} (${WIDTH} by ${HEIGHT})`);
} finally {
  await browser.close();
  demo.stop();
  rmSync(scratch, { recursive: true, force: true });
}
