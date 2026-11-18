import { manage } from "./support/django";
import { expect, test } from "./support/fixtures";

/**
 * The screens after this file (accessibility, keyboard, responsive) are more useful with records on them, so the development demo data
 * (quotations, contracts, clients, tasks, payments, leave) is loaded into the throwaway database. The command is safe to repeat. The seats
 * (CEO, heads, Marketing) are already held by the accounts the setup journey made, so the demo records are attached to those people.
 */
test("demo records are loaded into the throwaway database", async ({ as }) => {
  const out = manage("seed_demo_data");
  expect(out).toContain("Demo data ready");
  const head = await as("commercial_head");
  const { api } = await import("./support/fixtures");
  const r = await api(head, "GET", "/leads/");
  expect(r.status).toBe(200);
});
