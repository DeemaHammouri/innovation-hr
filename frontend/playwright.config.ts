import { defineConfig, type Project } from "@playwright/test";

/**
 * Browser suite. `npm run e2e` starts a throwaway Django (port 8100, temporary SQLite file) and a production Next server
 * (port 3100), runs every spec in English and then Arabic, and removes everything afterwards. See e2e/README.md.
 */
const chromePath = process.env.E2E_CHROME; // optional: an explicit chrome.exe; otherwise the installed Google Chrome is used

// One project per journey file, chained with dependencies, so the files run strictly in order (01 accounts, 02 leads, 03 demo data, 05 keyboard, 07 guard)
// even with several workers. English runs first, then Arabic on the database English left behind (which also proves the suite repeats on existing data).
// The scans (04 accessibility, 06 responsive) only read, so their tests run in parallel afterwards.
const JOURNEYS = [
  ["setup", /01-setup-journey/],
  ["leads", /02-lead-journey/],
  ["demo", /03-demo-data/],
  ["keyboard", /05-keyboard/],
  ["console", /07-console-hygiene/],
] as const;
const projects: Project[] = [];
let previous: string | undefined;
for (const lang of ["en", "ar"] as const) {
  for (const [name, testMatch] of JOURNEYS) {
    const id = `${lang}-${name}`;
    projects.push({ name: id, metadata: { lang }, testMatch, dependencies: previous ? [previous] : [] });
    previous = id;
  }
}
for (const lang of ["en", "ar"] as const) {
  projects.push({ name: `${lang}-scan-a11y`, metadata: { lang }, testMatch: /04-accessibility/, fullyParallel: true, dependencies: [previous!] });
  projects.push({ name: `${lang}-scan-responsive`, metadata: { lang }, testMatch: /06-responsive/, fullyParallel: true, dependencies: [previous!] });
}

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  fullyParallel: false,
  workers: Number(process.env.E2E_WORKERS ?? 4),
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://localhost:3100",
    headless: true,
    channel: chromePath ? undefined : "chrome",
    launchOptions: chromePath ? { executablePath: chromePath } : {},
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects,
});
