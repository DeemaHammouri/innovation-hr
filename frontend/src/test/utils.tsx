import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { User } from "@/lib/api";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";

/** Renders under the real language provider. Direction and lang are set on <html> like the app does. */
export function renderWithLang(ui: React.ReactElement, lang: Lang = "en") {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  return render(ui, { wrapper: ({ children }) => <LanguageProvider initialLang={lang}>{children}</LanguageProvider> });
}

export function makeUser(over: Partial<User> = {}): User {
  return {
    id: 1,
    full_name: "Test User",
    email: "test@example.com",
    username: null,
    capabilities: [],
    department: null,
    department_name: null,
    role: "member",
    role_key: null,
    is_active: true,
    must_change_password: false,
    preferred_language: "en",
    permissions: { manage_users: false, manage_clients: false },
    ...over,
  };
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Stubs global fetch with a handler; returns the mock so calls can be inspected. */
export function stubFetch(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const mock = vi.fn((url: string, init: RequestInit) => Promise.resolve(handler(url, init ?? {})));
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function clearCookies() {
  for (const c of document.cookie.split("; ")) {
    const name = c.split("=")[0];
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}
