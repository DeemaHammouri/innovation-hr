"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/States";
import type { Report } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** Where a click on a stage goes. Stages without a filtered list open the module that owns them. */
function target(step: string) {
  if (step === "created") return "/leads?view=list";
  if (step === "contacted" || step === "qualified") return `/leads?view=list&status=${step}`;
  return "/contracts";
}

/** Leads to handed-over clients over the last 90 days. The numbers come from the Sales funnel report, so they follow the same visibility rules. */
export function FunnelStrip() {
  const { t, formatNumber } = useI18n();
  const { data, loading } = useFetch<Report>("/reports/funnel/");
  const steps = data?.series.find((s) => s.key === "funnel")?.points ?? [];
  const max = Math.max(1, ...steps.map((p) => p.value ?? 0));

  return (
    <Card as="section" aria-labelledby="funnel-title" className="p-5 md:p-6">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 id="funnel-title" className="text-section text-ink">{t("home.funnel")}</h2>
        <span className="text-label font-normal text-ink-2">{t("home.last90")}</span>
      </div>
      {loading && !data ? (
        <Skeleton className="h-20" />
      ) : steps.length === 0 ? (
        <p className="text-body text-ink-2">{t("rep.noData")}</p>
      ) : (
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {steps.map((p, i) => (
            <li key={p.key}>
              <Link href={target(p.key)} className="block rounded-control border border-line p-3 transition-colors hover:border-primary-line hover:bg-primary-tint/40">
                <span className="block truncate text-label font-normal text-ink-2">{t(`rep.k.${p.key}`)}</span>
                <span className="tnum mt-1 block text-[length:var(--text-title)] leading-none font-bold text-ink">{formatNumber(p.value ?? 0)}</span>
                <span className="mt-3 block h-1.5 overflow-hidden rounded-full bg-canvas" aria-hidden>
                  <span className="grow-bar block h-full rounded-full bg-primary" style={{ width: `${((p.value ?? 0) / max) * 100}%`, animationDelay: `${i * 40}ms` }} />
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
