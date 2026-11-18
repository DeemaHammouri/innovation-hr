import type { Page } from "@playwright/test";
import { CEO, STRONG_PASSWORD, SUPER_ADMIN } from "./support/env";
import { account, api, expect, settle, signInUi, stampPng, STAFF_ROLES, test } from "./support/fixtures";

/**
 * Setup journey: Super Admin, then the CEO uploads the stamp and creates the seven other staff accounts through the screens,
 * each new person is forced to change the temporary password, and the seat rules refuse a second head / Marketing / Administration.
 * Repeatable on the same database: an account that already exists gets a fresh temporary password (Reset password) instead.
 */
test.describe.configure({ mode: "serial" });

type UserRow = { id: number; email: string; full_name: string; role: string; role_key?: string };

async function listUsers(page: Page): Promise<UserRow[]> {
  const r = await api(page, "GET", "/users/");
  return Array.isArray(r.body) ? r.body : (r.body?.results ?? []);
}

test("super admin signs in and sees the home screen", async ({ page, T, shots }) => {
  await page.goto("/login");
  await shots(page, "login");
  await signInUi(page, SUPER_ADMIN.email, SUPER_ADMIN.password);
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.locator("main")).toBeVisible();
  const me = await api(page, "GET", "/auth/me/");
  expect(me.status).toBe(200);
  expect(me.body.role_key ?? me.body.role).toBeTruthy();
  await shots(page, "setup-super-admin-home");
  expect(await page.title()).not.toBe("");
  void T;
});

test("CEO signs in, uploads the company stamp", async ({ page, T, shots }) => {
  await signInUi(page, CEO.email, CEO.password);
  await page.goto("/admin/company");
  await settle(page);
  await expect(page.locator("#field-stamp")).toBeAttached();
  await page.locator("#field-stamp").setInputFiles({ name: "stamp.png", mimeType: "image/png", buffer: stampPng() });
  await page.locator("form button[type=submit]").click();
  await expect(page.getByText(T("company.stampHas"))).toBeVisible();
  await shots(page, "setup-company-stamp");
});

// One test per account keeps a failure easy to read. Each test creates (or resets) the account, then the person signs in.
for (const spec of STAFF_ROLES) {
  test(`CEO creates ${spec.key} and the new user is forced to change the temporary password`, async ({ page, newContext, T, shots, lang }) => {
    const { email } = account(spec.key);
    await signInUi(page, CEO.email, CEO.password);
    const existing = (await listUsers(page)).find((u) => u.email === email);
    let temp = "";
    const departments = (await api(page, "GET", "/departments/")).body as { id: number; name: string }[];
    const deptId = String(departments.find((d) => d.name === spec.dept)!.id);

    if (!existing) {
      await page.goto("/users");
      await settle(page);
      await page.getByRole("link", { name: T("users.add") }).first().click();
      await expect(page).toHaveURL(/\/users\/new/);
      await page.locator("#field-full_name").fill(spec.name);
      await page.locator("#field-email").fill(email);
      await page.locator("#field-department").selectOption(deptId);
      await page.locator("#field-role").selectOption(spec.role);
      if (spec.key === "commercial_head") await shots(page, "setup-user-form");
      await page.getByRole("button", { name: T("users.create") }).click();
    } else {
      await page.goto("/users");
      await settle(page);
      await page.getByRole("searchbox").first().fill(email);
      await page.waitForTimeout(600);
      await page.getByRole("button", { name: T("users.actionsFor", { name: existing.full_name }) }).first().click();
      await page.getByRole("menuitem", { name: T("users.resetPassword") }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: T("users.resetPassword") }).click();
    }
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    temp = (await sheet.locator("dd.font-mono").innerText()).trim();
    expect(temp.length).toBeGreaterThanOrEqual(12);
    if (spec.key === "commercial_head") await shots(page, "setup-temporary-password");
    await sheet.getByRole("button", { name: T("common.done") }).click();

    // The new person signs in with the temporary password and must choose their own.
    const ctx = await newContext();
    const p = await ctx.newPage();
    await signInUi(p, email, temp);
    await expect(p).toHaveURL(/\/set-password/);
    const newField = p.locator("#field-new_password");
    const confirmField = p.locator("#field-confirm_password");
    // weak: too short
    await newField.fill("Short-1a");
    await confirmField.fill("Short-1a");
    await p.locator("form button[type=submit]").click();
    await expect(p.locator("#error-new_password")).toBeVisible();
    await expect(p).toHaveURL(/\/set-password/);
    if (spec.key === "commercial_head") await shots(p, "setup-weak-password-rejected");
    // weak: long enough but not acceptable (the same as the temporary password)
    await newField.fill(temp);
    await confirmField.fill(temp);
    await p.locator("form button[type=submit]").click();
    await expect(p).toHaveURL(/\/set-password/);
    await expect(p.locator("[role=alert]:visible").first()).toBeVisible();
    // strong: accepted
    await newField.fill(STRONG_PASSWORD);
    await confirmField.fill(STRONG_PASSWORD);
    await p.locator("form button[type=submit]").click();
    await p.waitForURL((u) => !u.pathname.startsWith("/set-password"), { timeout: 20_000 });
    await settle(p);
    await expect(p.locator("main")).toBeVisible();
    const me = await api(p, "GET", "/auth/me/");
    expect(me.body.email).toBe(email);
    expect(me.body.must_change_password).toBe(false);
    if (spec.key === "commercial_head") await shots(p, "setup-new-user-home");
  });
}

test("a second department head, second Marketing, second Administration and forbidden roles are refused", async ({ page, T, shots }) => {
  await signInUi(page, CEO.email, CEO.password);
  const departments = (await api(page, "GET", "/departments/")).body as { id: number; name: string }[];
  const id = (name: string) => String(departments.find((d) => d.name === name)!.id);
  const before = (await listUsers(page)).length;

  const attempts: { label: string; dept: string; role: "head" | "member" }[] = [
    { label: "second Commercial head", dept: "Commercial", role: "head" },
    { label: "second HR head", dept: "HR", role: "head" },
    { label: "second Operation head", dept: "Operation", role: "head" },
    { label: "second Marketing user", dept: "Marketing", role: "member" },
    { label: "second Administration user", dept: "Administration", role: "head" },
  ];
  for (const [i, a] of attempts.entries()) {
    await page.goto("/users/new");
    await settle(page);
    await page.locator("#field-full_name").fill(`E2E Duplicate ${i}`);
    await page.locator("#field-email").fill(`e2e-duplicate-${i}-${Date.now()}@e2e.test`);
    await page.locator("#field-department").selectOption(id(a.dept));
    await page.locator("#field-role").selectOption(a.role);
    await page.getByRole("button", { name: T("users.create") }).click();
    // a visible error, and no credentials were handed out
    await expect(page.locator("[role=alert]:visible").first(), a.label).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page).toHaveURL(/\/users\/new/);
    if (i === 0) await shots(page, "setup-second-head-refused");
    if (i === 3) await shots(page, "setup-second-marketing-refused");
    if (i === 4) await shots(page, "setup-second-administration-refused");
  }

  // The role list never offers Super Admin or Client, and Administration offers Head only.
  await page.goto("/users/new");
  await settle(page);
  expect(await page.locator("#field-role option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value).sort())).toEqual(["head", "member"]);
  await page.locator("#field-department").selectOption(id("Administration"));
  expect(await page.locator("#field-role option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value))).toEqual(["head"]);

  // Forbidden roles are refused by the server too.
  for (const role of ["super_admin", "client", "ceo", "nonsense"]) {
    const r = await api(page, "POST", "/users/", { full_name: "E2E Forbidden", email: `e2e-forbidden-${role}-${Date.now()}@e2e.test`, department: Number(id("Commercial")), role });
    expect(r.status, `role ${role}`).toBeGreaterThanOrEqual(400);
    expect(r.status, `role ${role}`).toBeLessThan(500);
  }
  expect((await listUsers(page)).length).toBe(before);
});

test("the CEO cannot see the Super Admin in the users list", async ({ page, T, shots }) => {
  await signInUi(page, CEO.email, CEO.password);
  await page.goto("/users");
  await settle(page);
  const rows = await listUsers(page);
  expect(rows.some((u) => u.email === SUPER_ADMIN.email)).toBe(false);
  await expect(page.getByText(SUPER_ADMIN.email)).toHaveCount(0);
  await page.getByRole("searchbox").first().fill("E2E System Admin");
  await page.waitForTimeout(700);
  await expect(page.getByText("E2E System Admin")).toHaveCount(0);
  const direct = rows.find((u) => u.full_name === "E2E System Admin");
  expect(direct).toBeUndefined();
  await page.getByRole("searchbox").first().fill("");
  await page.waitForTimeout(600);
  await shots(page, "setup-users-list");
});
