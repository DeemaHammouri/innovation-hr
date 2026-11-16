import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import type { User } from "@/lib/api";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { clearCookies, jsonResponse, makeUser, stubFetch } from "@/test/utils";
import { UserForm } from "./UserForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const departments = [
  { id: 1, name: "Administration" },
  { id: 2, name: "Marketing" },
  { id: 3, name: "Commercial" },
];
const me = makeUser({ id: 1, full_name: "Boss", role: "head", department: 1, department_name: "Administration" });

async function setup(opts: { editing?: User | null; lang?: Lang; handler?: (url: string, init: RequestInit) => Response; depts?: Response } = {}) {
  const { lang = "en", editing = null } = opts;
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  const f = stubFetch((url, init) => {
    if (url === "/api/v1/departments/") return opts.depts ?? jsonResponse(departments);
    return opts.handler ? opts.handler(url, init) : jsonResponse({});
  });
  render(
    <LanguageProvider initialLang={lang}>
      <ToastProvider>
        <UserForm editing={editing} me={me} />
      </ToastProvider>
    </LanguageProvider>,
  );
  await act(async () => {});
  const writes = () => f.mock.calls.filter((c) => c[1].method === "POST" || c[1].method === "PATCH");
  return { f, writes };
}

const fill = async (name: string, email: string) => {
  await userEvent.type(document.getElementById("field-full_name")!, name);
  await userEvent.type(document.getElementById("field-email")!, email);
};
const roleOptions = () => within(screen.getByLabelText(/^Role/)).getAllByRole("option").map((o) => (o as HTMLOptionElement).value);
const create = () => userEvent.click(screen.getByRole("button", { name: "Create user" }));

beforeEach(() => {
  clearCookies();
  push.mockClear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("UserForm: validation", () => {
  it("shows every missing field on submit, focuses the first, and sends nothing", async () => {
    const { writes } = await setup();
    await create();
    const alerts = screen.getAllByRole("alert").map((a) => a.textContent);
    expect(alerts).toEqual(expect.arrayContaining(["Enter the person's full name.", "Enter their email.", "Choose a department."]));
    expect(screen.getByLabelText(/Full name/)).toHaveFocus();
    expect(writes()).toHaveLength(0);
  });

  it("validates the email format on blur, and clears the message when the person returns to it", async () => {
    await setup();
    const email = screen.getByLabelText(/^Email/);
    await userEvent.type(email, "not-an-email");
    await userEvent.tab();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter an email like name@company.com.");
    await userEvent.click(email);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("never disables the submit button for invalid data", async () => {
    await setup();
    expect(screen.getByRole("button", { name: "Create user" })).toBeEnabled();
  });

  it("warns when the departments cannot be loaded", async () => {
    await setup({ depts: jsonResponse({ error: { message: "x" } }, 500) });
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load the departments.");
  });
});

describe("UserForm: role and department restriction", () => {
  it("offers both roles for an ordinary department, member first", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    expect(roleOptions()).toEqual(["member", "head"]);
    expect(screen.getByLabelText(/^Role/)).toHaveValue("member");
  });

  it("limits Administration to Head, and switches a Member selection to Head", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    expect(screen.getByLabelText(/^Role/)).toHaveValue("member");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "1");
    expect(roleOptions()).toEqual(["head"]);
    expect(screen.getByLabelText(/^Role/)).toHaveValue("head");
    expect(screen.getByText("Administration only has the CEO, who is its head.")).toBeInTheDocument();
  });

  it("keeps both roles again after moving away from Administration", async () => {
    await setup();
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "1");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "2");
    expect(roleOptions()).toEqual(["member", "head"]);
    expect(screen.getByText("Marketing has one person, who can have either role.")).toBeInTheDocument();
  });

  it("when editing yourself, department and role are locked with an explanation", async () => {
    await setup({ editing: me });
    expect(screen.getByLabelText(/Department/)).toBeDisabled();
    expect(screen.getByLabelText(/^Role/)).toBeDisabled();
    expect(screen.getByText("You can't change your own department.")).toBeInTheDocument();
    expect(screen.getByText("You can't change your own role.")).toBeInTheDocument();
  });

  it("when editing someone else, the form is prefilled and unlocked", async () => {
    const other = makeUser({ id: 7, full_name: "Sam Lee", email: "sam@x.com", department: 3, department_name: "Commercial", role: "member" });
    await setup({ editing: other });
    expect(screen.getByLabelText(/Full name/)).toHaveValue("Sam Lee");
    expect(screen.getByLabelText(/^Email/)).toHaveValue("sam@x.com");
    expect(screen.getByLabelText(/Department/)).toBeEnabled();
    expect(screen.getByLabelText(/Department/)).toHaveValue("3");
    expect(screen.getByRole("button", { name: "Save user" })).toBeInTheDocument();
  });
});

describe("UserForm: saving", () => {
  it("creates a user with a trimmed, typed payload, then shows the one-time credentials", async () => {
    document.cookie = "csrf_token=tok; path=/";
    const { writes } = await setup({
      handler: () => jsonResponse({ id: 11, full_name: "Dana Cole", email: "dana@x.com", temporary_password: "Tmp-Pass-1234" }, 201),
    });
    await fill("  Dana Cole ", " dana@x.com ");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    await create();
    const dialog = await screen.findByRole("dialog", { name: "User added" });
    expect(within(dialog).getByText("Tmp-Pass-1234")).toBeInTheDocument();
    const [url, init] = writes()[0];
    expect(url).toBe("/api/v1/users/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ full_name: "Dana Cole", email: "dana@x.com", department: 3, role: "member", preferred_language: "en" });
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    expect(push).toHaveBeenCalledWith("/users/11");
  });

  it("sends the page language as the new user's default language", async () => {
    const { writes } = await setup({ lang: "ar", handler: () => jsonResponse({ id: 1, temporary_password: "x" }, 201) });
    await fill("دانة", "d@x.com");
    await userEvent.selectOptions(document.getElementById("field-department")!, "3");
    await userEvent.click(screen.getAllByRole("button").find((b) => b.getAttribute("type") === "submit")!);
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(JSON.parse(String(writes()[0][1].body)).preferred_language).toBe("ar");
  });

  it("edits with PATCH to the user's URL and goes back to the profile", async () => {
    const other = makeUser({ id: 7, full_name: "Sam Lee", email: "sam@x.com", department: 3, role: "member" });
    const { writes } = await setup({ editing: other, handler: () => jsonResponse(other) });
    await userEvent.click(screen.getByRole("button", { name: "Save user" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/users/7"));
    expect(writes()[0][0]).toBe("/api/v1/users/7/");
    expect(writes()[0][1].method).toBe("PATCH");
  });

  it("puts a server field error beside the field, translated, and focuses it", async () => {
    await setup({
      handler: () => jsonResponse({ error: { code: "validation_error", message: "Fix.", fields: { email: ["Someone already uses this email."] } } }, 400),
    });
    await fill("Dana", "dana@x.com");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    await create();
    expect(await screen.findByRole("alert")).toHaveTextContent("Someone already uses this email.");
    expect(screen.getByLabelText(/^Email/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/^Email/)).toHaveFocus();
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a general failure message for server errors", async () => {
    await setup({ handler: () => jsonResponse({ error: { message: "boom" } }, 500) });
    await fill("Dana", "dana@x.com");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    await create();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create user" })).toBeEnabled();
  });

  it("guards against a double submit: the button locks while the request runs", async () => {
    let release: (r: Response) => void = () => {};
    const f = vi.fn((url: string, init: RequestInit) => {
      if (url === "/api/v1/departments/") return Promise.resolve(jsonResponse(departments));
      if (init.method === "POST") return new Promise<Response>((r) => (release = r));
      return Promise.resolve(jsonResponse({}));
    });
    vi.stubGlobal("fetch", f);
    document.documentElement.lang = "en";
    render(
      <LanguageProvider initialLang="en">
        <ToastProvider>
          <UserForm editing={null} me={me} />
        </ToastProvider>
      </LanguageProvider>,
    );
    await act(async () => {});
    await fill("Dana", "dana@x.com");
    await userEvent.selectOptions(screen.getByLabelText(/Department/), "3");
    const btn = screen.getByRole("button", { name: "Create user" });
    await userEvent.click(btn);
    await waitFor(() => expect(btn).toBeDisabled());
    expect(btn).toHaveAttribute("aria-busy", "true");
    await userEvent.click(btn);
    expect(f.mock.calls.filter((c) => c[1].method === "POST")).toHaveLength(1);
    await act(async () => release(jsonResponse({ id: 2, full_name: "Dana", email: "dana@x.com", temporary_password: "p" }, 201)));
  });
});

describe("UserForm in Arabic", () => {
  it("is rtl, keeps the email field ltr, and shows Arabic labels and errors", async () => {
    await setup({ lang: "ar" });
    expect(document.documentElement.dir).toBe("rtl");
    const submit = screen.getAllByRole("button").find((b) => b.getAttribute("type") === "submit")!;
    await userEvent.click(submit);
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBeGreaterThanOrEqual(3);
    for (const a of alerts) expect(a.textContent).toMatch(/[؀-ۿ]/);
    expect(document.querySelector("input[type=email]")).toHaveAttribute("dir", "ltr");
  });
});
