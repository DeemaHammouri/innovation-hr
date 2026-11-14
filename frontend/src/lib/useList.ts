"use client";

import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";

type Result<T> = { key: string; rows: T[] | null; error: string | null };

/** Loads a list from the API. `search` is debounced so we don't call the server on every keystroke. */
export function useList<T>(path: string, search: string) {
  const [query, setQuery] = useState(search);
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<Result<T>>({ key: "", rows: null, error: null });

  useEffect(() => {
    const t = setTimeout(() => setQuery(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const key = `${path}|${query}|${version}`;

  useEffect(() => {
    let cancelled = false;
    api<T[]>(`${path}${query ? `?search=${encodeURIComponent(query)}` : ""}`)
      .then((rows) => !cancelled && setResult({ key, rows, error: null }))
      .catch((err) =>
        !cancelled &&
        setResult((prev) => ({ key, rows: prev.rows, error: errorMessage(err, "err.loadList") })),
      );
    return () => {
      cancelled = true;
    };
  }, [path, query, key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const loading = result.key !== key;
  return {
    data: result.rows,
    error: loading ? null : result.error,
    loading,
    reload,
    searching: query !== "",
  };
}
