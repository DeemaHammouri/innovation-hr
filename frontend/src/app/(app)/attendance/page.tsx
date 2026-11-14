"use client";

import { Clock, DownloadSimple } from "@phosphor-icons/react";
import { useMemo } from "react";
import { Stat } from "@/components/payments/payUi";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { downloadFile, errorMessage, type AttendanceMine, type AttendanceRow, type AttendanceSummary, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const SIZE = 25;
const KEYS = ["tab", "month", "from", "to", "user", "late", "page"] as const;
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const thisMonth = () => iso(new Date()).slice(0, 7);

export default function AttendancePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  if (!user) return null;
  const report = ["ceo", "hr_head", "hr_member"].includes(user.role_key ?? "");
  const tab = report && params.tab === "report" ? "report" : "mine";
  return (
    <>
      <PageHeader title={t("att.title")} description={t("att.description")} />
      {report ? (
        <Segmented
          label={t("att.tabs")}
          mode="tablist"
          value={tab}
          onChange={(v) => setParams({ tab: v === "report" ? "report" : "", page: "" })}
          segments={[{ value: "mine", label: t("att.tab.mine") }, { value: "report", label: t("att.tab.report") }]}
          className="mb-5 w-full md:w-fit"
        />
      ) : null}
      {tab === "mine" ? <Mine params={params} setParams={setParams} /> : <Report params={params} setParams={setParams} />}
    </>
  );
}

type Tabs = { params: Record<(typeof KEYS)[number], string>; setParams: (p: Partial<Record<(typeof KEYS)[number], string>>) => void };

function DayRow({ r, showName }: { r: AttendanceRow; showName: boolean }) {
  const { t, formatDate, formatTime, formatNumber } = useI18n();
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="text-body font-semibold text-ink">{showName ? `${r.user_name} · ` : ""}{formatDate(r.date)}</p>
        <p className="text-label font-normal text-ink-2">
          {t("att.inOut", { from: formatTime(r.first_in), to: r.last_out ? formatTime(r.last_out) : t("att.stillOpen") })}
          {r.hours !== null ? ` · ${t("att.hours", { hours: formatNumber(r.hours) })}` : ""}
          {showName ? ` · ${r.department}` : ""}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {r.late ? <StatusPill tone="warning">{t("att.late", { minutes: formatNumber(r.minutes_late) })}</StatusPill> : <StatusPill tone="success">{t("att.onTime")}</StatusPill>}
        {r.open ? <StatusPill tone="neutral" dot={false}>{t("att.noSignOut")}</StatusPill> : null}
      </div>
    </li>
  );
}

function Summary({ s }: { s: AttendanceSummary }) {
  const { t, formatNumber } = useI18n();
  return (
    <section aria-label={t("att.summary")} className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label={t("att.days")} value={formatNumber(s.days)} />
      <Stat label={t("att.lateDays")} value={formatNumber(s.late_days)} tone={s.late_days ? "danger" : undefined} />
      <Stat label={t("att.totalHours")} value={formatNumber(s.hours)} />
      <Stat label={t("att.openDays")} value={formatNumber(s.open_days)} />
    </section>
  );
}

function useCsv(path: string, name: string) {
  const { msg } = useI18n();
  const toast = useToast();
  return async () => {
    try {
      await downloadFile(path, name);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  };
}

function Mine({ params, setParams }: Tabs) {
  const { t } = useI18n();
  const month = params.month || thisMonth();
  const { data, error, loading, reload } = useFetch<AttendanceMine>(`/hr/attendance/mine/?month=${month}`);
  const show = useDelayed(loading);
  const csv = useCsv(`/hr/attendance/mine/export/?month=${month}`, `attendance-${month}.csv`);
  return (
    <div className="max-w-3xl">
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-56">
          <Input name="month" label={t("att.month")} type="month" max={thisMonth()} value={month} onChange={(e) => e.target.value && setParams({ month: e.target.value === thisMonth() ? "" : e.target.value })} />
        </div>
        <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={csv}>{t("att.export")}</Button>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        show ? <RowsSkeleton /> : <div className="h-48" />
      ) : (
        <>
          <Summary s={data.summary} />
          <Card className="overflow-hidden">
            <p className="border-b border-line p-4 text-label font-normal text-ink-2">
              {t("att.rule", { start: data.work_hours.work_start, grace: data.work_hours.grace_minutes })}
            </p>
            {data.rows.length === 0 ? (
              <EmptyState icon={<Clock size={24} aria-hidden />} title={t("att.emptyTitle")} description={t("att.emptyText")} />
            ) : (
              <ul className="divide-y divide-line">{data.rows.map((r) => <DayRow key={r.date} r={r} showName={false} />)}</ul>
            )}
          </Card>
          <p className="mt-3 text-caption text-ink-3">{t("att.note")}</p>
        </>
      )}
    </div>
  );
}

function Report({ params, setParams }: Tabs) {
  const { t, formatNumber } = useI18n();
  const today = new Date();
  const to = params.to || iso(today);
  const from = params.from || iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6));
  const page = Math.max(1, Number(params.page) || 1);
  const people = useFetch<{ id: number; full_name: string; department: string }[]>("/hr/people/");
  const query = useMemo(() => {
    const q = new URLSearchParams({ from, to });
    if (params.user) q.set("user", params.user);
    if (params.late === "1") q.set("late", "1");
    return q.toString();
  }, [from, to, params.user, params.late]);
  const { data, error, loading, reload } = useQuery<Page<AttendanceRow> & { summary: AttendanceSummary }>(`/hr/attendance/?${query}&page=${page}&page_size=${SIZE}`);
  const show = useDelayed(loading && !data);
  const csv = useCsv(`/hr/attendance/export/?${query}`, `attendance-${from}-${to}.csv`);
  return (
    <div>
      <Card className="mb-5 space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input name="from" label={t("att.from")} type="date" max={to} value={from} onChange={(e) => e.target.value && setParams({ from: e.target.value, page: "" })} />
          <Input name="to" label={t("att.to")} type="date" min={from} max={iso(new Date())} value={to} onChange={(e) => e.target.value && setParams({ to: e.target.value, page: "" })} />
          <Select name="user" label={t("att.person")} value={params.user} onChange={(e) => setParams({ user: e.target.value, page: "" })} options={[{ value: "", label: t("att.everyone") }, ...(people.data ?? []).map((p) => ({ value: String(p.id), label: p.full_name }))]} />
          <div className="flex items-end">
            <label htmlFor="late-only" className="flex h-11 cursor-pointer items-center gap-2.5 text-label text-ink md:h-10">
              <input id="late-only" type="checkbox" checked={params.late === "1"} onChange={(e) => setParams({ late: e.target.checked ? "1" : "", page: "" })} className="size-4 accent-[var(--color-primary)]" />
              {t("att.lateOnly")}
            </label>
          </div>
        </div>
        <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={csv}>{t("att.export")}</Button>
      </Card>
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        show ? <RowsSkeleton /> : <div className="h-48" />
      ) : (
        <>
          <Summary s={data.summary} />
          <Card className="overflow-hidden">
            {data.results.length === 0 ? (
              <EmptyState icon={<Clock size={24} aria-hidden />} title={t("att.emptyReportTitle")} description={t("att.emptyReportText")} />
            ) : (
              <div className={loading ? "opacity-70 transition-opacity" : ""}>
                <p role="status" className="tnum border-b border-line p-4 text-label font-normal text-ink-2">{t("att.count", { count: formatNumber(data.count) })}</p>
                <ul className="divide-y divide-line">{data.results.map((r) => <DayRow key={`${r.user}-${r.date}`} r={r} showName />)}</ul>
                <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
