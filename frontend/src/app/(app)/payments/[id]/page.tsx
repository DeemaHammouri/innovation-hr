"use client";

import { DotsThreeVertical, DownloadSimple, Paperclip, Plus } from "@phosphor-icons/react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { CancelInstalmentSheet, EditInstalmentSheet, PaySheet, ReceiptSheet, ReverseSheet, ScheduleSheet } from "@/components/payments/PaymentSheets";
import { InstalmentPill, Stat } from "@/components/payments/payUi";
import { useMoney } from "@/components/quotations/quoteUi";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { downloadFile, errorMessage, type Instalment, type PaymentRow, type Statement } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Sheet =
  | { kind: "schedule" }
  | { kind: "pay" | "edit" | "cancel"; inst: Instalment }
  | { kind: "reverse"; pay: PaymentRow }
  | { kind: "receipt"; id: number }
  | null;

export default function StatementPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, msg, formatDate, formatDateTime } = useI18n();
  const money = useMoney();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<Statement>(user ? `/payments/clients/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  const [liveRaw, setLiveRaw] = useState<{ src: Statement | null; val: Statement } | null>(null);
  const setLive = (val: Statement) => setLiveRaw({ src: data, val });
  const [sheet, setSheet] = useState<Sheet>(null);
  const st = liveRaw && liveRaw.src === data ? liveRaw.val : data;

  if (!user) return null;
  const back = { href: "/payments", label: t("pay.title") };
  if (user.role_key !== "ceo" && user.role_key !== "commercial_head") return <NoAccess />;
  if (error) return <><PageHeader title={t("pay.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!st) {
    return (
      <>
        <PageHeader title={t("pay.title")} back={back} />
        {showSkeleton ? <div className="max-w-3xl space-y-4" aria-busy="true"><Skeleton className="h-24 rounded-card" /><Skeleton className="h-48 rounded-card" /></div> : null}
      </>
    );
  }
  const write = st.permissions.can_write;
  const cur = st.currency;
  const update = (s: Statement) => {
    setLive(s);
    setSheet(null);
  };
  async function exportCsv() {
    try {
      await downloadFile(`/payments/clients/${st!.client.id}/export/`, `statement-${st!.client.id}.csv`);
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  return (
    <>
      <PageHeader
        back={back}
        title={st.client.company_name}
        description={t("pay.statement")}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={exportCsv}>{t("pay.export")}</Button>
            {write ? <Button icon={<Plus size={20} aria-hidden />} onClick={() => setSheet({ kind: "schedule" })}>{t("pay.sched.add")}</Button> : null}
          </div>
        }
      />
      <div className="max-w-3xl space-y-5 md:space-y-6">
        <section aria-label={t("pay.totals")} className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label={t("pay.total")} value={money(st.totals.total, cur)} />
          <Stat label={t("pay.paid")} value={money(st.totals.paid, cur)} />
          <Stat label={t("pay.balance")} value={money(st.totals.balance, cur)} />
          <Stat label={t("pay.overdue")} value={money(st.totals.overdue_amount, cur)} tone={st.totals.overdue_count ? "danger" : undefined} />
        </section>

        <Card as="section" aria-labelledby="pay-instalments" className="overflow-hidden">
          <h2 id="pay-instalments" className="p-4 text-section text-ink">{t("pay.instalments")}</h2>
          {st.instalments.length === 0 ? (
            <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("pay.noSchedule")}</p>
          ) : (
            <ul className="divide-y divide-line border-t border-line">
              {st.instalments.map((i) => (
                <li key={i.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-body font-semibold text-ink">{t("pay.instalmentN", { n: i.number })} · <span dir="ltr" className="tnum">{money(i.amount, i.currency)}</span></p>
                    <p className="text-label font-normal text-ink-2">
                      {t("pay.dueOn", { date: formatDate(i.due_date) })}
                      {i.status !== "cancelled" ? ` · ${t("pay.paidOf", { paid: money(i.paid, i.currency), balance: money(i.balance, i.currency) })}` : ""}
                    </p>
                    {i.note ? <p className="text-label font-normal text-ink-2">{i.note}</p> : null}
                    {i.status === "cancelled" ? <p className="text-label font-normal text-ink-2">{t("pay.cancelledBecause", { reason: i.cancel_reason })}</p> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <InstalmentPill status={i.status} />
                    {write && i.status !== "cancelled" ? (
                      <>
                        {i.status !== "paid" ? <Button variant="secondary" onClick={() => setSheet({ kind: "pay", inst: i })}>{t("pay.record")}</Button> : null}
                        <Menu
                          label={t("common.actions")}
                          trigger={({ open: isOpen, ...props }) => (
                            <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${isOpen ? "bg-canvas" : ""}`}>
                              <DotsThreeVertical size={20} weight="bold" aria-hidden />
                            </IconButton>
                          )}
                        >
                          {(done) => (
                            <>
                              {i.can_edit ? <MenuItem onSelect={() => { done(); setSheet({ kind: "edit", inst: i }); }}>{t("pay.edit")}</MenuItem> : null}
                              <MenuItem danger onSelect={() => { done(); setSheet({ kind: "cancel", inst: i }); }}>{t("pay.cancel")}</MenuItem>
                            </>
                          )}
                        </Menu>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card as="section" aria-labelledby="pay-ledger" className="overflow-hidden">
          <h2 id="pay-ledger" className="p-4 text-section text-ink">{t("pay.ledger")}</h2>
          {st.payments.length === 0 ? (
            <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("pay.noPayments")}</p>
          ) : (
            <ul className="divide-y divide-line border-t border-line">
              {st.payments.map((p) => (
                <li key={p.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-body font-semibold text-ink">
                      {p.kind === "reversal" ? t("pay.reversal") : t("pay.payment")} <span dir="ltr" className="tnum">{p.kind === "reversal" ? "−" : ""}{money(p.amount, p.currency)}</span>
                    </p>
                    <p className="text-label font-normal text-ink-2">
                      {t("pay.instalmentN", { n: p.instalment_number })} · {formatDate(p.received_on)} · {t(`pay.method.${p.method}`)}
                      {p.reference ? <> · <span dir="ltr">{p.reference}</span></> : null}
                    </p>
                    {p.reason ? <p className="text-label font-normal text-ink-2">{t("pay.reversedBecause", { reason: p.reason })}</p> : null}
                    <p className="text-caption text-ink-2">{p.recorded_by_name} · {formatDateTime(p.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {p.reversed ? <StatusPill tone="neutral">{t("pay.reversed")}</StatusPill> : null}
                    {p.kind === "payment" && !p.has_receipt && !p.reversed ? <StatusPill tone="warning">{t("pay.noReceipt")}</StatusPill> : null}
                    {p.kind === "payment" ? (
                      <Button variant="secondary" icon={<Paperclip size={18} aria-hidden />} onClick={() => setSheet({ kind: "receipt", id: p.id })}>{t("pay.receipt")}</Button>
                    ) : null}
                    {write && p.can_reverse ? <Button variant="ghost" onClick={() => setSheet({ kind: "reverse", pay: p })}>{t("pay.reverse")}</Button> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {sheet?.kind === "schedule" ? <ScheduleSheet clientId={st.client.id} currency={cur} onClose={() => setSheet(null)} onDone={update} /> : null}
      {sheet?.kind === "pay" ? (
        <PaySheet
          inst={sheet.inst}
          onClose={() => setSheet(null)}
          onDone={(s) => {
            setLive(s);
            setSheet(s.recorded ? { kind: "receipt", id: s.recorded } : null);
          }}
        />
      ) : null}
      {sheet?.kind === "edit" ? <EditInstalmentSheet inst={sheet.inst} onClose={() => setSheet(null)} onDone={update} /> : null}
      {sheet?.kind === "cancel" ? <CancelInstalmentSheet inst={sheet.inst} onClose={() => setSheet(null)} onDone={update} /> : null}
      {sheet?.kind === "reverse" ? <ReverseSheet paymentId={sheet.pay.id} number={sheet.pay.instalment_number} onClose={() => setSheet(null)} onDone={update} /> : null}
      {sheet?.kind === "receipt" ? (
        <ReceiptSheet
          paymentId={sheet.id}
          canAttach={write}
          onClose={() => {
            setSheet(null);
            reload();
          }}
        />
      ) : null}
    </>
  );
}
