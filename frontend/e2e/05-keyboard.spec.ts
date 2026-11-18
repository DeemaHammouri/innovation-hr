import type { Locator, Page } from "@playwright/test";
import { CEO } from "./support/env";
import { api, expect, settle, test } from "./support/fixtures";

/**
 * Keyboard-only walkthroughs. Nothing here uses the mouse: Tab, Shift+Tab, arrows, Enter, Space and Escape only.
 * Run in English (left to right) and Arabic (right to left), so the focus order is checked in both directions.
 */

/** Presses Tab until `target` has focus (at most `max` presses). Returns the number of presses. */
async function tabTo(page: Page, target: Locator, max = 40): Promise<number> {
  for (let i = 1; i <= max; i++) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return i;
  }
  throw new Error(`Tab never reached the target in ${max} presses`);
}

/**
 * Tabs through every stop inside `container` and checks the order matches what the eye sees: top to bottom, and within a row left to right
 * in English and right to left in Arabic. Returns the labels in order.
 */
async function focusOrder(page: Page, container: Locator, rtl: boolean, max = 30): Promise<string[]> {
  const stops: { label: string; x: number; y: number; w: number }[] = [];
  const first = container.locator("a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), select, textarea").first();
  await first.focus();
  for (let i = 0; i < max; i++) {
    const info = await container.evaluate((root) => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || !root.contains(el)) return null;
      const r = el.getBoundingClientRect();
      return { label: el.getAttribute("aria-label") || el.getAttribute("name") || el.textContent?.trim().slice(0, 30) || el.tagName, x: r.left + r.width / 2 + window.scrollX, y: r.top + r.height / 2 + window.scrollY, w: r.width };
    });
    if (!info) break;
    stops.push(info);
    await page.keyboard.press("Tab");
  }
  for (let i = 1; i < stops.length; i++) {
    const a = stops[i - 1];
    const b = stops[i];
    const sameRow = Math.abs(b.y - a.y) < 20; // a control drawn inside a field (the show-password eye) shares the field's row
    if (sameRow) expect(rtl ? b.x < a.x : b.x > a.x, `same row: "${a.label}" then "${b.label}" must go ${rtl ? "right to left" : "left to right"}`).toBe(true);
    else expect(b.y, `"${b.label}" must not be above "${a.label}"`).toBeGreaterThan(a.y);
  }
  return stops.map((s) => s.label);
}

test("login by keyboard only: Tab to the fields, errors take focus, Enter signs in", async ({ page, lang, T, shots }) => {
  await page.goto("/login");
  await settle(page);
  const rtl = lang === "ar";
  expect(await page.evaluate(() => document.documentElement.dir)).toBe(rtl ? "rtl" : "ltr");

  const email = page.locator("#field-email");
  const password = page.locator("#field-password");
  const taps = await tabTo(page, email);
  expect(taps).toBeLessThan(10);
  await shots(page, "keyboard-login-focus");
  // Enter on an empty form: errors appear and the first problem has the focus
  await page.keyboard.press("Enter");
  await expect(page.locator("#error-email")).toBeVisible();
  await expect(email).toBeFocused();
  // the visual order of the stops in the form
  const order = await focusOrder(page, page.locator("form"), rtl);
  expect(order.length).toBeGreaterThanOrEqual(3);
  // fill with the keyboard and submit with Enter
  await email.focus();
  await page.keyboard.type(CEO.email);
  await page.keyboard.press("Tab");
  await expect(password).toBeFocused();
  await page.keyboard.type(CEO.password);
  await page.keyboard.press("Enter");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20_000 });
  void T;
});

test("global search by keyboard: shortcut, type, arrow, Enter", async ({ as, T, shots }) => {
  const page = await as("ceo");
  await page.goto("/");
  await settle(page);
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: T("search.title") });
  await expect(dialog).toBeVisible();
  const box = dialog.getByRole("combobox");
  await expect(box).toBeFocused();
  await box.pressSequentially(T("nav.users").slice(0, 4), { delay: 40 });
  await expect(dialog.getByRole("option").first()).toBeVisible();
  const active = async () => box.getAttribute("aria-activedescendant");
  const before = await active();
  await page.keyboard.press("ArrowDown");
  const after = await active();
  // With a single match there is nothing to move to; with several, the arrow key must move the highlight.
  if ((await dialog.getByRole("option").count()) > 1) expect(after).not.toBe(before);
  else expect(after).toBe(before);
  await shots(page, "keyboard-search-open");
  const chosen = await page.locator(`[id="${after}"]`).innerText();
  expect(chosen.trim().length).toBeGreaterThan(0);
  await page.keyboard.press("Enter");
  await expect(dialog).toHaveCount(0);
  await settle(page);
  expect(new URL(page.url()).pathname).not.toBe("/");
  // Escape closes it and gives focus back to what had it before
  const home = page.locator("aside a[href=\"/\"], aside a").first();
  await home.focus();
  await page.keyboard.press("Control+k");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(home).toBeFocused();
});

test("a form by keyboard: tab order follows the page, errors take focus", async ({ as, T, lang, shots }) => {
  const page = await as("ceo");
  await page.goto("/users/new");
  await settle(page);
  const rtl = lang === "ar";
  const form = page.locator("form");
  const order = await focusOrder(page, form, rtl, 20);
  expect(order.length).toBeGreaterThanOrEqual(5);
  // Enter in the first field with nothing filled in: focus lands on the first invalid field and its error is announced
  const name = page.locator("#field-full_name");
  await name.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#error-full_name")).toBeVisible();
  await expect(name).toBeFocused();
  await expect(name).toHaveAttribute("aria-invalid", "true");
  await shots(page, "keyboard-form-error");
  // Fix the name only: the next Enter moves focus to the next problem (the email)
  await page.keyboard.type("E2E Keyboard");
  await page.keyboard.press("Enter");
  await expect(page.locator("#field-email")).toBeFocused();
  void T;
});

test("a modal by keyboard: focus goes in, stays trapped, Escape closes and returns focus", async ({ as, T, shots }) => {
  const page = await as("commercial_member");
  const r = await api(page, "GET", "/leads/?status=new");
  const lead = (r.body.results ?? r.body)[0];
  expect(lead, "the member needs a new lead (made by the lead journey)").toBeTruthy();
  await page.goto(`/leads/${lead.id}`);
  await settle(page);
  const opener = page.getByRole("button", { name: T("lead.next.contact") });
  await opener.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const inside = () => page.evaluate(() => !!document.activeElement?.closest("[role=dialog],[role=alertdialog]"));
  expect(await inside(), "focus moves into the dialog on open").toBe(true);
  await shots(page, "keyboard-modal-open");
  for (let i = 0; i < 14; i++) {
    await page.keyboard.press("Tab");
    expect(await inside(), `Tab ${i + 1} stays inside`).toBe(true);
  }
  for (let i = 0; i < 14; i++) {
    await page.keyboard.press("Shift+Tab");
    expect(await inside(), `Shift+Tab ${i + 1} stays inside`).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("a modal on a phone: filters sheet opens by keyboard, traps focus and gives focus back", async ({ as, T }) => {
  const page = await as("ceo");
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto("/users");
  await settle(page);
  const opener = page.getByRole("button", { name: T("users.filters") });
  await opener.focus();
  await page.keyboard.press("Space");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => !!document.activeElement?.closest("[role=dialog]"))).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});
