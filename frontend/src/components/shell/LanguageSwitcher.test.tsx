import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { clearCookies, jsonResponse, makeUser, stubFetch } from "@/test/utils";
import { LanguageSwitcher } from "./LanguageSwitcher";

function setup(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  return render(
    <LanguageProvider initialLang={lang}>
      <AuthProvider>
        <LanguageSwitcher />
      </AuthProvider>
    </LanguageProvider>,
  );
}

beforeEach(() => clearCookies());
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("LanguageSwitcher", () => {
  it("offers both languages by their own names and marks the current one", async () => {
    stubFetch(() => jsonResponse({ error: { message: "x" } }, 401));
    setup("en");
    expect(screen.getByRole("radiogroup", { name: "Language · اللغة" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "English" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "العربية" })).not.toBeChecked();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
  });

  it("switching to Arabic flips dir to rtl and lang to ar on the page, and stores the cookie", async () => {
    stubFetch(() => jsonResponse({ error: { message: "x" } }, 401));
    setup("en");
    await userEvent.click(screen.getByRole("radio", { name: "العربية" }));
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.cookie).toContain("lang=ar");
    expect(screen.getByRole("radio", { name: "العربية" })).toBeChecked();
  });

  it("switching back to English restores ltr", async () => {
    stubFetch(() => jsonResponse({ error: { message: "x" } }, 401));
    setup("ar");
    await userEvent.click(screen.getByRole("radio", { name: "English" }));
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("en");
  });

  it("does not call the server when nobody is signed in", async () => {
    const f = stubFetch(() => jsonResponse({ error: { message: "x" } }, 401));
    setup("en");
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1)); // the session check only
    await userEvent.click(screen.getByRole("radio", { name: "العربية" }));
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("saves the choice on the account (PATCH with CSRF) when signed in", async () => {
    document.cookie = "csrf_token=tok; path=/";
    const me = makeUser({ id: 5, preferred_language: "en" });
    const f = stubFetch((_url, init) => (init.method === "PATCH" ? jsonResponse({ ...me, preferred_language: "ar" }) : jsonResponse(me)));
    setup("en");
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole("radio", { name: "العربية" }));
    await waitFor(() => expect(f.mock.calls.some((c) => c[1].method === "PATCH")).toBe(true));
    const patch = f.mock.calls.find((c) => c[1].method === "PATCH")!;
    expect(patch[0]).toBe("/api/v1/auth/me/");
    expect(JSON.parse(String(patch[1].body))).toEqual({ preferred_language: "ar" });
    expect((patch[1].headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
  });

  it("clicking the already-selected language does nothing", async () => {
    const f = stubFetch(() => jsonResponse(makeUser()));
    setup("en");
    await waitFor(() => expect(f).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole("radio", { name: "English" }));
    expect(f).toHaveBeenCalledTimes(1);
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("keeps the new language even when saving to the account fails", async () => {
    document.cookie = "csrf_token=tok; path=/";
    stubFetch((_url, init) => (init.method === "PATCH" ? jsonResponse({ error: { message: "boom" } }, 500) : jsonResponse(makeUser())));
    setup("en");
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole("radio", { name: "العربية" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("applies the language saved on the account after sign-in check", async () => {
    stubFetch(() => jsonResponse(makeUser({ preferred_language: "ar" })));
    setup("en");
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("ar");
  });
});
