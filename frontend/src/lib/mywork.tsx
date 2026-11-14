"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, type MyWork } from "./api";

type State = {
  data: MyWork | null;
  /** Per-section counts for the sidebar badges, keyed by nav key. */
  badges: Record<string, number>;
  unread: number;
  reload: () => void;
};

const MyWorkContext = createContext<State | null>(null);
const REFRESH_MS = 60_000;

/** One small request feeds the sidebar badges, the bell and the "My Work" list. It refreshes every minute and when the tab is focused again. */
export function MyWorkProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<MyWork | null>(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    api<MyWork>("/my-work/")
      .then((d) => !cancelled && setData(d))
      .catch(() => {}); // a failed refresh keeps the last numbers; the page itself shows real errors
    return () => {
      cancelled = true;
    };
  }, [tick]);

  useEffect(() => {
    const id = setInterval(reload, REFRESH_MS);
    const onVisible = () => document.visibilityState === "visible" && reload();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [reload]);

  const value = useMemo<State>(
    () => ({ data, badges: data?.badges ?? {}, unread: data?.unread_notifications ?? 0, reload }),
    [data, reload],
  );
  return <MyWorkContext.Provider value={value}>{children}</MyWorkContext.Provider>;
}

export function useMyWork() {
  const ctx = useContext(MyWorkContext);
  if (!ctx) throw new Error("useMyWork must be used inside MyWorkProvider");
  return ctx;
}
