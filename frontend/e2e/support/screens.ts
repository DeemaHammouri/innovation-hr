import type { Page } from "@playwright/test";
import { api, settle } from "./fixtures";

export type Screen = { name: string; path: string };

const slug = (p: string) => p.replace(/^\//, "").replace(/[/?=&]+/g, "-").replace(/-+$/, "") || "home";

/**
 * The main screens this person can reach: every link in the sidebar for their role, the profile and settings, the "new" forms they may
 * open, and the first record of each list they can read (lead, quotation, contract, client, user). Reading the sidebar means a new
 * module is picked up without editing the suite.
 */
export async function screensFor(page: Page): Promise<Screen[]> {
  await page.goto("/");
  await settle(page);
  const links = await page.locator("aside a[href^='/'], nav a[href^='/']").evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).getAttribute("href") as string));
  const paths = new Set<string>(["/", ...links, "/profile", "/profile?tab=settings"]);

  const detail: [string, string][] = [
    ["/leads/", "/leads/"],
    ["/quotations/", "/quotations/"],
    ["/contracts/", "/contracts/"],
    ["/clients/", "/clients/"],
    ["/users/", "/users/"],
  ];
  for (const [endpoint, base] of detail) {
    const r = await api(page, "GET", endpoint);
    const rows = r.status === 200 ? (Array.isArray(r.body) ? r.body : (r.body?.results ?? [])) : [];
    if (rows.length) paths.add(`${base}${rows[0].id}`);
  }
  // Forms and tools that only some roles can open. A role without access sees the "no access" screen, which is also checked.
  const me = (await api(page, "GET", "/auth/me/")).body as { capabilities?: string[] };
  const has = (c: string) => !!me.capabilities?.includes(c);
  if (has("lead.access")) paths.add("/leads");
  if (has("lead.create")) paths.add("/leads/new");
  if (has("lead.import")) paths.add("/leads/import");
  if (has("user.manage")) paths.add("/users/new");
  return [...paths].map((path) => ({ name: slug(path), path }));
}
