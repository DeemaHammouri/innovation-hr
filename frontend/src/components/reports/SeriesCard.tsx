"use client";

import { useId, useState } from "react";
import { useMoney } from "@/components/quotations/quoteUi";
import { Card } from "@/components/ui/Card";
import { Segmented } from "@/components/ui/Segmented";
import type { ReportPoint, ReportSeries } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** The series' title key: money series carry their currency in the key (expected_JOD); the title does not. */
const baseKey = (s: ReportSeries) => (s.currency && s.key.endsWith(`_${s.currency}`) ? s.key.slice(0, -s.currency.length - 1) : s.key);

export function useReportText() {
  const { t, lang, formatNumber, formatMonthYear } = useI18n();
  const money = useMoney();
  const label = (p: ReportPoint) => {
    const own = lang === "ar" ? p.label_ar : p.label_en;
    if (own) return own;
    const m = /^(\d{4})-(\d{2})$/.exec(p.key);
    if (m) return formatMonthYear(new Date(Number(m[1]), Number(m[2]) - 1, 1));
    return t(`rep.k.${p.key}`);
  };
  const value = (s: ReportSeries, v: number | null) => {
    if (v === null) return t("rep.noData");
    if (s.unit === "money") return money(v, s.currency);
    if (s.unit === "percent") return `${formatNumber(v)}%`;
    if (s.unit === "hours") return t("rep.hours", { n: formatNumber(v) });
    return formatNumber(v);
  };
  const title = (s: ReportSeries) => t(`rep.s.${baseKey(s)}`) + (s.currency ? ` (${s.currency})` : "");
  return { label, value, title };
}

/**
 * One series as a chart and as a table. The bars are drawn in the blue token family; the table is the accessible alternative and
 * always shows how many records each value rests on. A value with nothing behind it says so instead of drawing a zero.
 */
export function SeriesCard({ s }: { s: ReportSeries }) {
  const { t, formatNumber } = useI18n();
  const { label, value, title } = useReportText();
  const [view, setView] = useState<"chart" | "table">("chart");
  const id = useId();
  const max = Math.max(0, ...s.points.map((p) => p.value ?? 0));
  const funnel = s.kind === "funnel";
  return (
    <Card as="section" aria-labelledby={`${id}-t`} className="p-4 md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id={`${id}-t`} className="text-section text-ink">{title(s)}</h3>
        <Segmented label={t("rep.view")} mode="tablist" value={view} onChange={setView} segments={[{ value: "chart", label: t("rep.view.chart") }, { value: "table", label: t("rep.view.table") }]} className="w-full sm:w-auto" />
      </div>
      {s.points.length === 0 ? (
        <p className="mt-4 text-label font-normal text-ink-2">{t("rep.empty")}</p>
      ) : view === "chart" ? (
        <ul className="mt-4 space-y-3">
          {s.points.map((p, i) => {
            const width = p.value === null || max === 0 ? 0 : Math.max(2, (p.value / max) * 100);
            return (
              <li key={`${p.key}-${i}`}>
                <div className="flex items-baseline justify-between gap-3 text-label">
                  <span className="min-w-0 truncate text-ink">{label(p)}</span>
                  <span dir="ltr" className="tnum shrink-0 font-semibold text-ink">{value(s, p.value)}</span>
                </div>
                <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-primary-tint" aria-hidden>
                  <div className={`h-full rounded-full ${funnel && i > 0 ? "bg-primary-strong" : "bg-primary"}`} style={{ width: `${width}%` }} />
                </div>
                {p.n !== null && s.unit !== "count" ? <p className="mt-0.5 text-caption text-ink-2">{t("rep.basedOn", { n: formatNumber(p.n) })}</p> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-label">
            <caption className="sr-only">{title(s)}</caption>
            <thead>
              <tr className="border-b border-line text-start text-ink-2">
                <th scope="col" className="py-2 pe-3 text-start font-semibold">{t("rep.col.item")}</th>
                <th scope="col" className="py-2 pe-3 text-end font-semibold">{t("rep.col.value")}</th>
                <th scope="col" className="py-2 text-end font-semibold">{t("rep.col.records")}</th>
              </tr>
            </thead>
            <tbody>
              {s.points.map((p, i) => (
                <tr key={`${p.key}-${i}`} className="border-b border-line last:border-0">
                  <th scope="row" className="py-2 pe-3 text-start font-normal text-ink">{label(p)}</th>
                  <td dir="ltr" className="tnum py-2 pe-3 text-end text-ink">{value(s, p.value)}</td>
                  <td dir="ltr" className="tnum py-2 text-end text-ink-2">{p.n === null ? "—" : formatNumber(p.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
