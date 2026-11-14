"use client";

import { DotsThreeVertical, Prohibit } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ApproveSheet, CancelContractSheet, MeetingSheet, ReturnSheet, SendSheet, SubmitSheet } from "@/components/contracts/ContractSheets";
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

type Sheet = "send" | "meeting" | "submit" | "approve" | "return" | "cancel" | null;

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDate, formatDateTime } = useI18n();
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
  else if (p.can_send) primary = <Button onClick={() => setSheet("send")}>{t("ct.next.send")}</Button>;
  else if (p.can_review) {
    primary = <Button onClick={() => setSheet("approve")}>{t("ct.next.approve")}</Button>;
    secondary = <Button variant="secondary" onClick={() => setSheet("return")}>{t("ct.next.return")}</Button>;
  } else if (p.can_handover) primary = <Button loading={busy} onClick={() => post("handover", t("ct.handedOver"))}>{t("ct.next.handover")}</Button>;
  else if (p.can_submit) primary = <Button onClick={() => setSheet("submit")}>{t("ct.next.submit")}</Button>;
  if (p.can_log_meeting) {
    if (primary) secondary = <Button variant="secondary" onClick={() => setSheet("meeting")}>{t("ct.next.meeting")}</Button>;
    else primary = <Button onClick={() => setSheet("meeting")}>{t("ct.next.meeting")}</Button>;
  }

  const hint =
    p.can_start ? t(data.status === "returned" ? "ct.hint.redraft" : "ct.hint.start")
    : p.can_send ? t("ct.hint.send")
    : p.can_log_meeting ? t(data.status === "returned" ? "ct.hint.returned" : "ct.hint.meeting")
    : p.can_submit ? t("ct.hint.submit")
    : p.can_review ? t("ct.hint.review")
    : p.can_handover ? t("ct.hint.handover")
    : data.status === "ceo_review" ? t("ct.hint.withCeo")
    : ["requested", "drafting", "returned"].includes(data.status) ? t("ct.hint.withHr")
    : ["with_commercial", "meeting_logged"].includes(data.status) ? t("ct.hint.withCommercial")
    : data.status === "signed" ? t("ct.hint.signedWait")
    : "";

  const menu = p.can_cancel ? (
    <Menu
      label={t("common.actions")}
      trigger={({ open, ...props }) => (
        <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${open ? "bg-canvas" : ""}`}>
          <DotsThreeVertical size={20} weight="bold" aria-hidden />
        </IconButton>
      )}
    >
      {(close) => <MenuItem danger icon={<Prohibit size={20} aria-hidden />} onSelect={() => { close(); setSheet("cancel"); }}>{t("ct.cancel.title")}</MenuItem>}
    </Menu>
  ) : null;
  const empty = <span className="text-ink-3">{"—"}</span>;
  const returned = (data.status === "returned" || data.status === "ceo_review") && data.ceo_comment;

  return (
    <>
      <PageHeader
        back={back}
        title={`${data.ref} · ${data.lead_company}`}
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
                <p className="text-body font-semibold">{t("ct.ceoReturned")}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.ceo_comment}</p>
              </div>
            ) : null}
            <ContractDocuments contract={data} onChanged={reload} />
            <InsetList title={t("qt.sectionClient")}>
              <InsetRow label={t("lead.company")}><Link href={`/leads/${data.lead}`} className="text-primary-strong hover:underline">{data.lead_company}</Link></InsetRow>
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
            {data.meeting_date ? (
              <InsetList title={t("ct.sectionMeeting")}>
                <InsetRow label={t("ct.meeting.date")}>{formatDate(data.meeting_date)}</InsetRow>
                <InsetRow label={t("ct.loggedBy")}>{data.meeting_by_name ?? empty}</InsetRow>
                <InsetRow label={t("ct.meeting.notes")}><span className="whitespace-pre-line">{data.meeting_notes}</span></InsetRow>
              </InsetList>
            ) : null}
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
      {sheet === "meeting" ? <MeetingSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "submit" ? <SubmitSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "approve" ? <ApproveSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "return" ? <ReturnSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "cancel" ? <CancelContractSheet contract={data} onClose={() => setSheet(null)} onDone={done} /> : null}
    </>
  );
}
