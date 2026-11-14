"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";

type Result<T> = { key: string; data: T | null; error: string | null };

/** One GET with loading, error and retry. Pass null to wait (for example until a permission is known). */
export function useFetch<T>(path: string | null) {
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<Result<T>>({ key: "", data: null, error: null });
  const key = `${path}|${version}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => !cancelled && setResult({ key, data, error: null }))
      .catch((err) => !cancelled && setResult({ key, data: null, error: errorMessage(err, "err.loadList") }));
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const loading = path !== null && result.key !== key;
  return { data: loading ? null : result.data, error: loading ? null : result.error, loading, reload };
}
