import { expect, test } from "./support/fixtures";

/**
 * Console hygiene is enforced for EVERY test by an automatic fixture (support/fixtures.ts): a console error, an uncaught page error or an
 * HTTP 5xx in any browser context fails the test that caused it. This file proves the guard itself works, so a silent guard cannot go unnoticed.
 */
test("the guard records a console error, a page error and an HTTP 5xx, and ignores a 4xx", async ({ page, problems }) => {
  await page.goto("/login");
  await page.evaluate(() => console.error("guard check: console error"));
  await page.evaluate(() => setTimeout(() => { throw new Error("guard check: page error"); }, 0));
  await page.evaluate(() => fetch("/api/v1/auth/me/")); // 401 or 200: not a problem
  await page.waitForTimeout(300);
  expect(problems.some((p) => p.includes("console.error: guard check: console error"))).toBe(true);
  expect(problems.some((p) => p.includes("pageerror") && p.includes("guard check: page error"))).toBe(true);
  expect(problems.some((p) => p.startsWith("HTTP 4"))).toBe(false);
  // an HTTP 5xx: ask the proxy for a backend path that does not exist behind an unreachable upstream is not possible, so answer one ourselves
  await page.route("**/api/v1/health/", (route) => route.fulfill({ status: 503, body: "{}" }));
  await page.evaluate(() => fetch("/api/v1/health/"));
  await page.waitForTimeout(200);
  expect(problems.some((p) => p.startsWith("HTTP 503"))).toBe(true);
  problems.length = 0; // the guard works: clear what this test provoked on purpose
});
