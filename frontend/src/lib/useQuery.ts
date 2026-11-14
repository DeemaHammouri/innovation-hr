"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";

type Result<T> = { key: string; data: T | null; error: string | null };

/** Like useFetch, but keeps showing the previous rows while a new query loads, so filtering never flashes a skeleton. */
export function useQuery<T>(path: string | null) {
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<Result<T>>({ key: "", data: null, error: null });
  const key = `${path}|${version}`;
  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => !cancelled && setResult({ key, data, error: null }))
      .catch((err) => !cancelled && setResult((prev) => ({ key, data: prev.data, error: errorMessage(err, "err.loadList") })));
    return () => {
      cancelled = true;
    };
  }, [path, key]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const loading = path !== null && result.key !== key;
  return { data: result.data, error: loading ? null : result.error, loading, reload };
}

/** Debounces a fast-changing value (search text). */
export function useDebounced<V>(value: V, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}
