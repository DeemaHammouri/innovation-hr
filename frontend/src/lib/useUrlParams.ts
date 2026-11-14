"use client";

import { useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * List filters that live in the address bar, so a refresh or a shared link keeps the search.
 * Updates use replaceState: no new history entry per keystroke, and no page reload.
 */
export function useUrlParams<K extends string>(keys: readonly K[]) {
  const search = useSearchParams();
  const values = Object.fromEntries(keys.map((k) => [k, search.get(k) ?? ""])) as Record<K, string>;

  const set = useCallback(
    (patch: Partial<Record<K, string>>) => {
      const next = new URLSearchParams(window.location.search);
      for (const [k, v] of Object.entries(patch) as [K, string][]) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      const qs = next.toString();
      window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
    },
    [],
  );

  return [values, set] as const;
}
