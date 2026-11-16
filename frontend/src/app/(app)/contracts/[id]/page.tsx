"use client";

import { DotsThreeVertical, FilePdf, PencilSimple, Prohibit } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ApproveSheet, CancelContractSheet, ClientCopySheet, CommercialReturnSheet, ConfirmContractSheet, DraftSheet, ReturnSheet, SendSheet, SendToClientSheet } from "@/components/contracts/ContractSheets";
import { DownloadSheet } from "@/components/documents/DownloadSheet";
import { ContractDocuments } from "@/components/contracts/ContractDocuments";
import { ContractStatusPill, ContractStepper } from "@/components/contracts/contractUi";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, InsetList, InsetRow } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Contract } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Sheet = "send" | "draft" | "confirm" | "creturn" | "toclient" | "copy" | "approve" | "return" | "cancel" | "download" | null;

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, lang, formatDateTime } = useI18n();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch<Contract>(user ? `/contracts/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  const back = { href: "/contracts", label: t("ct.title") };
  if (error) return <><PageHeader title={t("ct.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) {
    return (
      <>
        <PageHeader title={t("ct.title")} back={back} />
        {showSkeleton ? <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-24 rounded-card" /><Skeleton className="h-48 rounded-card" /></div> : null}
      </>
    );
  }
  const p = data.permissions;
  const done = () => {
    setSheet(null);
    reload();
  };

  async function post(path: string, message: string) {
    setBusy(true);
    try {
      await api(`/contracts/${data!.id}/${path}/`, { method: "POST" });
      toast.success(message);
      reload();
    } catch {
      toast.error(t("qt.saveFailed"));
    }
    setBusy(false);
  }

  let primary: React.ReactNode = null;
  let secondary: React.ReactNode = null;
  if (p.can_start) primary = <Button loading={busy} onClick={() => post("start", t("ct.started"))}>{t(data.status === "returned" ? "ct.next.redraft" : "ct.next.start")}</Button>;
  else if (p.can_send) {
    primary = <Button onClick={() => setSheet("send")}>{t("ct.next.send")}</Button>;
    secondary = <Button variant="secondary" icon={<PencilSimple size={18} aria-hidden />} onClick={() => setSheet("draft")}>{t("ct.next.edit")}</Button>;
  } else if (p.can_confirm) {
    primary = <Button onClick={() => setSheet("confirm")}>{t("ct.next.confirm")}</Button>;
    secondary = <Button variant="secondary" onClick={() => setSheet("creturn")}>{t("ct.next.cReturn")}</Button>;
  } else if (p.can_send_to_client) primary = <Button onClick={() => setSheet("toclient")}>{t("ct.next.toClient")}</Button>;
  else if (p.can_upload_client_copy) primary = <Button variant="secondary" onClick={() => setSheet("copy")}>{t("ct.next.copy")}</Button>;
  else if (p.can_review) {
    primary = <Button onClick={() => setSheet("approve")}>{t("ct.next.approve")}</Button>;
    secondary = <Button variant="secondary" onClick={() => setSheet("return")}>{t("ct.next.return")}</Button>;
  } else if (p.can_handover) primary = <Button loading={busy} onClick={() => post("handover", t("ct.handedOver"))}>{t("ct.next.handover")}</Button>;

  const hint =
    p.can_start ? t(data.status === "returned" ? "ct.hint.redraft" : "ct.hint.start")
    : p.can_send ? t("ct.hint.send")
    : p.can_confirm ? t("ct.hint.confirm")
    : p.can_send_to_client ? t("ct.hint.toClient")
    : p.can_upload_client_copy ? t("ct.hint.copy")
    : p.can_review ? t("ct.hint.review")
    : p.can_handover ? t("ct.hint.handover")
    : data.status === "ceo_review" ? t("ct.hint.withCeo")
    : data.status === "sent" ? t("ct.hint.withClient")
    : ["requested", "drafting", "returned"].includes(data.status) ? t("ct.hint.withHr")
    : ["with_commercial", "meeting_logged", "confirmed"].includes(data.status) ? t("ct.hint.withCommercial")
    : data.status === "signed" ? t("ct.hint.signedWait")
    : "";

  const menu = (
    <Menu
      label={t("common.actions")}
      trigger={({ open, ...props }) => (
        <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${open ? "bg-canvas" : ""}`}>
          <DotsThreeVertical size={20} weight="bold" aria-hidden />
        </IconButton>
      )}
    >
      {(close) => (
        <>
          <MenuItem icon={<FilePdf size={20} aria-hidden />} onSelect={() => { close(); setSheet("download"); }}>{t("doc.menu")}</MenuItem>
          {p.can_cancel ? <MenuItem danger icon={<Prohibit size={20} aria-hidden />} onSelect={() => { close(); setSheet("cancel"); }}>{t("ct.cancel.title")}</MenuItem> : null}
        </>
      )}
    </Menu>
  );
  const empty = <span className="text-ink-3">{"—"}</span>;
  const returned = data.status === "returned" && (data.returned_comment || data.ceo_comment);
  const latest = data.versions?.[data.versions.length - 1];

  return (
    <>
      <PageHeader
        back={back}
        title={`${data.number ?? data.ref} · ${data.lead_company}`}
        meta={<ContractStatusPill status={data.status} />}
        action={<div className="flex flex-wrap items-center gap-2">{secondary}{primary}{menu}</div>}
      />
      <div className="max-w-2xl">
        <Card className="mb-5 space-y-3 p-4 md:mb-6 md:p-5">
          <ContractStepper contract={data} />
          {hint ? <p className="text-label font-normal text-ink-2">{hint}</p> : null}
        </Card>
      </div>
      <RecordTabs
        target={`contract:${data.id}`}
        canAttach={data.attachable.includes("")}
        overview={
          <div className="space-y-5 md:space-y-6">
            {returned ? (
              <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
                <p className="text-body font-semibold">{t("ct.returnedNotes")}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.returned_comment || data.ceo_comment}</p>
              </div>
            ) : null}
            <ContractDocuments contract={data} onChanged={reload} />
            <InsetList title={t("qt.sectionClient")}>
              <InsetRow label={t("lead.company")}>{can(user, "lead.access") ? <Link href={`/leads/${data.lead}`} className="text-primary-strong underline underline-offset-2">{data.lead_company}</Link> : data.lead_company}</InsetRow>
              <InsetRow label={t("lead.reference")}><Ltr>{data.lead_ref}</Ltr></InsetRow>
              <InsetRow label={t("lead.contactName")}>{data.lead_contact || empty}</InsetRow>
              <InsetRow label={t("lead.assignee")}>{data.assigned_to_name ?? empty}</InsetRow>
              <InsetRow label={t("ct.quotation")}>{data.quotation ? <Link href={`/quotations/${data.quotation}`} className="text-primary-strong hover:underline"><Ltr>{data.quotation_ref}</Ltr></Link> : t("ct.noQuotation")}</InsetRow>
            </InsetList>
            <InsetList title={t("qt.sectionRequest")}>
              <InsetRow label={t("qt.requestedBy")}>{data.requested_by_name}</InsetRow>
              <InsetRow label={t("qt.requestedOn")}>{formatDateTime(data.created_at)}</InsetRow>
              <InsetRow label={t("qt.requestNote")}>{data.request_note ? <span className="whitespace-pre-line">{data.request_note}</span> : empty}</InsetRow>
              <InsetRow label={t("ct.draftedBy")}>{data.drafted_by_name ?? empty}</InsetRow>
            </InsetList>
            {latest && (latest.body_en || latest.body_ar) ? (
              <Card as="section" aria-labelledby="ct-text" className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 id="ct-text" className="text-section text-ink">{t("ct.text")}</h2>
                  {p.can_edit ? <Button variant="secondary" icon={<PencilSimple size={18} aria-hidden />} onClick={() => setSheet("draft")}>{t("ct.next.edit")}</Button> : null}
                </div>
                <p dir="auto" className="mt-3 max-h-80 overflow-auto whitespace-pre-line text-body text-ink">{lang === "ar" && latest.body_ar ? latest.body_ar : latest.body_en || latest.body_ar}</p>
              </Card>
            ) : null}
            <InsetList title={t("ct.sectionSigning")}>
              <InsetRow label={t("ct.number")}>{data.number ? <Ltr>{data.number}</Ltr> : empty}</InsetRow>
              <InsetRow label={t("ct.sentOn")}>{data.sent_at ? formatDateTime(data.sent_at) : empty}</InsetRow>
              <InsetRow label={t("ct.clientSigned")}>{data.client_signed_at ? `${formatDateTime(data.client_signed_at)} · ${t(`ct.via.${data.client_signed_via}`)}` : empty}</InsetRow>
            </InsetList>
            {data.signed_by_name ? (
              <InsetList title={t("qt.sectionSignature")}>
                <InsetRow label={t("qt.signedBy")}>{data.signed_by_name}</InsetRow>
                <InsetRow label={t("qt.signedOn")}>{data.signed_at ? formatDateTime(data.signed_at) : empty}</InsetRow>
                {data.handed_over_at ? <InsetRow label={t("ct.handedOverOn")}>{formatDateTime(data.handed_over_at)}</InsetRow> : null}
                {data.handed_over_by_name ? <InsetRow label={t("ct.handedOverBy")}>{data.handed_over_by_name}</InsetRow> : null}
              </InsetList>
            ) : null}
            {data.status === "cancelled" ? (
              <InsetList title={t("qt.sectionOutcome")}>
                <InsetRow label={t("ct.cancel.reason")}>{data.cancel_reason || empty}</InsetRow>
              </InsetList>
            ) : null}
            {data.versions && data.versions.length ? (
              <InsetList title={t("ct.versions")}>
                {data.versions.map((v) => (
                  <InsetRow key={v.id} label={t("qt.versionN", { number: v.number })}>
                    <span className="block text-end">
                      {v.created_by_name} · {formatDateTime(v.created_at)}
                      {v.note ? <span className="block whitespace-pre-line text-label font-normal text-ink-2">{v.note}</span> : null}
                    </span>
                  </InsetRow>
                ))}
              </InsetList>
            ) : null}
          </div>
        }
      />
      {sheet === "send" ? <SendSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "draft" ? <DraftSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "confirm" ? <ConfirmContractSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "creturn" ? <CommercialReturnSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "toclient" ? <SendToClientSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "copy" ? <ClientCopySheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "download" ? <DownloadSheet path={`/contracts/${data.id}/document/`} fileBase={`contract-${(data.number ?? data.ref).replace(/\//g, "-")}`} onClose={() => setSheet(null)} /> : null}
      {sheet === "approve" ? <ApproveSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "return" ? <ReturnSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "cancel" ? <CancelContractSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
    </>
  );
}
