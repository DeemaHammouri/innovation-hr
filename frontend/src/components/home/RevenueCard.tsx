"use client";

import { useMoney } from "@/components/quotations/quoteUi";
import { useReportText } from "@/components/reports/SeriesCard";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/States";
import type { Report } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const MONTHS = 6;

function isoDay(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Expected against received for the last six months, from the Revenue report. The table under the bars is the accessible version. */
export function RevenueCard() {
  const { t } = useI18n();
  const money = useMoney();
  const { label } = useReportText();
  const now = new Date();
  const from = isoDay(new Date(now.getFullYear(), now.getMonth() - (MONTHS - 1), 1));
  const to = isoDay(new Date(now.getFullYear(), now.getMonth() + 1, 0));
  const { data, loading } = useFetch<Report>(`/reports/revenue/?from=${from}&to=${to}`);
  const exp = data?.series.find((s) => s.key.startsWith("expected_"));
  const rec = data?.series.find((s) => s.key.startsWith("received_"));
  const keys = [...new Set([...(exp?.points ?? []), ...(rec?.points ?? [])].map((p) => p.key))].sort();
  const at = (s: typeof exp, key: string) => s?.points.find((p) => p.key === key)?.value ?? 0;
  const max = Math.max(1, ...keys.map((k) => Math.max(at(exp, k), at(rec, k))));
  const cur = exp?.currency;
  const sumExpected = keys.reduce((n, k) => n + at(exp, k), 0);
  const sumReceived = keys.reduce((n, k) => n + at(rec, k), 0);
  const monthLabel = (key: string) => label({ key, value: 0, n: null });

  return (
    <Card as="section" aria-labelledby="revenue-title" className="p-5 md:p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="revenue-title" className="text-section text-ink">{t("home.revenue")}</h2>
        <span className="text-label font-normal text-ink-2">{t("home.last6")}</span>
      </div>
      {loading && !data ? (
        <Skeleton className="h-40" />
      ) : keys.length === 0 || !cur ? (
        <p className="text-body text-ink-2">{t("rep.empty")}</p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-x-8 gap-y-2">
            <p>
              <span className="block text-label font-normal text-ink-2">{t("home.expected")}</span>
              <span className="tnum text-[length:var(--text-title)] font-bold text-ink">{money(sumExpected, cur)}</span>
            </p>
            <p>
              <span className="block text-label font-normal text-ink-2">{t("home.received")}</span>
              <span className="tnum text-[length:var(--text-title)] font-bold text-primary-strong">{money(sumReceived, cur)}</span>
            </p>
          </div>
          <div className="flex h-32 items-end gap-3 border-b border-line" aria-hidden>
            {keys.map((k) => (
              <div key={k} className="flex h-full min-w-0 flex-1 items-end justify-center gap-1">
                <span className="rise-bar block w-3 rounded-t bg-ink-3 md:w-4" style={{ height: `${(at(exp, k) / max) * 100}%` }} />
                <span className="rise-bar block w-3 rounded-t bg-primary md:w-4" style={{ height: `${(at(rec, k) / max) * 100}%`, animationDelay: "60ms" }} />
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-3" aria-hidden>
            {keys.map((k) => <span key={k} className="min-w-0 flex-1 truncate text-center text-[11px] font-normal text-ink-2">{monthLabel(k)}</span>)}
          </div>
          <p className="mt-3 flex items-center gap-4 text-label font-normal text-ink-2" aria-hidden>
            <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-ink-3" />{t("home.expected")}</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-primary" />{t("home.received")}</span>
          </p>
          <table className="sr-only">
            <caption>{t("home.revenue")} ({cur})</caption>
            <thead>
              <tr><th scope="col">{t("rep.col.item")}</th><th scope="col">{t("home.expected")}</th><th scope="col">{t("home.received")}</th></tr>
            </thead>
            <tbody>
              {keys.map((k) => <tr key={k}><th scope="row">{monthLabel(k)}</th><td>{money(at(exp, k), cur)}</td><td>{money(at(rec, k), cur)}</td></tr>)}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}
