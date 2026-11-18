import zlib from "node:zlib";
import { test as base, expect, type Browser, type BrowserContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { CEO, EVIDENCE_DIR, FRONTEND_DIR, STRONG_PASSWORD, SUPER_ADMIN, WEB_URL } from "./env";

export { expect };
export type Lang = "en" | "ar";
export const WIDTHS = [375, 768, 1280] as const;

/** The nine accounts the suite works with. Everything except the CEO and the Super Admin is created by the setup journey. */
export type RoleKey = "super" | "ceo" | "marketing" | "commercial_head" | "commercial_member" | "hr_head" | "hr_member" | "operation_head" | "operation_member";
export const STAFF_ROLES: { key: Exclude<RoleKey, "super" | "ceo">; dept: string; role: "head" | "member"; name: string }[] = [
  { key: "marketing", dept: "Marketing", role: "member", name: "E2E Marketing" },
  { key: "commercial_head", dept: "Commercial", role: "head", name: "E2E Commercial Head" },
  { key: "commercial_member", dept: "Commercial", role: "member", name: "E2E Commercial Member" },
  { key: "hr_head", dept: "HR", role: "head", name: "E2E HR Head" },
  { key: "hr_member", dept: "HR", role: "member", name: "E2E HR Member" },
  { key: "operation_head", dept: "Operation", role: "head", name: "E2E Operation Head" },
  { key: "operation_member", dept: "Operation", role: "member", name: "E2E Operation Member" },
];
export const ALL_ROLES: RoleKey[] = ["super", "ceo", ...STAFF_ROLES.map((r) => r.key)];

export const account = (key: RoleKey): { email: string; password: string } =>
  key === "super" ? SUPER_ADMIN : key === "ceo" ? CEO : { email: `e2e-${key.replace(/_/g, "-")}@e2e.test`, password: STRONG_PASSWORD };

// ---- translations (same plural/placeholder rules as the app) -----------------------------------------------------------
const locales: Record<Lang, Record<string, string>> = {
  en: JSON.parse(fs.readFileSync(path.join(FRONTEND_DIR, "src", "locales", "en.json"), "utf8")),
  ar: JSON.parse(fs.readFileSync(path.join(FRONTEND_DIR, "src", "locales", "ar.json"), "utf8")),
};
export function translate(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const text = locales[lang][key] ?? locales.en[key] ?? key;
  return text
    .replace(/\{(\w+)((?:\|[^|{}]*){2,4})\}/g, (whole, k: string, rest: string) => {
      const forms = rest.slice(1).split("|");
      const shown = String(vars[k] ?? "");
      const n = Number(shown.replace(/,/g, ""));
      if (Number.isNaN(n)) return whole;
      let pick = forms[forms.length - 1];
      if (forms.length === 2) pick = n === 1 ? forms[0] : forms[1];
      else if (forms.length === 4) pick = lang === "ar" ? (n === 1 ? forms[0] : n === 2 ? forms[1] : n % 100 >= 3 && n % 100 <= 10 ? forms[2] : forms[3]) : n === 1 ? forms[0] : forms[3];
      return pick.replace(/#/g, shown);
    })
    .replace(/\{(\w+)\}/g, (_, n: string) => String(vars[n] ?? ""));
}

// ---- the PNG the stamp upload needs (a plain 96x96 disc drawn in memory) ---------------------------------------------
export function stampPng(): Buffer {
  const size = 96;
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0;
    for (let x = 0; x < size; x++) {
      const inside = (x - 48) ** 2 + (y - 48) ** 2 < 44 ** 2;
      const o = y * (size * 4 + 1) + 1 + x * 4;
      raw[o] = 20; raw[o + 1] = 60; raw[o + 2] = 140; raw[o + 3] = inside ? 255 : 0;
    }
  }
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, sum]);
  };
  const head = Buffer.alloc(13);
  head.writeUInt32BE(size, 0);
  head.writeUInt32BE(size, 4);
  head[8] = 8;
  head[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", head), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

// ---- console hygiene ----------------------------------------------------------------------------------------------------
/** A 4xx answer is a normal part of negative tests (browsers log it as a console error), so only other errors count. */
const IGNORED_CONSOLE = [/Failed to load resource: the server responded with a status of 4\d\d/];

export type Problems = string[];
function watch(context: BrowserContext, problems: Problems) {
  context.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (IGNORED_CONSOLE.some((r) => r.test(text))) return;
    problems.push(`console.error: ${text.slice(0, 300)} @ ${m.location().url}`);
  });
  context.on("weberror", (e) => problems.push(`pageerror: ${String(e.error()).slice(0, 300)}`));
  context.on("response", (r) => {
    if (r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.request().method()} ${r.url()}`);
  });
}

// ---- helpers --------------------------------------------------------------------------------------------------------------
export type Api = { status: number; body: any }; // eslint-disable-line @typescript-eslint/no-explicit-any

/** Calls the app's own API from the page, the way the app does (same-origin proxy, cookies, CSRF header). */
export async function api(page: Page, method: string, url: string, body?: unknown): Promise<Api> {
  return page.evaluate(
    async ([m, u, b]) => {
      const token = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)?.[1] ?? "";
      const r = await fetch("/api/v1" + u, { method: m as string, headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, credentials: "same-origin", body: b ? JSON.stringify(b) : undefined });
      let json = null;
      try { json = await r.json(); } catch { /* no body */ }
      return { status: r.status, body: json };
    },
    [method, url, body ?? null] as const,
  );
}

export const settle = async (page: Page) => {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(250);
};

export async function noHorizontalScroll(page: Page) {
  return page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
}

type Fixtures = {
  lang: Lang;
  T: (key: string, vars?: Record<string, string | number>) => string;
  problems: Problems;
  /** A fresh browser context (cookies: language set) that is also under the console/5xx watch. */
  newContext: () => Promise<BrowserContext>;
  /** Sign in through the API in a fresh context and return its page. The account's language is set to the project's language. */
  as: (key: RoleKey) => Promise<Page>;
  /** Screenshots at 375, 768 and 1280 px into docs/evidence/acceptance/e2e. */
  shots: (page: Page, name: string) => Promise<void>;
  goto: (page: Page, path: string) => Promise<void>;
  autoGuard: void;
};

export const test = base.extend<Fixtures>({
  lang: async ({}, use, testInfo) => { // eslint-disable-line no-empty-pattern
    await use(testInfo.project.metadata.lang as Lang);
  },
  T: async ({ lang }, use) => {
    await use((key, vars) => translate(lang, key, vars));
  },
  problems: async ({}, use) => { // eslint-disable-line no-empty-pattern
    await use([]);
  },
  newContext: async ({ browser, lang, problems }, use) => {
    const made: BrowserContext[] = [];
    await use(async () => {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, baseURL: WEB_URL });
      await ctx.addCookies([{ name: "lang", value: lang, url: WEB_URL }]);
      watch(ctx, problems);
      made.push(ctx);
      return ctx;
    });
    for (const c of made) await c.close().catch(() => undefined);
  },
  as: async ({ newContext, lang }, use) => {
    await use(async (key) => {
      const ctx = await newContext();
      const { email, password } = account(key);
      const login = await ctx.request.post("/api/v1/auth/login/", { data: { identifier: email, password } });
      if (!login.ok()) throw new Error(`Sign-in as ${key} failed (${login.status()}). Run the setup journey (01-setup-journey) first.`);
      const csrf = (await ctx.cookies()).find((c) => c.name === "csrf_token")?.value ?? "";
      await ctx.request.patch("/api/v1/auth/me/", { data: { preferred_language: lang }, headers: { "X-CSRF-Token": csrf } });
      const page = await ctx.newPage();
      await page.goto("/");
      await settle(page);
      return page;
    });
  },
  shots: async ({ lang }, use) => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    await use(async (page, name) => {
      const original = page.viewportSize() ?? { width: 1280, height: 900 };
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.waitForTimeout(350);
        await page.screenshot({ path: path.join(EVIDENCE_DIR, `${lang}-${width}-${name}.png`) });
      }
      await page.setViewportSize(original);
      await page.waitForTimeout(150);
    });
  },
  goto: async ({}, use) => { // eslint-disable-line no-empty-pattern
    await use(async (page, p) => {
      await page.goto(p);
      await settle(page);
    });
  },
  // Every test fails on any console error, uncaught page error or HTTP 5xx in any of its browser contexts.
  autoGuard: [
    async ({ context, lang, problems }, use) => {
      await context.addCookies([{ name: "lang", value: lang, url: WEB_URL }]);
      watch(context, problems);
      await use();
      expect(problems, "console errors, page errors or HTTP 5xx during the test").toEqual([]);
    },
    { auto: true },
  ],
});

/** Signs in through the login screen (the real form), returns once the app has left /login. */
export async function signInUi(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.locator("#field-email").fill(email);
  await page.locator("#field-password").fill(password);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20_000 });
  await settle(page);
}

