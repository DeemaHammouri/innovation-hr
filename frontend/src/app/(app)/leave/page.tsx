"use client";

import { CaretLeft, CaretRight, Plus } from "@phosphor-icons/react";
import { can, canAny } from "@/lib/can";
import { useState } from "react";
import { LeavePill, RejectSheet, RequestSheet, TypeSheet, isoDate, useTypeName } from "@/components/hr/LeaveSheets";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type LeaveBalance, type LeaveRequest, type LeaveType, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const KEYS = ["tab", "month", "page"] as const;
const SIZE = 20;
type Tab = "mine" | "requests" | "calendar" | "types";
type P = { params: Record<(typeof KEYS)[number], string>; setParams: (p: Partial<Record<(typeof KEYS)[number], string>>) => void };

export default function LeavePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  if (!user) return null;
  const decides = canAny(user, "hr.manage", "hr.leave_decide_hr_head");
  const canRequest = can(user, "hr.leave_request");
  const tabs: { value: Tab; label: string }[] = [
    ...(canRequest ? [{ value: "mine" as Tab, label: t("leave.tab.mine") }] : []),
    ...(decides ? [{ value: "requests" as Tab, label: t("leave.tab.requests") }] : []),
    { value: "calendar", label: t("leave.tab.calendar") },
    ...(can(user, "hr.manage") ? [{ value: "types" as Tab, label: t("leave.tab.types") }] : []),
  ];
  const tab = (tabs.find((x) => x.value === params.tab)?.value ?? tabs[0].value) as Tab;
  return (
    <>
      <PageHeader title={t("leave.title")} description={t("leave.description")} />
      {tabs.length > 1 ? <Segmented label={t("leave.tabs")} mode="tablist" value={tab} onChange={(v) => setParams({ tab: v === tabs[0].value ? "" : v, page: "" })} segments={tabs} className="mb-5 w-full md:w-fit" /> : null}
      {tab === "mine" ? <Mine params={params} setParams={setParams} /> : null}
      {tab === "requests" ? <Requests params={params} setParams={setParams} /> : null}
      {tab === "calendar" ? <CalendarTab params={params} setParams={setParams} /> : null}
      {tab === "types" ? <Types /> : null}
    </>
  );
}

function RequestRow({ r, showName, children }: { r: LeaveRequest; showName: boolean; children?: React.ReactNode }) {
  const { t, lang, formatDate, formatNumber } = useI18n();
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body font-semibold text-ink">{showName ? `${r.user_name} · ` : ""}{lang === "ar" ? r.type_ar : r.type_en}</p>
          <p className="text-label font-normal text-ink-2">
            {formatDate(r.start_date)} → {formatDate(r.end_date)} · {t("leave.days", { count: formatNumber(r.days) })}
            {!r.paid ? ` · ${t("leave.unpaid")}` : ""}
          </p>
          {r.reason ? <p className="whitespace-pre-line text-label font-normal text-ink-2">{r.reason}</p> : null}
          {r.status === "rejected" ? <p className="text-label font-normal text-ink-2">{t("leave.declinedBecause", { reason: r.decision_note })}</p> : null}
          {r.decided_by_name && r.status !== "cancelled" ? <p className="text-caption text-ink-2">{r.decided_by_name}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <LeavePill status={r.status} />
          {children}
        </div>
      </div>
    </li>
  );
}

function Mine({ params, setParams }: P) {
  const { t, msg, formatNumber } = useI18n();
  const toast = useToast();
  const name = useTypeName();
  const page = Math.max(1, Number(params.page) || 1);
  const balance = useFetch<{ year: number; balances: LeaveBalance[] }>("/hr/leave/balance/");
  const { data, error, loading, reload } = useQuery<Page<LeaveRequest>>(`/hr/leave/?scope=mine&page=${page}&page_size=${SIZE}`);
  const show = useDelayed(loading && !data);
  const [open, setOpen] = useState(false);
  async function cancel(r: LeaveRequest) {
    try {
      await api(`/hr/leave/${r.id}/cancel/`, { method: "POST", body: {} });
      toast.success(t("leave.cancelled"));
      reload();
      balance.reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  return (
    <div className="max-w-3xl space-y-5 md:space-y-6">
      <section aria-label={t("leave.balance")} className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
        {(balance.data?.balances ?? []).map((b) => (
          <div key={b.leave_type} className="rounded-card border border-line bg-surface p-4">
            <p className="text-label font-normal text-ink-2">{name(b)}</p>
            <p className="tnum mt-1 text-section text-ink">{b.remaining === null ? t("leave.noLimit") : t("leave.remaining", { count: formatNumber(b.remaining) })}</p>
            <p className="text-caption text-ink-2">{t("leave.usedPending", { used: formatNumber(b.used), pending: formatNumber(b.pending) })}</p>
          </div>
        ))}
      </section>
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 p-4">
          <h2 className="text-section text-ink">{t("leave.myRequests")}</h2>
          <Button icon={<Plus size={20} aria-hidden />} onClick={() => setOpen(true)}>{t("leave.request")}</Button>
        </div>
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-32" />
        ) : data.results.length === 0 ? (
          <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("leave.noneYet")}</p>
        ) : (
          <div className={`border-t border-line ${loading ? "opacity-70" : ""}`}>
            <ul className="divide-y divide-line">
              {data.results.map((r) => <RequestRow key={r.id} r={r} showName={false}>{r.can_cancel ? <Button variant="ghost" onClick={() => cancel(r)}>{t("leave.cancel")}</Button> : null}</RequestRow>)}
            </ul>
            <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
          </div>
        )}
      </Card>
      {open ? <RequestSheet onClose={() => setOpen(false)} onDone={() => { setOpen(false); reload(); balance.reload(); }} /> : null}
    </div>
  );
}

function Requests({ params, setParams }: P) {
  const { t, msg } = useI18n();
  const toast = useToast();
  const page = Math.max(1, Number(params.page) || 1);
  const [scope, setScope] = useState<"decide" | "all">("decide");
  const { data, error, loading, reload } = useQuery<Page<LeaveRequest>>(`/hr/leave/?scope=${scope}&page=${page}&page_size=${SIZE}`);
  const show = useDelayed(loading && !data);
  const [reject, setReject] = useState<LeaveRequest | null>(null);
  async function approve(r: LeaveRequest) {
    try {
      await api(`/hr/leave/${r.id}/approve/`, { method: "POST", body: {} });
      toast.success(t("leave.approved"));
      reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  return (
    <div className="max-w-3xl">
      <Segmented label={t("leave.scope")} value={scope} onChange={(v) => { setScope(v); setParams({ page: "" }); }} segments={[{ value: "decide", label: t("leave.scope.decide") }, { value: "all", label: t("leave.scope.all") }]} className="mb-5 w-full md:w-fit" />
      <Card className="overflow-hidden">
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-32" />
        ) : data.results.length === 0 ? (
          <EmptyState icon={<Plus size={24} aria-hidden />} title={t(scope === "decide" ? "leave.noDecide" : "leave.noAll")} description={t(scope === "decide" ? "leave.noDecideText" : "leave.noAllText")} />
        ) : (
          <div className={loading ? "opacity-70" : ""}>
            <ul className="divide-y divide-line">
              {data.results.map((r) => (
                <RequestRow key={r.id} r={r} showName>
                  {r.can_decide ? (
                    <>
                      <Button onClick={() => approve(r)}>{t("leave.approve")}</Button>
                      <Button variant="secondary" onClick={() => setReject(r)}>{t("leave.reject")}</Button>
                    </>
                  ) : null}
                </RequestRow>
              ))}
            </ul>
            <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
          </div>
        )}
      </Card>
      {reject ? <RejectSheet req={reject} onClose={() => setReject(null)} onDone={() => { setReject(null); reload(); }} /> : null}
    </div>
  );
}

const thisMonth = () => isoDate(new Date()).slice(0, 7);
const shift = (month: string, by: number) => {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

function CalendarTab({ params, setParams }: P) {
  const { t, lang, formatMonthYear, formatDate, formatNumber } = useI18n();
  const month = params.month || thisMonth();
  const { data, error, loading, reload } = useFetch<{ month: string; weekend_days: number[]; results: LeaveRequest[] }>(`/hr/leave/calendar/?month=${month}`);
  const show = useDelayed(loading);
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const last = new Date(y, m, 0).getDate();
  const days = (() => {
    const out: Record<string, LeaveRequest[]> = {};
    for (const r of data?.results ?? []) {
      for (let d = 1; d <= last; d++) {
        const key = `${month}-${String(d).padStart(2, "0")}`;
        if (key >= r.start_date && key <= r.end_date) (out[key] ||= []).push(r);
      }
    }
    return out;
  })();
  const weekend = new Set(data?.weekend_days ?? [4, 5]);
  const lead = (first.getDay() + 6) % 7; // Monday-first grid
  const dayNames = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(lang === "ar" ? "ar" : "en", { weekday: "short" }).format(new Date(2026, 0, 5 + i)));
  const nm = (r: LeaveRequest) => r.user_name.split(" ")[0];
  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <IconButton label={t("leave.cal.prev")} variant="secondary" onClick={() => setParams({ month: shift(month, -1) === thisMonth() ? "" : shift(month, -1) })}><CaretLeft size={20} aria-hidden className="rtl:rotate-180" /></IconButton>
        <h2 className="min-w-40 text-center text-section text-ink" aria-live="polite">{formatMonthYear(first)}</h2>
        <IconButton label={t("leave.cal.next")} variant="secondary" onClick={() => setParams({ month: shift(month, 1) === thisMonth() ? "" : shift(month, 1) })}><CaretRight size={20} aria-hidden className="rtl:rotate-180" /></IconButton>
      </div>
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        show ? <RowsSkeleton /> : <div className="h-48" />
      ) : (
        <>
          <Card className="hidden overflow-hidden md:block">
            <div className="grid grid-cols-7">
              {dayNames.map((n) => <div key={n} className="border-b border-line bg-canvas/50 p-2 text-center text-caption text-ink-2">{n}</div>)}
              {Array.from({ length: lead }, (_, i) => <div key={`l${i}`} className="min-h-24 border-b border-s border-line bg-canvas/30" />)}
              {Array.from({ length: last }, (_, i) => {
                const d = i + 1;
                const key = `${month}-${String(d).padStart(2, "0")}`;
                const off = weekend.has((lead + i) % 7); // Monday-first column = the server's weekday number
                const items = days[key] ?? [];
                return (
                  <div key={key} className={`min-h-24 border-b border-s border-line p-1.5 ${off ? "bg-canvas/50" : ""}`}>
                    <p className="tnum text-caption text-ink-2">{formatNumber(d)}</p>
                    <ul className="mt-1 space-y-1">
                      {items.slice(0, 3).map((r) => (
                        <li key={r.id} className={`truncate rounded px-1.5 py-0.5 text-caption ${r.status === "approved" ? "bg-primary/10 text-primary-strong" : "bg-warning-bg text-warning-ink"}`} title={`${r.user_name} · ${lang === "ar" ? r.type_ar : r.type_en}`}>{nm(r)}</li>
                      ))}
                      {items.length > 3 ? <li className="text-caption text-ink-2">{t("leave.cal.more", { count: formatNumber(items.length - 3) })}</li> : null}
                    </ul>
                  </div>
                );
              })}
            </div>
          </Card>
          <Card className="overflow-hidden md:hidden">
            {data.results.length === 0 ? (
              <p className="px-4 py-6 text-center text-label font-normal text-ink-2">{t("leave.cal.empty")}</p>
            ) : (
              <ul className="divide-y divide-line">
                {data.results.map((r) => (
                  <li key={r.id} className="flex items-start justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-body font-semibold text-ink">{r.user_name}</p>
                      <p className="text-label font-normal text-ink-2">{formatDate(r.start_date)} → {formatDate(r.end_date)}</p>
                    </div>
                    <StatusPill tone={r.status === "approved" ? "success" : "warning"}>{lang === "ar" ? r.type_ar : r.type_en}</StatusPill>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {data.results.length === 0 ? <p className="mt-3 hidden text-label font-normal text-ink-2 md:block">{t("leave.cal.empty")}</p> : null}
        </>
      )}
    </div>
  );
}

function Types() {
  const { t, msg, formatNumber } = useI18n();
  const toast = useToast();
  const name = useTypeName();
  const { data, error, reload } = useFetch<LeaveType[]>("/hr/leave-types/?all=1");
  const [edit, setEdit] = useState<LeaveType | "new" | null>(null);
  async function toggle(x: LeaveType) {
    try {
      await api(`/hr/leave-types/${x.id}/`, { method: "PATCH", body: { is_active: !x.is_active } });
      toast.success(t(x.is_active ? "leave.types.off" : "leave.types.on"));
      reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }
  return (
    <div className="max-w-3xl">
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 p-4">
          <h2 className="text-section text-ink">{t("leave.tab.types")}</h2>
          <Button icon={<Plus size={20} aria-hidden />} onClick={() => setEdit("new")}>{t("leave.types.add")}</Button>
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : (
          <ul className="divide-y divide-line border-t border-line">
            {(data ?? []).map((x) => (
              <li key={x.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-body font-semibold text-ink">{name(x)}</p>
                  <p className="text-label font-normal text-ink-2">
                    {x.annual_days ? t("leave.types.perYear", { count: formatNumber(x.annual_days) }) : t("leave.noLimit")} · {x.paid ? t("leave.paid") : t("leave.unpaid")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!x.is_active ? <StatusPill tone="neutral">{t("leave.types.inactive")}</StatusPill> : null}
                  <Button variant="secondary" onClick={() => setEdit(x)}>{t("common.edit")}</Button>
                  <Button variant="ghost" onClick={() => toggle(x)}>{t(x.is_active ? "leave.types.switchOff" : "leave.types.switchOn")}</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {edit ? <TypeSheet type={edit === "new" ? undefined : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload(); }} /> : null}
    </div>
  );
}
