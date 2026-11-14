"use client";

import { WarningCircle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { Button } from "./Button";

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`flex flex-col items-center px-6 text-center ${compact ? "py-8" : "py-14"}`}>
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-primary-tint text-primary-strong">{icon}</div>
      <h2 className="text-section text-ink">{title}</h2>
      <p className="mt-1 max-w-sm text-body text-ink-2">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t, msg } = useI18n();
  return (
    <div role="alert" className="flex flex-col items-center rounded-card border border-line bg-surface px-6 py-12 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-danger-bg text-danger-ink">
        <WarningCircle size={24} aria-hidden />
      </div>
      <h2 className="text-section text-ink">{t("state.loadFailed")}</h2>
      <p className="mt-1 max-w-sm text-body text-ink-2">{msg(message)}</p>
      <Button variant="secondary" className="mt-5" onClick={onRetry}>
        {t("common.tryAgain")}
      </Button>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** True only after `ms` of waiting, so quick loads never flash a skeleton. */
export function useDelayed(active: boolean, ms = 100) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!active) return;
    const t = setTimeout(() => setReady(true), ms);
    return () => {
      clearTimeout(t);
      setReady(false);
    };
  }, [active, ms]);
  return active && ready;
}

/** Rows that match the final list: avatar, two lines, a short value. */
export function RowsSkeleton({ rows = 6 }: { rows?: number }) {
  const { t } = useI18n();
  return (
    <div className="divide-y divide-line" aria-busy="true" aria-label={t("common.loading")}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3.5">
          <Skeleton className="size-10 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="hidden h-4 w-24 md:block" />
        </div>
      ))}
    </div>
  );
}
