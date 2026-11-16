"use client";

import { ArrowsClockwise, CheckCircle, DownloadSimple, PencilSimple } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import { useParams } from "next/navigation";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { EntrySheet, ReopenSheet, RunPill } from "@/components/hr/PayrollSheets";
import { Stat } from "@/components/payments/payUi";
import { useMoney } from "@/components/quotations/quoteUi";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, downloadFile, errorMessage, type PayrollEntry, type PayrollRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function PayrollRunPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, msg, formatDateTime } = useI18n();
  const money = useMoney();
  const toast = useToast();
  const allowed = can(user, "hr.payroll_view");
  const { data, error, loading, reload } = useFetch<PayrollRun>(user && allowed ? `/hr/payroll/runs/${id}/` : null);
  const show = useDelayed(loading);
  const [entry, setEntry] = useState<PayrollEntry | null>(null);
  const [reopen, setReopen] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  const back = { href: "/payroll?tab=runs", label: t("payroll.title") };
  if (!allowed) return <NoAccess />;
  if (error) return <><PageHeader title={t("payroll.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={t("payroll.title")} back={back} />{show ? <Skeleton className="h-48 max-w-3xl rounded-card" /> : null}</>;
  const { permissions: p } = data;
  const entries = data.entries ?? [];
  const sum = (k: "base_salary" | "allowances" | "deductions" | "net") => entries.reduce((a, e) => a + Number(e[k]), 0).toFixed(2);

  async function act(path: string, done: string) {
    setBusy(true);
    try {
      await api(`/hr/payroll/runs/${data!.id}/${path}/`, { method: "POST", body: {} });
      toast.success(done);
      reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    } finally {
      setBusy(false);
    }
  }
  async function exportCsv() {
    try {
      await downloadFile(`/hr/payroll/runs/${data!.id}/export/`, `payroll-${data!.month}.csv`);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  return (
    <>
      <PageHeader
        back={back}
        title={t("payroll.runTitle", { month: data.month })}
        meta={<RunPill status={data.status} />}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={exportCsv}>{t("payroll.export")}</Button>
            {p.can_edit ? <Button variant="secondary" icon={<ArrowsClockwise size={18} aria-hidden />} loading={busy} onClick={() => act("refresh", t("payroll.refreshed"))}>{t("payroll.refresh")}</Button> : null}
            {p.can_approve ? <Button icon={<CheckCircle size={20} aria-hidden />} loading={busy} onClick={() => act("approve", t("payroll.approved"))}>{t("payroll.approve")}</Button> : null}
            {p.can_reopen ? <Button variant="secondary" onClick={() => setReopen(true)}>{t("payroll.reopen")}</Button> : null}
            {p.can_pay ? <Button icon={<CheckCircle size={20} aria-hidden />} loading={busy} onClick={() => act("pay", t("payroll.paid"))}>{t("payroll.markPaid")}</Button> : null}
          </div>
        }
      />
      <div className="max-w-3xl space-y-5 md:space-y-6">
        <section aria-label={t("pay.totals")} className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label={t("payroll.base")} value={money(sum("base_salary"), data.currency)} />
          <Stat label={t("payroll.allowances")} value={money(sum("allowances"), data.currency)} />
          <Stat label={t("payroll.deductions")} value={money(sum("deductions"), data.currency)} />
          <Stat label={t("payroll.net")} value={money(sum("net"), data.currency)} />
        </section>
        {data.status !== "draft" ? (
          <p className="text-label font-normal text-ink-2">
            {data.approved_by_name ? t("payroll.approvedBy", { name: data.approved_by_name, when: data.approved_at ? formatDateTime(data.approved_at) : "" }) : ""}
            {data.paid_by_name ? ` · ${t("payroll.paidBy", { name: data.paid_by_name, when: data.paid_at ? formatDateTime(data.paid_at) : "" })}` : ""}
          </p>
        ) : p.can_edit ? (
          <p className="text-label font-normal text-ink-2">{t("payroll.draftHelp")}</p>
        ) : (
          <p className="text-label font-normal text-ink-2">{t("payroll.draftHelpCeo")}</p>
        )}
        <Card as="section" aria-labelledby="payroll-entries" className="overflow-hidden">
          <h2 id="payroll-entries" className="p-4 text-section text-ink">{t("payroll.entries")}</h2>
          <ul className="divide-y divide-line border-t border-line">
            {entries.map((e) => (
              <li key={e.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-body font-semibold text-ink">{e.user_name}</p>
                  <p className="text-label font-normal text-ink-2">{e.department}</p>
                  <p dir="ltr" className="tnum mt-1 text-label font-normal text-ink-2 text-start">
                    {e.base_salary} + {e.allowances} − {e.deductions}
                  </p>
                  {e.note ? <p className="text-label font-normal text-ink-2">{e.note}</p> : null}
                </div>
                <div className="flex items-center gap-2">
                  <p dir="ltr" className="tnum text-body font-semibold text-ink">{money(e.net, data.currency)}</p>
                  {p.can_edit ? <IconButton label={t("payroll.editEntry", { name: e.user_name })} variant="ghost" onClick={() => setEntry(e)}><PencilSimple size={20} aria-hidden /></IconButton> : null}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      {entry ? <EntrySheet entry={entry} currency={data.currency} onClose={() => setEntry(null)} onDone={() => { setEntry(null); reload(); }} /> : null}
      {reopen ? <ReopenSheet run={data} onClose={() => setReopen(false)} onDone={() => { setReopen(false); reload(); }} /> : null}
    </>
  );
}
