import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { ALL_ROLES, api, expect, settle, test, type RoleKey } from "./support/fixtures";
import { screensFor } from "./support/screens";

/**
 * Accessibility: axe-core (WCAG 2.0 A and AA, WCAG 2.1 AA) must report zero violations on every main screen each role can reach,
 * in English and Arabic: the login page, the home screen, every sidebar screen, list and detail screens, the profile and settings,
 * the command palette, a modal and the language switcher. A real violation is fixed in the app, never excluded here.
 */
const TAGS = ["wcag2a", "wcag2aa", "wcag21aa"];

async function scan(page: Page, label: string, failures: string[]) {
  await page.waitForTimeout(450); // let entrance animations finish so colours are final
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  for (const v of result.violations) {
    const nodes = v.nodes.slice(0, 3).map((n) => `${n.target.join(" ")} :: ${(n.failureSummary ?? "").replace(/\s+/g, " ").slice(0, 220)}`);
    failures.push(`[${label}] ${v.id} (${v.impact}) ${v.help} -> ${nodes.join(" || ")}`);
  }
}

test("login page, language switcher and the forced-password screen have no violations", async ({ page, lang, shots }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const failures: string[] = [];
  await page.goto("/login");
  await settle(page);
  await scan(page, "login", failures);
  await shots(page, "a11y-login");
  // an error state on the login form
  await page.locator("form button[type=submit]").click();
  await expect(page.locator("[role=alert]:visible").first()).toBeVisible();
  await scan(page, "login with errors", failures);
  // the language switcher: flip to the other language and scan again
  await page.getByRole("radio", { name: lang === "en" ? "العربية" : "English" }).first().click();
  await settle(page);
  await scan(page, "login after switching language", failures);
  expect(failures).toEqual([]);
});

for (const role of ALL_ROLES) {
  test(`${role}: every main screen, the command palette and a modal pass axe`, async ({ as, T, shots }) => {
    test.setTimeout(420_000);
    const page = await as(role);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const failures: string[] = [];
    const screens = await screensFor(page);
    expect(screens.length).toBeGreaterThan(2);
    for (const s of screens) {
      await page.goto(s.path);
      await settle(page);
      await scan(page, s.path, failures);
      if (s.path === "/") await shots(page, `a11y-home-${role}`);
    }

    // language switcher: switch the signed-in app to the other language and scan the home screen, then switch back
    await page.goto("/");
    await settle(page);
    const switcher = page.getByRole("radio", { name: /^(العربية|English)$/ });
    if (await switcher.count()) {
      const [en, ar] = [page.getByRole("radio", { name: "English" }).first(), page.getByRole("radio", { name: "العربية" }).first()];
      const current = await page.evaluate(() => document.documentElement.lang);
      await (current === "ar" ? en : ar).click();
      await settle(page);
      await scan(page, `/ after switching language from ${current}`, failures);
      await (current === "ar" ? ar : en).click();
      await settle(page);
    }

    // command palette
    await page.goto("/");
    await settle(page);
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: T("search.title") })).toBeVisible();
    await scan(page, "command palette", failures);
    await shots(page, `a11y-palette-${role}`);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // a modal, per role where one is a main task
    const modal = await openModal(page, role, T);
    if (modal) {
      await scan(page, `modal (${modal})`, failures);
      await shots(page, `a11y-modal-${role}`);
      await page.keyboard.press("Escape");
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
}

/** Opens one real dialog for the roles that have one on a main screen. Returns its name, or null when the role has none. */
async function openModal(page: Page, role: RoleKey, T: (k: string, v?: Record<string, string | number>) => string): Promise<string | null> {
  const first = async (endpoint: string) => {
    const r = await api(page, "GET", endpoint);
    const rows = Array.isArray(r.body) ? r.body : (r.body?.results ?? []);
    return rows[0] as { id: number; full_name?: string; status?: string } | undefined;
  };
  if (role === "ceo" || role === "super") {
    await page.goto("/users");
    await settle(page);
    const rows = (await api(page, "GET", "/users/")).body as { id: number; full_name: string }[];
    const target = rows.find((u) => u.full_name.startsWith("E2E ") && u.full_name !== "E2E Chief Executive") ?? rows[0];
    await page.getByRole("button", { name: T("users.actionsFor", { name: target.full_name }) }).first().click();
    await page.getByRole("menuitem", { name: T("users.resetPassword") }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    return "reset password";
  }
  if (role === "commercial_member" || role === "commercial_head") {
    const lead = await first("/leads/?status=new");
    if (!lead) return null;
    await page.goto(`/leads/${lead.id}`);
    await settle(page);
    const button = page.getByRole("button", { name: new RegExp(`^(${T("lead.next.assign")}|${T("lead.next.contact")})$`) });
    if (!(await button.count())) return null;
    await button.first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    return "lead sheet";
  }
  if (role === "marketing") {
    const lead = await first("/leads/?status=new");
    if (!lead) return null;
    await page.goto(`/leads/${lead.id}`);
    await settle(page);
    const actions = page.getByRole("button", { name: T("common.actions") });
    if (!(await actions.count())) return null;
    await actions.first().click();
    const item = page.getByRole("menuitem", { name: T("lead.archive") });
    if (!(await item.count())) return null;
    await item.click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    return "archive lead";
  }
  return null;
}
