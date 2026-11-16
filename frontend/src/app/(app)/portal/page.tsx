"use client";

import { useState } from "react";
import { DownloadSheet } from "@/components/documents/DownloadSheet";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { NoAccess } from "@/components/NoAccess";
import { useMoney } from "@/components/quotations/quoteUi";
import { Button } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type PortalMe, type PortalQuotation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** The client's home. Everything here comes from /portal/, which only ever returns the signed-in client's own company and documents. */
export default function PortalPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const allowed = !!user && can(user, "portal.access");
  const { data, error, reload } = useFetch<PortalMe>(allowed ? "/portal/me/" : null);
  const quotes = useFetch<PortalQuotation[]>(allowed ? "/portal/quotations/" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  const empty = <span className="text-ink-2">—</span>;
  return (
    <>
      <PageHeader title={t("portal.title")} description={t("portal.description")} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? (
        <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-48 rounded-card" /></div>
      ) : (
        <div className="max-w-2xl space-y-5 md:space-y-6">
          <InsetList title={t("portal.company")}>
            <InsetRow label={t("clients.company")}>{data.client.company_name}</InsetRow>
            <InsetRow label={t("clients.contactPerson")}>{data.client.contact_person || empty}</InsetRow>
            <InsetRow label={t("common.phone")} ltr={!!data.client.phone}>{data.client.phone || empty}</InsetRow>
            <InsetRow label={t("common.email")} ltr={!!data.client.email}>{data.client.email || empty}</InsetRow>
          </InsetList>
          <section aria-labelledby="portal-quotes" className="space-y-3">
            <h2 id="portal-quotes" className="text-section text-ink">{t("portal.quotations")}</h2>
            {quotes.error ? <ErrorState message={quotes.error} onRetry={quotes.reload} /> : !quotes.data ? <Skeleton className="h-40 rounded-card" /> : quotes.data.length === 0 ? (
              <Card className="p-5"><p className="text-body text-ink-2">{t("portal.quotations.none")}</p></Card>
            ) : quotes.data.map((q) => <QuotationCard key={q.id} q={q} onSigned={quotes.reload} />)}
          </section>
        </div>
      )}
    </>
  );
}

function QuotationCard({ q, onSigned }: { q: PortalQuotation; onSigned: () => void }) {
  const { t, formatDate, formatDateTime } = useI18n();
  const money = useMoney();
  const [open, setOpen] = useState(false);
  const [download, setDownload] = useState(false);
  const v = q.version;
  return (
    <Card as="section" className="p-5 md:p-6" aria-label={q.number ?? String(q.id)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-section text-ink"><Ltr>{q.number ?? ""}</Ltr></h3>
          {v?.valid_until ? <p className="text-label font-normal text-ink-2">{t("portal.q.validUntil", { date: formatDate(v.valid_until) })}</p> : null}
        </div>
        {q.can_sign ? <StatusPill tone="warning">{t("portal.q.waiting")}</StatusPill> : <StatusPill tone="success">{t("qt.status.confirmed")}</StatusPill>}
      </div>
      {v ? (
        <>
          <ul className="mt-4 divide-y divide-line rounded-control border border-line">
            {v.lines.map((l, i) => (
              <li key={i} className="flex items-start justify-between gap-3 p-3 text-body">
                <div className="min-w-0">
                  <p className="text-ink">{l.description}</p>
                  <p className="text-label font-normal text-ink-2">{t(`qt.freq.${l.frequency}`)}{l.visits ? ` · ${t("qt.visits")}: ${l.visits}` : ""}</p>
                </div>
                <span className="tnum shrink-0 text-ink" dir="ltr">{money(l.line_total, v.currency)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center justify-between text-section font-semibold text-ink">
            <span>{t("portal.q.total")}</span>
            <span className="tnum" dir="ltr">{money(v.total, v.currency)}</span>
          </div>
          {v.payment_terms ? <p className="mt-4 whitespace-pre-line text-label font-normal text-ink-2"><span className="font-semibold text-ink">{t("portal.q.payment")}: </span>{v.payment_terms}</p> : null}
        </>
      ) : null}
      {q.client_signed_at ? (
        <p className="mt-4 text-label font-medium text-success-ink">{t(q.client_signed_via === "upload" ? "portal.q.signedByStaff" : "portal.q.signed", { date: formatDateTime(q.client_signed_at) })}</p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-3">
        {q.can_sign ? <Button onClick={() => setOpen(true)}>{t("portal.q.sign")}</Button> : null}
        <Button variant="secondary" onClick={() => setDownload(true)}>{t("doc.menu")}</Button>
      </div>
      {download ? <DownloadSheet path={`/portal/quotations/${q.id}/document/`} fileBase={`quotation-${(q.number ?? String(q.id)).replace(/\//g, "-")}`} onClose={() => setDownload(false)} /> : null}
      {open && v ? <SignSheet q={q} total={money(v.total, v.currency)} onClose={() => setOpen(false)} onDone={() => { setOpen(false); onSigned(); }} /> : null}
    </Card>
  );
}

function SignSheet({ q, total, onClose, onDone }: { q: PortalQuotation; total: string; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["signature"]);
  const [signature, setSignature] = useState("");
  const [local, setLocal] = useState("");
  async function sign() {
    if (!signature) return setLocal("sign.drawHere");
    setLocal("");
    const saved = await action.run(() => api<PortalQuotation>(`/portal/quotations/${q.id}/sign/`, { method: "POST", body: { signature } }));
    if (saved) {
      toast.success(t("portal.q.signDone"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("portal.q.sign")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={sign}>{t("qt.sign.save")}</Button></>}>
      <FormError message={action.formError} />
      <p className="mb-4 text-body text-ink-2">{t("portal.q.signText", { total })}</p>
      <SignaturePad label={t("sign.pad")} onChange={(d) => { setSignature(d); setLocal(""); }} error={local ? t(local) : action.errors.signature} />
    </Sheet>
  );
}
