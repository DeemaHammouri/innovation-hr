"use client";

import { Plus, Wallet } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { NewRunSheet, RunPill, SalarySheet } from "@/components/hr/PayrollSheets";
import { useMoney } from "@/components/quotations/quoteUi";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Page, PayrollRun, Payslip, SalaryRow } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";
import { useRouter } from "next/navigation";

const KEYS = ["tab", "page"] as const;
const SIZE = 20;
type Tab = "payslips" | "runs" | "salaries";

export default function PayrollPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  if (!user) return null;
  const manager = user.role_key === "hr_head" || user.role_key === "ceo";
  const tabs: { value: Tab; label: string }[] = [
    { value: "payslips", label: t("payroll.tab.payslips") },
    ...(manager ? [{ value: "runs" as Tab, label: t("payroll.tab.runs") }, { value: "salaries" as Tab, label: t("payroll.tab.salaries") }] : []),
  ];
  const tab = (tabs.find((x) => x.value === params.tab)?.value ?? (manager ? "runs" : "payslips")) as Tab;
  return (
    <>
      <PageHeader title={t("payroll.title")} description={t(manager ? "payroll.descriptionManager" : "payroll.description")} />
      {tabs.length > 1 ? <Segmented label={t("payroll.tabs")} mode="tablist" value={tab} onChange={(v) => setParams({ tab: v, page: "" })} segments={tabs} className="mb-5 w-full md:w-fit" /> : null}
      {tab === "payslips" ? <Payslips /> : null}
      {tab === "runs" ? <Runs canCreate={user.role_key === "hr_head"} page={Math.max(1, Number(params.page) || 1)} setPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} /> : null}
      {tab === "salaries" ? <Salaries canEdit={user.role_key === "hr_head"} /> : null}
    </>
  );
}

function Payslips() {
  const { t, formatDate } = useI18n();
  const money = useMoney();
  const { data, error, loading, reload } = useFetch<Payslip[]>("/hr/payslips/");
  const show = useDelayed(loading);
  return (
    <div className="max-w-3xl">
      <Card className="overflow-hidden">
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-32" />
        ) : data.length === 0 ? (
          <EmptyState icon={<Wallet size={24} aria-hidden />} title={t("payroll.noPayslips")} description={t("payroll.noPayslipsText")} />
        ) : (
          <ul className="divide-y divide-line">
            {data.map((p) => (
              <li key={p.id}>
                <Link href={`/payroll/payslip/${p.id}`} className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-canvas/60">
                  <div>
                    <p className="text-body font-semibold text-ink">{t("payroll.payslipFor", { month: p.month })}</p>
                    {p.paid_at ? <p className="text-label font-normal text-ink-2">{t("payroll.paidOn", { date: formatDate(p.paid_at) })}</p> : null}
                  </div>
                  <p dir="ltr" className="tnum text-body font-semibold text-ink">{money(p.net, p.currency)}</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Runs({ canCreate, page, setPage }: { canCreate: boolean; page: number; setPage: (p: number) => void }) {
  const { t, formatNumber } = useI18n();
  const money = useMoney();
  const router = useRouter();
  const { data, error, loading, reload } = useQuery<Page<PayrollRun>>(`/hr/payroll/runs/?page=${page}&page_size=${SIZE}`);
  const show = useDelayed(loading && !data);
  const [open, setOpen] = useState(false);
  return (
    <div className="max-w-3xl">
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 p-4">
          <h2 className="text-section text-ink">{t("payroll.tab.runs")}</h2>
          {canCreate ? <Button icon={<Plus size={20} aria-hidden />} onClick={() => setOpen(true)}>{t("payroll.run.new")}</Button> : null}
        </div>
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-32" />
        ) : data.results.length === 0 ? (
          <EmptyState icon={<Wallet size={24} aria-hidden />} title={t("payroll.noRuns")} description={t(canCreate ? "payroll.noRunsText" : "payroll.noRunsTextCeo")} />
        ) : (
          <div className={`border-t border-line ${loading ? "opacity-70" : ""}`}>
            <ul className="divide-y divide-line">
              {data.results.map((r) => (
                <li key={r.id}>
                  <Link href={`/payroll/${r.id}`} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 hover:bg-canvas/60">
                    <div>
                      <p className="text-body font-semibold text-ink"><span dir="ltr">{r.month}</span></p>
                      <p className="text-label font-normal text-ink-2">{t("payroll.people", { count: formatNumber(r.people) })} · <span dir="ltr" className="tnum">{money(r.total_net, r.currency)}</span></p>
                    </div>
                    <RunPill status={r.status} />
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination page={page} total={data.count} onPage={setPage} pageSize={SIZE} />
          </div>
        )}
      </Card>
      {open ? <NewRunSheet onClose={() => setOpen(false)} onDone={(run) => router.push(`/payroll/${run.id}`)} /> : null}
    </div>
  );
}

function Salaries({ canEdit }: { canEdit: boolean }) {
  const { t } = useI18n();
  const money = useMoney();
  const { data, error, loading, reload } = useFetch<SalaryRow[]>("/hr/salaries/");
  const show = useDelayed(loading);
  const [edit, setEdit] = useState<SalaryRow | null>(null);
  return (
    <div className="max-w-3xl">
      <Card className="overflow-hidden">
        <h2 className="p-4 text-section text-ink">{t("payroll.tab.salaries")}</h2>
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-32" />
        ) : (
          <ul className="divide-y divide-line border-t border-line">
            {data.map((s) => (
              <li key={s.user} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-body font-semibold text-ink">{s.user_name}</p>
                  <p className="text-label font-normal text-ink-2">{s.department}</p>
                </div>
                <div className="flex items-center gap-3">
                  <p dir="ltr" className="tnum text-body text-ink">{s.base_salary ? money(s.base_salary, s.currency ?? "JOD") : <span className="text-ink-3">{t("payroll.noSalary")}</span>}</p>
                  {canEdit ? <Button variant="secondary" onClick={() => setEdit(s)}>{t(s.base_salary ? "common.edit" : "payroll.salary.set")}</Button> : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {edit ? <SalarySheet row={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload(); }} /> : null}
    </div>
  );
}
