"use client";

import { DownloadSimple, Info } from "@phosphor-icons/react";
import { SeriesCard } from "@/components/reports/SeriesCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useMoney } from "@/components/quotations/quoteUi";
import { downloadFile, errorMessage, type Report } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useUrlParams } from "@/lib/useUrlParams";

const KEYS = ["tab", "from", "to"] as const;
const ORDER = ["funnel", "revenue", "forecast", "operations", "hr"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function ReportsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  const index = useFetch<{ sections: string[] }>(user ? "/reports/" : null);
  if (!user) return null;
  const sections = ORDER.filter((s) => index.data?.sections.includes(s));
  const tab = sections.includes(params.tab) ? params.tab : sections[0];
  return (
    <>
      <PageHeader title={t("rep.title")} description={t("rep.description")} />
      {index.error ? <ErrorState message={index.error} onRetry={index.reload} /> : null}
      {!index.data && !index.error ? <Skeleton className="h-10 w-full max-w-md rounded-control" /> : null}
      {tab ? (
        <>
          {sections.length > 1 ? (
            <Segmented label={t("rep.tabs")} mode="tablist" value={tab} onChange={(v) => setParams({ tab: v, from: "", to: "" })} segments={sections.map((s) => ({ value: s, label: t(`rep.tab.${s}`) }))} className="mb-5 w-full md:w-fit" />
          ) : null}
          <Section key={tab} section={tab} from={params.from} to={params.to} setPeriod={(p) => setParams(p)} />
        </>
      ) : null}
    </>
  );
}

function Section({ section, from, to, setPeriod }: { section: string; from: string; to: string; setPeriod: (p: { from?: string; to?: string }) => void }) {
  const { t, lang, msg, formatDate, formatNumber } = useI18n();
  const toast = useToast();
  const money = useMoney();
  const days = section === "forecast" ? 365 : 90;
  const today = new Date();
  const end = to || iso(today);
  const start = from || iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - days + 1));
  const qs = `from=${start}&to=${end}`;
  const { data, error, loading, reload } = useFetch<Report>(`/reports/${section}/?${qs}`);
  const show = useDelayed(loading);
  async function exportAs(kind: "csv" | "xlsx" | "pdf") {
    try {
      await downloadFile(`/reports/${section}/export/?${qs}&fmt=${kind}&lang=${lang}`, `report-${section}-${start}-${end}.${kind}`);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  const m = data?.method;
  return (
    <div className="max-w-4xl space-y-5 md:space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 sm:flex-none"><Input name="from" label={t("rep.from")} type="date" max={end} value={start} onChange={(e) => e.target.value && setPeriod({ from: e.target.value })} /></div>
        <div className="min-w-0 flex-1 sm:flex-none"><Input name="to" label={t("rep.to")} type="date" min={start} max={iso(today)} value={end} onChange={(e) => e.target.value && setPeriod({ to: e.target.value })} /></div>
        <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={() => exportAs("csv")} disabled={!data}>{t("rep.export")}</Button>
        <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={() => exportAs("xlsx")} disabled={!data}>{t("rep.exportXlsx")}</Button>
        <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={() => exportAs("pdf")} disabled={!data}>{t("rep.exportPdf")}</Button>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        show ? <div className="space-y-4" aria-busy="true"><Skeleton className="h-40 rounded-card" /><Skeleton className="h-40 rounded-card" /></div> : <div className="h-40" />
      ) : (
        <div className={`space-y-5 md:space-y-6 ${loading ? "opacity-70" : ""}`}>
          <p className="text-label font-normal text-ink-2">{t("rep.period", { from: formatDate(data.period.from), to: formatDate(data.period.to) })}{section !== "forecast" ? ` · ${t("rep.records", { n: formatNumber(data.records) })}` : ""}</p>
          {section === "forecast" && m ? (
            <section aria-labelledby="fc-method" className="rounded-card border border-primary-line bg-primary-tint p-4 md:p-5">
              <h3 id="fc-method" className="flex items-center gap-2 text-section text-ink"><Info size={20} aria-hidden />{t("rep.fc.method")}</h3>
              {data.refused ? (
                <p className="mt-2 text-body text-ink">{t("rep.fc.refused", { decided: formatNumber(m.decided), left: formatNumber(m.left_early), min: formatNumber(m.min_sample), from: formatDate(m.window_from), to: formatDate(m.window_to) })}</p>
              ) : (
                <>
                  <p className="mt-2 text-body text-ink">{t("rep.fc.how", { conf: formatNumber(Math.round((m.p_confirmed ?? 0) * 100)), sent: formatNumber(Math.round((m.p_sent ?? 0) * 100)) })}</p>
                  <p className="mt-2 text-label font-normal text-ink-2">{t("rep.fc.basis", { decided: formatNumber(m.decided), left: formatNumber(m.left_early), open: formatNumber(m.open_quotations ?? 0), from: formatDate(m.window_from), to: formatDate(m.window_to) })}</p>
                </>
              )}
              <p className="mt-2 text-label font-normal text-ink-2">{t("rep.fc.unpaid", { n: formatNumber(data.unpaid_records ?? 0) })}</p>
            </section>
          ) : null}
          {data.kpis && Object.keys(data.kpis).length ? (
            <section aria-label={t("rep.s.overdue")} className="grid gap-3 sm:grid-cols-2">
              {Object.entries(data.kpis).map(([cur, k]) => (
                <div key={cur} className="rounded-card border border-line bg-surface p-4">
                  <p className="text-label font-normal text-ink-2">{t("rep.kpi.overdue", { cur })}</p>
                  <p dir="ltr" className="tnum mt-1 text-section text-ink">{money(k.overdue_total, cur)}</p>
                  <p className="text-caption text-ink-2">{t("rep.kpi.instalments", { n: formatNumber(k.overdue_instalments) })}</p>
                </div>
              ))}
            </section>
          ) : null}
          {data.series.length === 0 ? (
            <EmptyState icon={<Info size={24} aria-hidden />} title={t("rep.empty")} description={t("rep.emptyText")} />
          ) : (
            data.series.map((s) => <SeriesCard key={s.key} s={s} />)
          )}
        </div>
      )}
    </div>
  );
}
