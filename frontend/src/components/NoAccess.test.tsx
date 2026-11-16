import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";
import { jsonResponse, renderWithLang, stubFetch } from "@/test/utils";
import { NoAccess } from "./NoAccess";
import { StatusPage } from "./StatusPage";

beforeEach(() => {
  stubFetch(() => jsonResponse({ error: { message: "x" } }, 401));
});
afterEach(() => vi.unstubAllGlobals());

describe("NoAccess", () => {
  it("explains the problem and links home", () => {
    renderWithLang(<NoAccess />);
    expect(screen.getByRole("heading", { name: "This page isn't available for your role" })).toBeInTheDocument();
    expect(screen.getByText("If you think you should have access, ask the CEO.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Home" })).toHaveAttribute("href", "/");
  });

  it("is translated in Arabic", () => {
    renderWithLang(<NoAccess />, "ar");
    expect(screen.queryByText("Go to Home")).toBeNull();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
    expect(screen.getByRole("heading").textContent).toMatch(/[؀-ۿ]/);
  });
});

async function renderStatus(ui: React.ReactElement, lang: "en" | "ar" = "en") {
  document.documentElement.lang = lang;
  const out = render(
    <LanguageProvider initialLang={lang}>
      <AuthProvider>{ui}</AuthProvider>
    </LanguageProvider>,
  );
  await act(async () => {}); // let the session check settle
  return out;
}

describe("StatusPage", () => {
  it.each([
    ["notFound", "We can't find that page"],
    ["noAccess", null],
    ["expired", null],
    ["error", null],
    ["offline", null],
  ] as const)("renders the %s message with a heading and a way back", async (kind, title) => {
    await renderStatus(<StatusPage kind={kind} href="/login" action="Back" />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBeTruthy();
    expect(h1.textContent).not.toMatch(/^status\./);
    if (title) expect(h1).toHaveTextContent(title);
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute("href", "/login");
  });

  it("uses a button when an onAction handler is given, instead of a link", async () => {
    const onAction = vi.fn();
    await renderStatus(<StatusPage kind="offline" href="/" action="Retry" onAction={onAction} />);
    expect(screen.queryByRole("link", { name: "Retry" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("includes the language switcher so a person can read it in their own language", async () => {
    await renderStatus(<StatusPage kind="notFound" href="/" action="Home" />);
    expect(screen.getByRole("radiogroup", { name: "Language · اللغة" })).toBeInTheDocument();
  });

  it("is translated in Arabic", async () => {
    await renderStatus(<StatusPage kind="notFound" href="/" action="الرئيسية" />, "ar");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/[؀-ۿ]/);
  });
});
