"use client";

import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useT } from "@/lib/i18n";

type Toast = { id: number; kind: "success" | "error"; message: string; undo?: () => void };
type Api = {
  success: (m: string, opts?: { undo?: () => void }) => void;
  error: (m: string) => void;
};
const ToastContext = createContext<Api | null>(null);

const DURATION = 4000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const t = useT();
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((x) => x.id !== id)), []);

  const push = useCallback(
    (kind: Toast["kind"], message: string, undo?: () => void) => {
      const id = Date.now() + Math.random();
      setToasts((all) => [...all.slice(-2), { id, kind, message, undo }]);
      setTimeout(() => dismiss(id), DURATION);
    },
    [dismiss],
  );

  const api = useMemo<Api>(
    () => ({ success: (m, opts) => push("success", m, opts?.undo), error: (m) => push("error", m) }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* Bottom-centre above the tab bar on phones, top-end on desktop. */}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-[70] flex flex-col items-center gap-2 md:inset-x-auto md:end-6 md:top-20 md:bottom-auto md:items-end"
      >
        {toasts.map((x) => (
          <div
            key={x.id}
            className="pointer-events-auto flex w-full max-w-sm animate-pop items-center gap-3 rounded-card border border-line bg-surface p-3.5 text-body shadow-float"
          >
            {x.kind === "success" ? (
              <CheckCircle size={20} weight="fill" className="shrink-0 text-success" aria-hidden />
            ) : (
              <WarningCircle size={20} weight="fill" className="shrink-0 text-danger" aria-hidden />
            )}
            <p className="min-w-0 flex-1 text-ink">{x.message}</p>
            {x.undo ? (
              <button
                type="button"
                onClick={() => {
                  x.undo?.();
                  dismiss(x.id);
                }}
                className="rounded-control px-2 py-1 text-label text-primary-strong hover:bg-primary-tint"
              >
                {t("common.undo")}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
