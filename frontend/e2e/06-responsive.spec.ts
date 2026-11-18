import type { Page } from "@playwright/test";
import path from "node:path";
import { EVIDENCE_DIR } from "./support/env";
import { ALL_ROLES, expect, settle, test, WIDTHS } from "./support/fixtures";
import { screensFor } from "./support/screens";

/**
 * Responsive: no horizontal page scroll at 375, 768 and 1280 px on any main screen of any role, in both languages.
 * When a screen overflows, the failure names the elements that stick out so the cause is easy to find.
 */
async function overflow(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const width = window.innerWidth;
    if (doc.scrollWidth <= width + 1 && document.body.scrollWidth <= width + 1) return null;
    const culprits: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("body *"))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.right > width + 1 || r.left < -1) {
        // skip elements inside a scroll container of their own (tables with overflow-x: auto are fine)
        let p: HTMLElement | null = el.parentElement;
        let contained = false;
        while (p && p !== document.body) {
          const o = getComputedStyle(p).overflowX;
          if (o === "auto" || o === "scroll" || o === "hidden" || o === "clip") { contained = true; break; }
          p = p.parentElement;
        }
        if (!contained) culprits.push(`${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(/\s+/).slice(0, 3).join(".") : ""} [${Math.round(r.left)}..${Math.round(r.right)}]`);
      }
      if (culprits.length >= 4) break;
    }
    return `scrollWidth ${doc.scrollWidth} > ${width}; ${culprits.join(" | ")}`;
  });
}

for (const role of ALL_ROLES) {
  test(`${role}: no horizontal scroll at 375, 768 and 1280 on any main screen`, async ({ as, lang }) => {
    test.setTimeout(420_000);
    const page = await as(role);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const screens = await screensFor(page);
    const failures: string[] = [];
    for (const s of screens) {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(s.path);
      await settle(page);
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.waitForTimeout(250);
        const bad = await overflow(page);
        if (bad) failures.push(`${s.path} @${width}: ${bad}`);
        if (s.path === "/" || role === "ceo") {
          await page.screenshot({ path: path.join(EVIDENCE_DIR, `${lang}-${width}-responsive-${role}-${s.name}.png`) });
        }
      }
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
}
