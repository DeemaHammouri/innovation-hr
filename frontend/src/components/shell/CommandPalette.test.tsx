import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { ShellProvider, useShell } from "@/lib/shell";
import { jsonResponse, makeUser, stubFetch } from "@/test/utils";
import type { User } from "@/lib/api";
import { CommandPalette } from "./CommandPalette";

const push = vi.fn();
const changeLanguage = vi.fn();
const signOut = vi.fn();
let me: User = makeUser();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: me }),
  useChangeLanguage: () => changeLanguage,
  useSignOut: () => signOut,
}));

function Opener() {
  const { setPaletteOpen } = useShell();
  useEffect(() => setPaletteOpen(true), [setPaletteOpen]);
  return null;
}

async function open(lang: Lang = "en") {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  const out = render(
    <LanguageProvider initialLang={lang}>
      <ShellProvider>
        <Opener />
        <CommandPalette />
      </ShellProvider>
    </LanguageProvider>,
  );
  await screen.findByRole("dialog");
  return out;
}

const searchApi = (extra: Record<string, unknown> = {}) =>
  stubFetch((url) => {
    if (url.startsWith("/api/v1/users/")) return jsonResponse(extra.users ?? []);
    if (url.startsWith("/api/v1/clients/")) return jsonResponse(extra.clients ?? []);
    if (url.startsWith("/api/v1/search/")) return jsonResponse({ results: extra.records ?? [] });
    return jsonResponse({});
  });

beforeEach(() => {
  me = makeUser({ id: 9, capabilities: ["user.manage", "client.manage"] });
  push.mockClear();
  changeLanguage.mockClear();
  signOut.mockClear();
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("CommandPalette", () => {
  it("opens as a labelled modal dialog with the search box focused", async () => {
    searchApi();
    await open();
    expect(screen.getByRole("dialog", { name: "Search" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("combobox", { name: "Search" })).toHaveFocus();
  });

  it("suggests actions when empty, for this person's capabilities", async () => {
    searchApi();
    await open();
    expect(screen.getByRole("group", { name: "Suggested" })).toBeInTheDocument();
    const titles = screen.getAllByRole("option").map((o) => o.textContent);
    expect(titles).toEqual(expect.arrayContaining(["Add user", "Add client", "Switch language", "Sign out"]));
  });

  it("hides admin actions from someone without the capabilities", async () => {
    me = makeUser({ capabilities: [] });
    searchApi();
    await open();
    const titles = screen.getAllByRole("option").map((o) => o.textContent);
    expect(titles).not.toContain("Add user");
    expect(titles).not.toContain("Add client");
    expect(titles).toContain("Sign out");
  });

  it("marks the first option active and moves with ArrowDown / ArrowUp, wrapping around", async () => {
    searchApi();
    await open();
    const options = () => screen.getAllByRole("option");
    expect(options()[0]).toHaveAttribute("aria-selected", "true");
    const input = screen.getByRole("combobox");
    await userEvent.keyboard("{ArrowDown}");
    expect(options()[1]).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", options()[1].id);
    await userEvent.keyboard("{ArrowUp}{ArrowUp}");
    expect(options()[options().length - 1]).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{ArrowDown}");
    expect(options()[0]).toHaveAttribute("aria-selected", "true");
  });

  it("Enter runs the active entry and closes the palette", async () => {
    searchApi();
    await open();
    await userEvent.keyboard("{Enter}"); // first suggested: Add user
    expect(push).toHaveBeenCalledWith("/users/new");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull(), { timeout: 2000 });
  });

  it("clicking an option runs it", async () => {
    searchApi();
    await open();
    await userEvent.click(screen.getByRole("option", { name: "Switch language" }));
    expect(changeLanguage).toHaveBeenCalledWith("ar");
  });

  it("Switch language goes the other way from Arabic", async () => {
    searchApi();
    await open("ar");
    const opt = screen.getAllByRole("option").find((o) => o.id && /[؀-ۿ]/.test(o.textContent ?? "") && o.textContent?.includes("اللغة"));
    expect(opt).toBeTruthy();
    await userEvent.click(opt!);
    expect(changeLanguage).toHaveBeenCalledWith("en");
  });

  it("Sign out runs the sign-out hook", async () => {
    searchApi();
    await open();
    await userEvent.click(screen.getByRole("option", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalled();
  });

  it("Escape closes the palette", async () => {
    searchApi();
    await open();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull(), { timeout: 2000 });
  });

  it("typing filters pages immediately, and highlights the match", async () => {
    searchApi();
    await open();
    await userEvent.type(screen.getByRole("combobox"), "cli");
    const pages = await screen.findByRole("group", { name: "Pages" });
    expect(pages).toHaveTextContent("Clients");
    expect(pages.querySelector("mark")).toHaveTextContent("Cli");
    expect(screen.queryByRole("group", { name: "Suggested" })).toBeNull();
  });

  it("searches after a pause: encoded query to users, clients and records, then lists the hits", async () => {
    const f = searchApi({
      users: [{ id: 3, full_name: "Dana Cole", email: "dana@example.com", department_name: "HR", role: "head" }],
      clients: [{ id: 4, company_name: "Dana Trading", contact_person: "Dana", email: "", phone: "" }],
      records: [{ kind: "lead", id: 5, title: "Dana Lead", subtitle: "LD-5", href: "/leads/5" }],
    });
    await open();
    await userEvent.type(screen.getByRole("combobox"), "dan a");
    await waitFor(() => expect(screen.getByRole("group", { name: "People" })).toBeInTheDocument(), { timeout: 3000 });
    const urls = f.mock.calls.map((c) => c[0]);
    expect(urls).toEqual(expect.arrayContaining(["/api/v1/users/?search=dan%20a", "/api/v1/clients/?search=dan%20a", "/api/v1/search/?q=dan%20a"]));
    expect(screen.getByRole("group", { name: "Clients" })).toHaveTextContent("Dana Trading");
    expect(screen.getByRole("group", { name: "Leads" })).toHaveTextContent("Dana Lead");
  });

  it("choosing a person navigates and remembers them in this browser's recents", async () => {
    searchApi({ users: [{ id: 3, full_name: "Dana Cole", email: "dana@example.com", department_name: "HR", role: "head" }] });
    await open();
    await userEvent.type(screen.getByRole("combobox"), "dana");
    const option = await screen.findByRole("option", { name: /Dana Cole/ }, { timeout: 3000 });
    await userEvent.click(option);
    expect(push).toHaveBeenCalledWith("/users/3");
    expect(JSON.parse(localStorage.getItem("innovation.recent.9")!)[0]).toMatchObject({ kind: "user", id: 3, href: "/users/3" });
  });

  it("does not search users or clients without the capability, but still searches records", async () => {
    me = makeUser({ capabilities: [] });
    const f = searchApi();
    await open();
    await userEvent.type(screen.getByRole("combobox"), "zed");
    await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).startsWith("/api/v1/search/"))).toBe(true), { timeout: 3000 });
    expect(f.mock.calls.some((c) => String(c[0]).startsWith("/api/v1/users/"))).toBe(false);
    expect(f.mock.calls.some((c) => String(c[0]).startsWith("/api/v1/clients/"))).toBe(false);
  });

  it("shows a no-results message when nothing matches", async () => {
    searchApi();
    await open();
    await userEvent.type(screen.getByRole("combobox"), "qqqzzz");
    expect(await screen.findByText('No results for "qqqzzz"', undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Try a name, email or phone number.")).toBeInTheDocument();
  });

  it("lists recents first when the query is empty", async () => {
    localStorage.setItem("innovation.recent.9", JSON.stringify([{ kind: "client", id: 1, title: "Acme", subtitle: "Ann", href: "/clients/1" }]));
    searchApi();
    await open();
    expect(screen.getByRole("group", { name: "Recent" })).toHaveTextContent("Acme");
    await userEvent.click(screen.getByRole("option", { name: /Acme/ }));
    expect(push).toHaveBeenCalledWith("/clients/1");
  });

  it("works in Arabic: dialog is labelled in Arabic and the page is rtl", async () => {
    searchApi();
    await open("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("dialog").getAttribute("aria-label")).toMatch(/[؀-ۿ]/);
    expect(screen.queryByRole("group", { name: "Suggested" })).toBeNull();
  });

  it("does not render when closed", () => {
    render(
      <LanguageProvider initialLang="en">
        <ShellProvider>
          <CommandPalette />
        </ShellProvider>
      </LanguageProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    void act;
  });
});
