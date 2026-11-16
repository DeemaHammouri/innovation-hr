import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/utils";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "./States";
import { PAGE_SIZE, Pagination } from "./Pagination";

afterEach(() => vi.useRealTimers());

describe("EmptyState", () => {
  it("shows title, description and the action", () => {
    renderWithLang(<EmptyState icon={<svg data-testid="ic" />} title="No clients yet" description="Add your first client." action={<button>Add client</button>} />);
    expect(screen.getByRole("heading", { name: "No clients yet" })).toBeInTheDocument();
    expect(screen.getByText("Add your first client.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add client" })).toBeInTheDocument();
    expect(screen.getByTestId("ic")).toBeInTheDocument();
  });

  it("renders no action wrapper when there is no action", () => {
    renderWithLang(<EmptyState icon={null} title="T" description="D" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ErrorState", () => {
  it("is an alert with a translated message and a working retry", async () => {
    const onRetry = vi.fn();
    renderWithLang(<ErrorState message="Record not found." onRetry={onRetry} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("We couldn't load this");
    expect(alert).toHaveTextContent(en("err.recordNotFound"));
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("never shows an unknown raw backend message in Arabic", () => {
    renderWithLang(<ErrorState message="Stack trace: boom" onRetry={() => {}} />, "ar");
    expect(screen.getByRole("alert")).not.toHaveTextContent("boom");
    expect(screen.getByRole("button", { name: "إعادة المحاولة" })).toBeInTheDocument();
  });

  it("shows an unknown message as-is in English", () => {
    renderWithLang(<ErrorState message="Server busy" onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Server busy");
  });
});

import enJson from "@/locales/en.json";
function en(key: string) {
  return (enJson as Record<string, string>)[key];
}

describe("RowsSkeleton", () => {
  it("is a busy region with the requested number of rows", () => {
    renderWithLang(<RowsSkeleton rows={3} />);
    const region = screen.getByLabelText("Loading");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region.children).toHaveLength(3);
  });

  it("defaults to six rows", () => {
    renderWithLang(<RowsSkeleton />);
    expect(screen.getByLabelText("Loading").children).toHaveLength(6);
  });
});

describe("useDelayed", () => {
  it("stays false for quick loads and becomes true after the delay", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDelayed(true, 100));
    expect(result.current).toBe(false);
    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(result.current).toBe(false);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe(true);
  });

  it("never shows when the load finishes before the delay", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ a }) => useDelayed(a, 100), { initialProps: { a: true } });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    rerender({ a: false });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current).toBe(false);
  });
});

describe("Pagination", () => {
  it("renders nothing when everything fits on one page", () => {
    renderWithLang(<Pagination page={1} total={PAGE_SIZE} onPage={() => {}} />);
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("shows the range, disables Previous on page 1 and moves forward", async () => {
    const onPage = vi.fn();
    renderWithLang(<Pagination page={1} total={24} onPage={onPage} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toHaveTextContent("Showing 1-10 of 24");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("clamps the last range to the total and disables Next on the last page", async () => {
    const onPage = vi.fn();
    renderWithLang(<Pagination page={3} total={24} onPage={onPage} />);
    expect(screen.getByText(/Showing 21-24 of 24/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("formats the range with Western digits in Arabic", () => {
    renderWithLang(<Pagination page={2} total={1234} pageSize={20} onPage={() => {}} />, "ar");
    const text = screen.getByRole("navigation").textContent ?? "";
    expect(text).toMatch(/21/);
    expect(text).not.toMatch(/[٠-٩]/);
  });
});
