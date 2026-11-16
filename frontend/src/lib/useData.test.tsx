import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookies, jsonResponse, stubFetch } from "@/test/utils";
import { useFetch } from "./useFetch";
import { useList } from "./useList";
import { useDebounced, useQuery } from "./useQuery";
import { useUrlParams } from "./useUrlParams";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }));

beforeEach(() => clearCookies());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  window.history.replaceState(null, "", "/");
});

describe("useFetch", () => {
  it("loads, then returns data", async () => {
    stubFetch(() => jsonResponse({ n: 1 }));
    const { result } = renderHook(() => useFetch<{ n: number }>("/things/"));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ n: 1 });
    expect(result.current.error).toBeNull();
  });

  it("waits while the path is null and makes no request", () => {
    const f = stubFetch(() => jsonResponse({}));
    const { result } = renderHook(() => useFetch(null));
    expect(result.current.loading).toBe(false);
    expect(f).not.toHaveBeenCalled();
  });

  it("reports the API error message and no data", async () => {
    stubFetch(() => jsonResponse({ error: { code: "x", message: "Record not found." } }, 404));
    const { result } = renderHook(() => useFetch("/things/9/"));
    await waitFor(() => expect(result.current.error).toBe("Record not found."));
    expect(result.current.data).toBeNull();
  });

  it("reports err.network when the network is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const { result } = renderHook(() => useFetch("/things/"));
    await waitFor(() => expect(result.current.error).toBe("err.network"));
  });

  it("reload() fetches again", async () => {
    let n = 0;
    const f = stubFetch(() => jsonResponse({ n: ++n }));
    const { result } = renderHook(() => useFetch<{ n: number }>("/things/"));
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data).toEqual({ n: 2 }));
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("refetches when the path changes", async () => {
    const f = stubFetch((url) => jsonResponse({ url }));
    const { result, rerender } = renderHook(({ p }) => useFetch<{ url: string }>(p), { initialProps: { p: "/a/" } });
    await waitFor(() => expect(result.current.data?.url).toBe("/api/v1/a/"));
    rerender({ p: "/b/" });
    await waitFor(() => expect(result.current.data?.url).toBe("/api/v1/b/"));
    expect(f).toHaveBeenCalledTimes(2);
  });
});

describe("useQuery", () => {
  it("keeps showing the previous data while a new query loads", async () => {
    let release: (r: Response) => void = () => {};
    const f = vi.fn((url: string) => (url.endsWith("/b/") ? new Promise<Response>((r) => (release = r)) : Promise.resolve(jsonResponse({ v: "a" }))));
    vi.stubGlobal("fetch", f);
    const { result, rerender } = renderHook(({ p }) => useQuery<{ v: string }>(p), { initialProps: { p: "/a/" } });
    await waitFor(() => expect(result.current.data).toEqual({ v: "a" }));
    rerender({ p: "/b/" });
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toEqual({ v: "a" });
    await act(async () => release(jsonResponse({ v: "b" })));
    await waitFor(() => expect(result.current.data).toEqual({ v: "b" }));
    expect(result.current.loading).toBe(false);
  });

  it("keeps the old data and surfaces the error when a later query fails", async () => {
    stubFetch((url) => (url.endsWith("/bad/") ? jsonResponse({ error: { message: "Nope." } }, 400) : jsonResponse({ v: "ok" })));
    const { result, rerender } = renderHook(({ p }) => useQuery<{ v: string }>(p), { initialProps: { p: "/ok/" } });
    await waitFor(() => expect(result.current.data).toEqual({ v: "ok" }));
    rerender({ p: "/bad/" });
    await waitFor(() => expect(result.current.error).toBe("Nope."));
    expect(result.current.data).toEqual({ v: "ok" });
  });

  it("does nothing for a null path", () => {
    const f = stubFetch(() => jsonResponse({}));
    const { result } = renderHook(() => useQuery(null));
    expect(result.current.loading).toBe(false);
    expect(f).not.toHaveBeenCalled();
  });
});

describe("useDebounced", () => {
  it("only settles after the delay", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ v }) => useDebounced(v, 300), { initialProps: { v: "a" } });
    rerender({ v: "ab" });
    rerender({ v: "abc" });
    expect(result.current).toBe("a");
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("a");
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("abc");
  });
});

describe("useList", () => {
  it("loads rows, then debounces the search and sends it URL-encoded", async () => {
    const f = stubFetch((url) => jsonResponse(url.includes("search=") ? [{ id: 2 }] : [{ id: 1 }]));
    const { result, rerender } = renderHook(({ s }) => useList<{ id: number }>("/clients/", s), { initialProps: { s: "" } });
    await waitFor(() => expect(result.current.data).toEqual([{ id: 1 }]));
    expect(result.current.searching).toBe(false);
    rerender({ s: "a&b c" });
    expect(f).toHaveBeenCalledTimes(1); // nothing is requested until typing pauses
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2), { timeout: 2000 });
    expect(f.mock.calls[1][0]).toBe("/api/v1/clients/?search=a%26b%20c");
    await waitFor(() => expect(result.current.data).toEqual([{ id: 2 }]));
    expect(result.current.searching).toBe(true);
  });

  it("keeps the previous rows when a reload fails and shows the error", async () => {
    let fail = false;
    stubFetch(() => (fail ? jsonResponse({ error: { message: "Server hiccup." } }, 500) : jsonResponse([{ id: 1 }])));
    const { result } = renderHook(() => useList<{ id: number }>("/clients/", ""));
    await waitFor(() => expect(result.current.data).toEqual([{ id: 1 }]));
    fail = true;
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.error).toBe("Server hiccup."));
    expect(result.current.data).toEqual([{ id: 1 }]);
  });
});

describe("useUrlParams", () => {
  it("reads the keys from the address bar, empty when absent", () => {
    window.history.replaceState(null, "", "/leads?q=acme&page=2");
    const { result } = renderHook(() => useUrlParams(["q", "page", "tab"] as const));
    expect(result.current[0]).toEqual({ q: "acme", page: "2", tab: "" });
  });

  it("writes with replaceState (no new history entry), drops empty values and keeps other params", () => {
    window.history.replaceState(null, "", "/leads?keep=1&q=old");
    const before = window.history.length;
    const spy = vi.spyOn(window.history, "replaceState");
    const { result } = renderHook(() => useUrlParams(["q", "page"] as const));
    act(() => result.current[1]({ q: "new", page: "3" }));
    expect(window.location.search).toBe("?keep=1&q=new&page=3");
    act(() => result.current[1]({ q: "" }));
    expect(window.location.search).toBe("?keep=1&page=3");
    act(() => result.current[1]({ page: "" }));
    expect(window.location.search).toBe("?keep=1");
    expect(spy).toHaveBeenCalledTimes(3);
    expect(window.history.length).toBe(before);
    spy.mockRestore();
  });

  it("leaves a clean path when the last param is removed", () => {
    window.history.replaceState(null, "", "/leads?q=x");
    const { result } = renderHook(() => useUrlParams(["q"] as const));
    act(() => result.current[1]({ q: "" }));
    expect(window.location.pathname + window.location.search).toBe("/leads");
  });
});
