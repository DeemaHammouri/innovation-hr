import { api, expect, settle, test } from "./support/fixtures";

/**
 * Lead journey: Marketing imports a CSV (valid, invalid and duplicate rows) and adds one lead by hand, the Commercial head assigns them,
 * the Commercial member logs contacts with three different outcomes, and the converted lead is locked.
 * Names and phone numbers carry a per-run suffix so the journey repeats on the same database.
 */
test.describe.configure({ mode: "serial" });

const run = Date.now().toString(36);
const digits = String(Date.now()).slice(-6); // the last six digits of the clock keep phone numbers unique per run
const phone = (n: number) => `0790${digits}${n}`;
const company = (n: number | string) => `E2E Co ${run} ${n}`;
const tomorrow = () => {
  const d = new Date(Date.now() + 2 * 86_400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const csv = [
  "Company,Name,Position,Phone,Email,Location,Source,Notes",
  `${company(1)},Sara Waiting,Manager,${phone(1)},e2e1-${run}@lead.test,Amman,Trade fair,valid row`,
  `${company(2)},Omar Rejected,Owner,${phone(2)},e2e2-${run}@lead.test,Irbid,Referral,valid row`,
  `${company(3)},Lina Accepted,Director,${phone(3)},e2e3-${run}@lead.test,Aqaba,Website,valid row`,
  `,No Company,Clerk,${phone(4)},e2e4-${run}@lead.test,Zarqa,Website,invalid: the company is missing`,
  `${company("dup")},Same Phone,Clerk,${phone(1)},,Amman,Website,duplicate of row 1 in this file`,
].join("\n");

test("Marketing imports a CSV: the preview shows errors and duplicates, then adds the valid rows", async ({ as, T, shots }) => {
  const page = await as("marketing");
  await page.goto("/leads/import");
  await settle(page);
  await page.locator("#field-file").setInputFiles({ name: `leads-${run}.csv`, mimeType: "text/csv", buffer: Buffer.from(csv, "utf8") });
  await page.getByRole("button", { name: T("lead.import.preview") }).click();
  await expect(page.getByText(T("lead.import.summary", { ok: 3, duplicates: 1, errors: 1 }))).toBeVisible();
  await expect(page.getByText(T("lead.import.state.error"), { exact: true })).toBeVisible();
  await expect(page.getByText(T("lead.import.state.duplicate"), { exact: true })).toBeVisible();
  await expect(page.getByText(T("lead.import.dupInFile", { row: 2 })).or(page.getByText(T("lead.import.dupInFile", { row: "٢" })))).toBeVisible();
  await shots(page, "leads-import-preview");
  await page.getByRole("button", { name: T("lead.import.confirm", { count: 3 }) }).click();
  // some rows were skipped, so the report is shown
  await expect(page.getByRole("heading", { name: T("lead.import.skippedHeading") })).toBeVisible();
  await shots(page, "leads-import-report");
  const found = await api(page, "GET", `/leads/?search=${encodeURIComponent(`E2E Co ${run}`)}`);
  const rows = found.body.results ?? found.body;
  expect(rows.length).toBe(3);
});

test("Marketing adds one lead by hand", async ({ as, T, shots }) => {
  const page = await as("marketing");
  await page.goto("/leads/new");
  await settle(page);
  // empty submit shows errors and keeps the focus on the first one
  await page.locator("form button[type=submit]").click();
  await expect(page.locator("[role=alert]:visible").first()).toBeVisible();
  await expect(page.locator("#field-company_name")).toBeFocused();
  await shots(page, "leads-new-errors");
  await page.locator("#field-company_name").fill(company("manual"));
  await page.locator("#field-contact_name").fill("Hand Entered");
  await page.locator("#field-phone").fill(phone(5));
  await page.locator("#field-email").fill(`e2e5-${run}@lead.test`);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL((u) => /\/leads\/\d+$/.test(u.pathname) || u.pathname === "/leads", { timeout: 20_000 });
  const found = await api(page, "GET", `/leads/?search=${encodeURIComponent(company("manual"))}`);
  expect((found.body.results ?? found.body).length).toBe(1);
  void T;
});

test("the Commercial head assigns the leads to the Commercial member", async ({ as, T, shots }) => {
  const page = await as("commercial_head");
  const memberName = "E2E Commercial Member";
  const found = await api(page, "GET", `/leads/?search=${encodeURIComponent(`E2E Co ${run}`)}`);
  const leads = (found.body.results ?? found.body) as { id: number; company_name: string }[];
  expect(leads.length).toBe(4);
  for (const [i, lead] of leads.entries()) {
    await page.goto(`/leads/${lead.id}`);
    await settle(page);
    await page.getByRole("button", { name: T("lead.next.assign") }).click();
    const sheet = page.getByRole("dialog");
    const value = await sheet.locator("#field-assigned_to option", { hasText: memberName }).first().getAttribute("value");
    await sheet.locator("#field-assigned_to").selectOption(value!);
    if (i === 0) await shots(page, "leads-assign-sheet");
    await sheet.getByRole("button", { name: T("lead.assign.save") }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText(memberName).first()).toBeVisible();
  }
  await page.goto("/pipeline");
  await settle(page);
  await shots(page, "leads-pipeline-head");
});

test("the Commercial member sets Waiting, Rejected and Initial acceptance on three leads; the converted lead is locked", async ({ as, T, shots }) => {
  const page = await as("commercial_member");
  const found = await api(page, "GET", `/leads/?search=${encodeURIComponent(`E2E Co ${run}`)}`);
  const leads = (found.body.results ?? found.body) as { id: number; company_name: string }[];
  const byName = (n: number) => leads.find((l) => l.company_name === company(n))!;
  const openContact = async (id: number) => {
    await page.goto(`/leads/${id}`);
    await settle(page);
    await page.getByRole("button", { name: T("lead.next.contact") }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  };
  const choose = (value: string) => page.locator(`label:has(input[type=radio][value="${value}"])`).click();
  const submit = () => page.getByRole("dialog").getByRole("button", { name: T("lead.logContact") }).click();

  // 1. Waiting needs a date
  const waiting = byName(1);
  await openContact(waiting.id);
  await choose("waiting");
  await submit();
  await expect(page.locator("#error-next_follow_up")).toBeVisible(); // date is required
  await shots(page, "leads-waiting-needs-date");
  await page.locator("#field-next_follow_up").fill(tomorrow());
  await submit();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(T("lead.status.waiting")).first()).toBeVisible();
  await shots(page, "leads-waiting");

  // 2. Rejected needs a reason
  const rejected = byName(2);
  await openContact(rejected.id);
  await choose("rejected");
  await submit();
  await expect(page.locator("#error-rejection_reason")).toBeVisible();
  await shots(page, "leads-rejected-needs-reason");
  const reasonValue = await page.locator("#field-rejection_reason option:not([value=''])").first().getAttribute("value");
  await page.locator("#field-rejection_reason").selectOption(reasonValue!);
  await submit();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(T("lead.status.rejected")).first()).toBeVisible();
  await shots(page, "leads-rejected");

  // 3. Initial acceptance converts the lead
  const accepted = byName(3);
  await openContact(accepted.id);
  await choose("accepted");
  await submit();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto(`/leads/${accepted.id}`);
  await settle(page);
  await expect(page.getByText(T("lead.status.qualified")).first()).toBeVisible();
  await expect(page.getByText(T("lead.converted"))).toBeVisible();
  await shots(page, "leads-accepted-locked");
  // locked: nothing to log, and the server refuses changes
  await expect(page.getByRole("button", { name: T("lead.logContact") })).toHaveCount(0);
  const refused = await api(page, "POST", `/leads/${accepted.id}/interactions/`, { type: "call", outcome: "", notes: "should not be allowed" });
  expect(refused.status).toBeGreaterThanOrEqual(400);
  expect(refused.status).toBeLessThan(500);
  const edited = await api(page, "PATCH", `/leads/${accepted.id}/`, { notes: "edit after conversion" });
  expect(edited.status).toBeGreaterThanOrEqual(400);
  expect(edited.status).toBeLessThan(500);
});
