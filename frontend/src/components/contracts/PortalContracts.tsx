"use client";

import { useState } from "react";
import { DownloadSheet } from "@/components/documents/DownloadSheet";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { useMoney } from "@/components/quotations/quoteUi";
import { Button } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { Sheet } from "@/components/ui/Sheet";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type PortalContract } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** The client's contracts: read the text that was sent, sign it on screen, download it. Only the signed-in client's own contracts arrive here. */
export function PortalContracts() {
  const { t } = useI18n();
  const contracts = useFetch<PortalContract[]>("/portal/contracts/");
  return (
    <section aria-labelledby="portal-contracts" className="space-y-3">
      <h2 id="portal-contracts" className="text-section text-ink">{t("portal.contracts")}</h2>
      {contracts.error ? <ErrorState message={contracts.error} onRetry={contracts.reload} /> : !contracts.data ? <Skeleton className="h-32 rounded-card" /> : contracts.data.length === 0 ? (
        <Card className="p-5"><p className="text-body text-ink-2">{t("portal.contracts.none")}</p></Card>
      ) : contracts.data.map((c) => <ContractCard key={c.id} c={c} onSigned={contracts.reload} />)}
    </section>
  );
}

function ContractCard({ c, onSigned }: { c: PortalContract; onSigned: () => void }) {
  const { t, lang, formatDate, formatDateTime } = useI18n();
  const money = useMoney();
  const [sign, setSign] = useState(false);
  const [download, setDownload] = useState(false);
  const [read, setRead] = useState(false);
  const v = c.version;
  const body = v ? (lang === "ar" && v.body_ar ? v.body_ar : v.body_en || v.body_ar) : "";
  const tone = c.status === "sent" ? "warning" : "success";
  return (
    <Card className="space-y-4 p-4 md:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-body font-semibold text-ink"><Ltr>{c.number}</Ltr></p>
        <StatusPill tone={tone}>{t(`portal.c.${c.status === "sent" ? "toSign" : c.status === "ceo_review" ? "signedByYou" : "signed"}`)}</StatusPill>
      </div>
      {v ? (
        <InsetList>
          <InsetRow label={t("ct.draft.total")}>{money(v.total, v.currency)}</InsetRow>
          <InsetRow label={t("ct.draft.terms")}>{v.payment_terms || "—"}</InsetRow>
          <InsetRow label={t("ct.draft.start")}>{v.start_date ? formatDate(v.start_date) : "—"}</InsetRow>
          <InsetRow label={t("ct.draft.end")}>{v.end_date ? formatDate(v.end_date) : "—"}</InsetRow>
          {c.client_signed_at ? <InsetRow label={t("ct.clientSigned")}>{formatDateTime(c.client_signed_at)}</InsetRow> : null}
        </InsetList>
      ) : null}
      {body ? (
        <div>
          <Button variant="secondary" onClick={() => setRead((x) => !x)} aria-expanded={read}>{t(read ? "portal.c.hide" : "portal.c.read")}</Button>
          {read ? <p dir="auto" className="mt-3 max-h-80 overflow-auto whitespace-pre-line rounded-control bg-canvas p-3 text-body text-ink">{body}</p> : null}
        </div>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {c.can_sign ? <Button onClick={() => setSign(true)}>{t("portal.c.sign")}</Button> : null}
        <Button variant="secondary" onClick={() => setDownload(true)}>{t("doc.menu")}</Button>
      </div>
      {sign ? <SignSheet c={c} onClose={() => setSign(false)} onDone={() => { setSign(false); onSigned(); }} /> : null}
      {download ? <DownloadSheet path={`/portal/contracts/${c.id}/document/`} fileBase={`contract-${c.number.replace(/\//g, "-")}`} onClose={() => setDownload(false)} /> : null}
    </Card>
  );
}

function SignSheet({ c, onClose, onDone }: { c: PortalContract; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["signature"]);
  const [signature, setSignature] = useState("");
  const [local, setLocal] = useState("");
  async function go() {
    if (!signature) return setLocal("sign.drawHere");
    setLocal("");
    const saved = await action.run(() => api<PortalContract>(`/portal/contracts/${c.id}/sign/`, { method: "POST", body: { signature } }));
    if (saved) {
      toast.success(t("portal.c.signed"));
      onDone();
    }
  }
  return (
    <Sheet open alert onClose={onClose} title={t("portal.c.signTitle")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={go}>{t("portal.c.sign")}</Button></>}>
      <FormError message={action.formError} />
      <p className="mb-4 text-body text-ink-2">{t("portal.c.signText", { number: c.number })}</p>
      <SignaturePad label={t("sign.pad")} onChange={(d) => { setSignature(d); setLocal(""); }} error={local ? t(local) : action.errors.signature} />
    </Sheet>
  );
}
