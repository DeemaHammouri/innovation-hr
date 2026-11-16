import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { clearCookies, jsonResponse, makeUser, stubFetch } from "@/test/utils";
import SetPasswordPage from "./page";

const replace = vi.fn();
const setUser = vi.fn();
const forget = vi.fn();
const signOut = vi.fn();
let temporary = "";
let authState: { user: ReturnType<typeof makeUser> | null; loading: boolean } = { user: null, loading: false };

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ ...authState, setUser }),
  getTemporaryPassword: () => temporary,
  forgetTemporaryPassword: () => forget(),
  useSignOut: () => signOut,
  useChangeLanguage: () => vi.fn(),
}));

async function setup(lang: Lang = "en", handler?: (url: string, init: RequestInit) => Response) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  const f = stubFetch((url, init) => (handler ? handler(url, init) : jsonResponse({})));
  render(
    <LanguageProvider initialLang={lang}>
      <ToastProvider>
        <SetPasswordPage />
      </ToastProvider>
    </LanguageProvider>,
  );
  await act(async () => {});
  return f;
}

const newPw = () => document.getElementById("field-new_password") as HTMLInputElement;
const confirmPw = () => document.getElementById("field-confirm_password") as HTMLInputElement;
async function enter(el: HTMLElement, text: string) {
  await userEvent.click(el);
  await userEvent.paste(text);
}
const save = () => userEvent.click(screen.getByRole("button", { name: "Save password" }));
const met = (rule: RegExp) => screen.getByText(rule).closest("li")!.textContent;

beforeEach(() => {
  clearCookies();
  document.cookie = "csrf_token=tok; path=/";
  replace.mockClear();
  setUser.mockClear();
  forget.mockClear();
  signOut.mockClear();
  temporary = "";
  authState = { user: makeUser({ must_change_password: true }), loading: false };
});
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("set-password page", () => {
  it("shows both fields as password inputs with labels", async () => {
    await setup();
    expect(newPw()).toHaveAttribute("type", "password");
    expect(confirmPw()).toHaveAttribute("type", "password");
    expect(screen.getByLabelText(/New password/)).toBe(newPw());
    expect(screen.getByLabelText(/Confirm new password/)).toBe(confirmPw());
  });

  it("flags a short password on blur and keeps Save enabled", async () => {
    await setup();
    await enter(newPw(), "short");
    await userEvent.tab();
    expect(screen.getByRole("alert")).toHaveTextContent("Use at least 12 characters.");
    expect(screen.getByRole("button", { name: "Save password" })).toBeEnabled();
  });

  it("submitting empty shows both errors, focuses the first, and calls nothing", async () => {
    const f = await setup();
    await save();
    const alerts = screen.getAllByRole("alert").map((a) => a.textContent);
    expect(alerts).toEqual(expect.arrayContaining(["Use at least 12 characters.", "Type the new password again."]));
    expect(newPw()).toHaveFocus();
    expect(f.mock.calls.filter((c) => c[1].method === "POST")).toHaveLength(0);
  });

  it("rejects a confirmation that does not match", async () => {
    const f = await setup();
    await enter(newPw(), "a-long-enough-password");
    await enter(confirmPw(), "a-long-enough-passwor");
    await save();
    expect(screen.getByRole("alert")).toHaveTextContent("The two passwords don't match.");
    expect(confirmPw()).toHaveAttribute("aria-invalid", "true");
    expect(f.mock.calls.filter((c) => c[1].method === "POST")).toHaveLength(0);
  });

  it("updates the checklist live", async () => {
    await setup();
    expect(met(/At least 12 characters/)).toContain("Not met yet");
    await enter(newPw(), "a-long-enough-password");
    await enter(confirmPw(), "a-long-enough-password");
    expect(met(/At least 12 characters/)).toContain("Met");
    expect(met(/Matches the confirmation/)).toContain("Met");
  });

  it("knows when the new password equals the temporary one", async () => {
    temporary = "Temp-Password-99";
    await setup();
    await enter(newPw(), "Temp-Password-99");
    expect(met(/Different from your temporary/)).toContain("Not met yet");
    await userEvent.clear(newPw());
    await enter(newPw(), "Brand-New-Password-1");
    expect(met(/Different from your temporary/)).toContain("Met");
  });

  it("posts both values with the CSRF header, forgets the temporary password, stores the user and goes home", async () => {
    const updated = makeUser({ must_change_password: false });
    const f = await setup("en", () => jsonResponse(updated));
    await enter(newPw(), "a-long-enough-password");
    await enter(confirmPw(), "a-long-enough-password");
    await save();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    const post = f.mock.calls.find((c) => c[1].method === "POST")!;
    expect(post[0]).toBe("/api/v1/auth/change-password/");
    expect(JSON.parse(String(post[1].body))).toEqual({ new_password: "a-long-enough-password", confirm_password: "a-long-enough-password" });
    expect((post[1].headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
    expect(forget).toHaveBeenCalled();
    expect(setUser).toHaveBeenCalledWith(updated);
    expect(await screen.findByText("Your new password is set.")).toBeInTheDocument();
  });

  it("shows the server's password rule on the field and does not navigate", async () => {
    await setup("en", () =>
      jsonResponse({ error: { code: "validation_error", message: "x", fields: { new_password: ["This password is too common."] } } }, 400),
    );
    await enter(newPw(), "password12345");
    await enter(confirmPw(), "password12345");
    await save();
    expect(await screen.findByRole("alert")).toHaveTextContent("This password is too common.");
    expect(newPw()).toHaveAttribute("aria-invalid", "true");
    expect(replace).not.toHaveBeenCalled();
    expect(forget).not.toHaveBeenCalled();
  });

  it("shows a general message when the server is down", async () => {
    await setup("en", () => jsonResponse({ error: { message: "boom" } }, 500));
    await enter(newPw(), "a-long-enough-password");
    await enter(confirmPw(), "a-long-enough-password");
    await save();
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't save your password just now.");
    expect(screen.getByRole("button", { name: "Save password" })).toBeEnabled();
  });

  it("locks Save while the request is running (no double submit)", async () => {
    let release: (r: Response) => void = () => {};
    const f = vi.fn((_u: string, init: RequestInit) => (init.method === "POST" ? new Promise<Response>((r) => (release = r)) : Promise.resolve(jsonResponse({}))));
    vi.stubGlobal("fetch", f);
    render(
      <LanguageProvider initialLang="en">
        <ToastProvider>
          <SetPasswordPage />
        </ToastProvider>
      </LanguageProvider>,
    );
    await enter(newPw(), "a-long-enough-password");
    await enter(confirmPw(), "a-long-enough-password");
    const btn = screen.getByRole("button", { name: "Save password" });
    await userEvent.click(btn);
    await waitFor(() => expect(btn).toBeDisabled());
    await userEvent.click(btn);
    expect(f.mock.calls.filter((c) => c[1].method === "POST")).toHaveLength(1);
    await act(async () => release(jsonResponse(makeUser())));
  });

  it("offers sign out as an escape", async () => {
    await setup();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalled();
  });

  it("sends a signed-out visitor to the login page", async () => {
    authState = { user: null, loading: false };
    await setup();
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("sends someone who already set their password home", async () => {
    authState = { user: makeUser({ must_change_password: false }), loading: false };
    await setup();
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("does not redirect while the session is still loading", async () => {
    authState = { user: null, loading: true };
    await setup();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders in Arabic: rtl page, password fields still ltr, messages translated", async () => {
    await setup("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(newPw()).toHaveAttribute("dir", "ltr");
    await userEvent.click(screen.getAllByRole("button").find((b) => b.getAttribute("type") === "submit")!);
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBe(2);
    for (const a of alerts) expect(a.textContent).toMatch(/[؀-ۿ]/);
  });
});
