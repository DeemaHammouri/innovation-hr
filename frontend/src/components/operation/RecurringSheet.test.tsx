import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import type { OpClient, RecurringTask } from "@/lib/api";
import { LanguageProvider } from "@/lib/i18n";
import type { Lang } from "@/lib/lang";
import { clearCookies, jsonResponse, stubFetch } from "@/test/utils";
import { RecurringSheet } from "./OpSheets";
import { useFrequencyLabel } from "./opUi";

const client = { id: 7, company_name: "Acme" } as OpClient;
const existing = {
  id: 3, client: 7, client_name: "Acme", title: "Close the books", description: "", frequency: "monthly", interval_days: null, day_rule: "nth_weekday", nth: -1, weekday: 3,
  weekend_policy: "previous", start_date: "2026-12-01", next_due: "2026-12-31", assignee: null, assignee_name: null, active: true,
} as RecurringTask;

async function setup(opts: { task?: RecurringTask; lang?: Lang } = {}) {
  const lang = opts.lang ?? "en";
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  const f = stubFetch((url) => (url.includes("/operations/assignees/") ? jsonResponse([]) : jsonResponse({ id: 1 })));
  render(
    <LanguageProvider initialLang={lang}>
      <ToastProvider>
        <RecurringSheet client={client} task={opts.task} onClose={() => {}} onDone={() => {}} />
      </ToastProvider>
    </LanguageProvider>,
  );
  await act(async () => {});
  const body = () => {
    const call = f.mock.calls.find((c) => c[1].method === "POST" || c[1].method === "PATCH");
    return call ? JSON.parse(String(call[1].body)) : null;
  };
  return { f, body };
}

const field = (name: string) => document.getElementById(`field-${name}`) as HTMLSelectElement | HTMLInputElement | null;
const choose = (name: string, value: string) => userEvent.selectOptions(field(name) as HTMLSelectElement, value);
const save = () => userEvent.click(screen.getByRole("button", { name: /Add recurring task|^Save$/ }));

beforeEach(clearCookies);
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("RecurringSheet: rule types", () => {
  it("offers every working day as a frequency", async () => {
    await setup();
    const options = Array.from((field("frequency") as HTMLSelectElement).options).map((o) => o.value);
    expect(options).toEqual(["daily", "workdays", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom"]);
  });

  it("asks which day of the month only for month-based frequencies", async () => {
    await setup();
    for (const f of ["monthly", "quarterly", "semiannual", "yearly"]) {
      await choose("frequency", f);
      expect(field("day_rule"), f).not.toBeNull();
    }
    for (const f of ["daily", "workdays", "weekly", "biweekly", "custom"]) {
      await choose("frequency", f);
      expect(field("day_rule"), f).toBeNull();
    }
  });

  it("shows the n-th and the weekday only for 'a weekday of the month'", async () => {
    await setup();
    expect(field("nth")).toBeNull();
    await choose("day_rule", "last_workday");
    expect(field("nth")).toBeNull();
    await choose("day_rule", "nth_weekday");
    expect(field("nth")).not.toBeNull();
    expect(field("weekday")).not.toBeNull();
    expect(Array.from((field("nth") as HTMLSelectElement).options).map((o) => o.value)).toEqual(["1", "2", "3", "4", "-1"]);
    expect(Array.from((field("weekday") as HTMLSelectElement).options)).toHaveLength(7);
  });

  it("has no weekend policy for 'every working day', which always skips closed days", async () => {
    await setup();
    expect(field("weekend_policy")).not.toBeNull();
    await choose("frequency", "workdays");
    expect(field("weekend_policy")).toBeNull();
  });

  it("sends the first and last working day rules and the chosen policy", async () => {
    const { body } = await setup();
    await userEvent.type(field("title")!, "Reconcile");
    await choose("day_rule", "last_workday");
    await choose("weekend_policy", "keep");
    await save();
    expect(body()).toMatchObject({ client: 7, title: "Reconcile", frequency: "monthly", day_rule: "last_workday", nth: null, weekday: null, weekend_policy: "keep" });
  });

  it("sends the n-th weekday as numbers", async () => {
    const { body } = await setup();
    await userEvent.type(field("title")!, "Review");
    await choose("day_rule", "nth_weekday");
    await choose("nth", "-1");
    await choose("weekday", "3");
    await save();
    expect(body()).toMatchObject({ day_rule: "nth_weekday", nth: -1, weekday: 3, weekend_policy: "next" });
  });

  it("never sends a stale day rule after switching to a weekly rule", async () => {
    const { body } = await setup();
    await userEvent.type(field("title")!, "Weekly");
    await choose("day_rule", "nth_weekday");
    await choose("frequency", "weekly");
    await save();
    expect(body()).toMatchObject({ frequency: "weekly", day_rule: "date", nth: null, weekday: null });
  });

  it("fills the form from an existing rule when editing", async () => {
    const { body } = await setup({ task: existing });
    expect(field("day_rule")!.value).toBe("nth_weekday");
    expect(field("nth")!.value).toBe("-1");
    expect(field("weekday")!.value).toBe("3");
    expect(field("weekend_policy")!.value).toBe("previous");
    await save();
    expect(body()).toMatchObject({ day_rule: "nth_weekday", nth: -1, weekday: 3, weekend_policy: "previous" });
  });

  it("shows the field error the server sends for a rule field", async () => {
    const f = stubFetch((url) => (url.includes("/assignees/") ? jsonResponse([]) : jsonResponse({ error: { code: "validation_error", message: "x", fields: { day_rule: ["Choose which day of the month it falls on."] } } }, 400)));
    render(
      <LanguageProvider initialLang="en">
        <ToastProvider>
          <RecurringSheet client={client} onClose={() => {}} onDone={() => {}} />
        </ToastProvider>
      </LanguageProvider>,
    );
    await act(async () => {});
    await userEvent.type(field("title")!, "X");
    await save();
    expect(await screen.findByText("Choose which day of the month it falls on.")).toBeInTheDocument();
    expect(f).toHaveBeenCalled();
  });

  it("is available in Arabic", async () => {
    await setup({ lang: "ar" });
    expect(screen.getByText("أي يوم من الشهر")).toBeInTheDocument();
    expect(screen.getByText("إذا صادف التاريخ عطلة أسبوعية أو رسمية")).toBeInTheDocument();
  });
});

describe("useFrequencyLabel", () => {
  const label = (r: Parameters<ReturnType<typeof useFrequencyLabel>>[0], lang: Lang = "en") =>
    renderHook(() => useFrequencyLabel(), { wrapper: ({ children }) => <LanguageProvider initialLang={lang}>{children}</LanguageProvider> }).result.current(r);

  it("describes the plain rules as before", () => {
    expect(label({ frequency: "monthly", interval_days: null })).toBe("Every month");
    expect(label({ frequency: "custom", interval_days: 45 })).toBe("Every 45 days");
    expect(label({ frequency: "workdays", interval_days: null })).toBe("Every working day");
  });

  it("adds the day rule to a month-based rule", () => {
    expect(label({ frequency: "monthly", interval_days: null, day_rule: "last_workday", nth: null, weekday: null })).toBe("Every month · Last working day");
    expect(label({ frequency: "quarterly", interval_days: null, day_rule: "first_workday", nth: null, weekday: null })).toBe("Every 3 months · First working day");
    expect(label({ frequency: "monthly", interval_days: null, day_rule: "nth_weekday", nth: 2, weekday: 1 })).toBe("Every month · 2nd Tuesday");
    expect(label({ frequency: "monthly", interval_days: null, day_rule: "nth_weekday", nth: -1, weekday: 3 })).toBe("Every month · Last Thursday");
    expect(label({ frequency: "monthly", interval_days: null, day_rule: "date", nth: null, weekday: null })).toBe("Every month");
  });

  it("reads in Arabic too", () => {
    expect(label({ frequency: "monthly", interval_days: null, day_rule: "nth_weekday", nth: 2, weekday: 1 }, "ar")).toContain("الثاني الثلاثاء");
  });
});
