import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import type { Lead } from "@/lib/api";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { clearCookies, jsonResponse, stubFetch } from "@/test/utils";
import { ContactSheet } from "./LeadSheets";

const reasons = [
  { id: 1, name_en: "Too expensive", name_ar: "مكلف جدا", is_active: true },
  { id: 2, name_en: "Went elsewhere", name_ar: "ذهب لجهة أخرى", is_active: true },
  { id: 3, name_en: "Retired reason", name_ar: "قديم", is_active: false },
];

const lead = (over: Partial<Lead> = {}) => ({ id: 42, company_name: "Acme", status: "contacted", ...over }) as Lead;

async function setup(opts: { lead?: Lead; mode?: "contact" | "outcome"; initialOutcome?: "" | "waiting" | "rejected" | "accepted"; lang?: Lang; post?: (body: Record<string, unknown>) => Response }) {
  const { lang = "en" } = opts;
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  const onDone = vi.fn();
  const onClose = vi.fn();
  const f = stubFetch((url, init) => {
    if (url.startsWith("/api/v1/lookups/rejection-reasons/")) return jsonResponse(reasons);
    if (init.method === "POST") return opts.post ? opts.post(JSON.parse(String(init.body))) : jsonResponse(lead({ status: "waiting" }));
    return jsonResponse({});
  });
  render(
    <LanguageProvider initialLang={lang}>
      <ToastProvider>
        <ContactSheet lead={opts.lead ?? lead()} mode={opts.mode ?? "outcome"} initialOutcome={opts.initialOutcome} onClose={onClose} onDone={onDone} />
      </ToastProvider>
    </LanguageProvider>,
  );
  await act(async () => {}); // let the reasons list load
  const posts = () => f.mock.calls.filter((c) => c[1].method === "POST");
  return { f, onDone, onClose, posts };
}

const submit = () => userEvent.click(screen.getByRole("button", { name: /Record outcome|Log contact/ }));

beforeEach(() => {
  clearCookies();
  document.cookie = "csrf_token=tok; path=/";
});
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("ContactSheet: outcome mode", () => {
  it("requires an outcome and sends nothing without one", async () => {
    const { posts } = await setup({});
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose what happened: waiting, rejected or accepted.");
    expect(posts()).toHaveLength(0);
    expect(screen.queryByRole("radio", { name: /Contact only/ })).toBeNull();
  });

  it("clears the outcome error as soon as one is chosen", async () => {
    await setup({});
    await submit();
    await userEvent.click(screen.getByRole("radio", { name: /Waiting/ }));
    expect(screen.queryByText("Choose what happened: waiting, rejected or accepted.")).toBeNull();
  });

  it("Waiting shows a required follow-up date, and submitting without it is refused", async () => {
    const { posts } = await setup({});
    expect(screen.queryByLabelText(/Follow up on/)).toBeNull();
    await userEvent.click(screen.getByRole("radio", { name: /Waiting/ }));
    const date = screen.getByLabelText(/Follow up on/);
    expect(date).toBeRequired();
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a follow-up date.");
    expect(date).toHaveAttribute("aria-invalid", "true");
    expect(date).toHaveFocus();
    expect(posts()).toHaveLength(0);
  });

  it("Waiting with a date posts the outcome and the date, then reports done", async () => {
    const { posts, onDone } = await setup({});
    await userEvent.click(screen.getByRole("radio", { name: /Waiting/ }));
    await userEvent.type(screen.getByLabelText(/Follow up on/), "2099-01-15");
    await submit();
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    const [url, init] = posts()[0];
    expect(url).toBe("/api/v1/leads/42/outcome/");
    expect(JSON.parse(String(init.body))).toEqual({ outcome: "waiting", notes: "", next_follow_up: "2099-01-15" });
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
    expect(await screen.findByText("Outcome recorded.")).toBeInTheDocument();
  });

  it("Rejected asks for a reason (active ones only) and refuses to submit without it", async () => {
    const { posts } = await setup({});
    await userEvent.click(screen.getByRole("radio", { name: /Rejected/ }));
    const reason = await screen.findByLabelText(/Reason/);
    await waitFor(() => expect(within(reason).getAllByRole("option").length).toBeGreaterThan(1));
    const labels = within(reason).getAllByRole("option").map((o) => o.textContent);
    expect(labels).toContain("Too expensive");
    expect(labels).toContain("Went elsewhere");
    expect(labels).not.toContain("Retired reason");
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose why this lead was rejected.");
    expect(reason).toHaveAttribute("aria-invalid", "true");
    expect(posts()).toHaveLength(0);
  });

  it("Rejected with a reason posts the numeric reason and the note", async () => {
    const { posts, onDone } = await setup({ post: () => jsonResponse(lead({ status: "rejected" })) });
    await userEvent.click(screen.getByRole("radio", { name: /Rejected/ }));
    const reason = await screen.findByLabelText(/Reason/);
    await waitFor(() => expect(within(reason).getAllByRole("option").length).toBeGreaterThan(1));
    await userEvent.selectOptions(reason, "2");
    await userEvent.type(screen.getByLabelText("Extra detail (optional)"), "Chose a rival");
    await submit();
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(JSON.parse(String(posts()[0][1].body))).toEqual({ outcome: "rejected", notes: "", rejection_reason: 2, rejection_note: "Chose a rival" });
  });

  it("accepted needs neither a date nor a reason", async () => {
    const { posts, onDone } = await setup({ post: () => jsonResponse(lead({ status: "qualified" })) });
    await userEvent.click(screen.getByRole("radio", { name: /Initial acceptance/ }));
    expect(screen.queryByLabelText(/Follow up on/)).toBeNull();
    expect(screen.queryByLabelText(/Reason/)).toBeNull();
    await submit();
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(JSON.parse(String(posts()[0][1].body))).toMatchObject({ outcome: "accepted" });
  });

  it("starts with the outcome the move already chose", async () => {
    await setup({ initialOutcome: "rejected" });
    expect(screen.getByRole("radio", { name: /Rejected/ })).toBeChecked();
  });

  it("puts a server field error on the right field and keeps the sheet open", async () => {
    const { onDone } = await setup({
      post: () => jsonResponse({ error: { code: "validation_error", message: "Fix it.", fields: { next_follow_up: ["Choose today or a later date."] } } }, 400),
    });
    await userEvent.click(screen.getByRole("radio", { name: /Waiting/ }));
    await userEvent.type(screen.getByLabelText(/Follow up on/), "2099-01-15");
    await submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose today or a later date.");
    expect(screen.getByLabelText(/Follow up on/)).toHaveAttribute("aria-invalid", "true");
    expect(onDone).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows a general problem as a form-level alert when the server error has no field", async () => {
    await setup({ post: () => jsonResponse({ error: { code: "x", message: "This lead is already closed." } }, 400) });
    await userEvent.click(screen.getByRole("radio", { name: /Initial acceptance/ }));
    await submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("This lead is already closed.");
  });

  it("locks the submit button while saving so it cannot be sent twice", async () => {
    let release: (r: Response) => void = () => {};
    document.documentElement.lang = "en";
    const f = vi.fn((url: string, init: RequestInit) => {
      if (url.includes("rejection-reasons")) return Promise.resolve(jsonResponse(reasons));
      if (init.method === "POST") return new Promise<Response>((r) => (release = r));
      return Promise.resolve(jsonResponse({}));
    });
    vi.stubGlobal("fetch", f);
    render(
      <LanguageProvider initialLang="en">
        <ToastProvider>
          <ContactSheet lead={lead()} mode="outcome" initialOutcome="accepted" onClose={() => {}} onDone={() => {}} />
        </ToastProvider>
      </LanguageProvider>,
    );
    await act(async () => {});
    const btn = screen.getByRole("button", { name: "Record outcome" });
    await userEvent.click(btn);
    await waitFor(() => expect(btn).toBeDisabled());
    await userEvent.click(btn);
    expect(f.mock.calls.filter((c) => c[1].method === "POST")).toHaveLength(1);
    await act(async () => release(jsonResponse(lead())));
  });

  it("cancel closes without sending anything", async () => {
    const { onClose, posts } = await setup({});
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(posts()).toHaveLength(0);
  });
});

describe("ContactSheet: contact mode", () => {
  it("lets a first contact be logged with no outcome, sending the contact type", async () => {
    const { posts, onDone } = await setup({ mode: "contact", lead: lead({ status: "new" }), post: () => jsonResponse(lead({ status: "contacted" })) });
    expect(screen.getByRole("radio", { name: /Contact only/ })).toBeChecked();
    await userEvent.selectOptions(screen.getByLabelText("How were you in touch?"), "email");
    await submit();
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(posts()[0][0]).toBe("/api/v1/leads/42/interactions/");
    expect(JSON.parse(String(posts()[0][1].body))).toEqual({ outcome: "", notes: "", type: "email" });
  });

  it("requires an outcome when the lead is already waiting", async () => {
    const { posts } = await setup({ mode: "contact", lead: lead({ status: "waiting" }) });
    expect(screen.queryByRole("radio", { name: /Contact only/ })).toBeNull();
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Choose what happened");
    expect(posts()).toHaveLength(0);
  });
});

describe("ContactSheet in Arabic", () => {
  it("renders rtl, with reasons in Arabic and errors translated", async () => {
    await setup({ lang: "ar", initialOutcome: "rejected" });
    expect(document.documentElement.dir).toBe("rtl");
    const reason = await screen.findByRole("combobox", { name: /./ });
    await waitFor(() => expect(within(reason).getAllByRole("option").length).toBeGreaterThan(1));
    expect(within(reason).getAllByRole("option").map((o) => o.textContent)).toContain("مكلف جدا");
    await userEvent.click(screen.getAllByRole("button").filter((b) => b.getAttribute("type") === "submit")[0]);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/[؀-ۿ]/);
    expect(alert).not.toHaveTextContent("Choose why this lead was rejected.");
  });
});
