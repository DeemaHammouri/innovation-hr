"use client";

import { FilePdf } from "@phosphor-icons/react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DownloadSheet } from "@/components/documents/DownloadSheet";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { reportTone } from "@/components/meetings/reportUi";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { SignaturePad } from "@/components/ui/SignaturePad";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type MeetingReport } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Sheet = "edit" | "sign" | "return" | "download" | null;

export default function MeetingReportPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDate, formatDateTime } = useI18n();
  const toast = useToast();
  const { data, error, reload } = useFetch<MeetingReport>(user ? `/meeting-reports/${id}/` : null);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const back = { href: "/meetings", label: t("mr.title") };
  if (error) return <><PageHeader title={t("mr.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={t("mr.title")} back={back} /><Skeleton className="h-48 max-w-2xl rounded-card" /></>;
  const p = data.permissions;
  const done = () => { setSheet(null); reload(); };
  async function approve() {
    setBusy(true);
    try {
      await api(`/meeting-reports/${data!.id}/approve/`, { method: "POST" });
      toast.success(t("mr.approved"));
      reload();
    } catch {
      toast.error(t("qt.saveFailed"));
    }
    setBusy(false);
  }
  const empty = <span className="text-ink-3">{"—"}</span>;
  const text = (v: string) => (v ? <span className="whitespace-pre-line">{v}</span> : empty);
  return (
    <>
      <PageHeader
        back={back}
        title={`${data.ref} · ${data.lead_company}`}
        meta={<StatusPill tone={reportTone(data.status)}>{t(`mr.status.${data.status}`)}</StatusPill>}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" icon={<FilePdf size={18} aria-hidden />} onClick={() => setSheet("download")}>{t("doc.menu")}</Button>
            {p.can_edit ? <Button variant="secondary" onClick={() => setSheet("edit")}>{t("mr.edit")}</Button> : null}
            {p.can_return ? <Button variant="secondary" onClick={() => setSheet("return")}>{t("ct.next.return")}</Button> : null}
            {p.can_approve ? <Button loading={busy} onClick={approve}>{t("mr.approve")}</Button> : null}
            {p.can_sign ? <Button onClick={() => setSheet("sign")}>{t("mr.sign")}</Button> : null}
          </div>
        }
      />
      <RecordTabs
        target={`meetingreport:${data.id}`}
        canAttach={false}
        overview={
          <div className="space-y-5 md:space-y-6">
            {data.status === "returned" && data.ceo_comment ? (
              <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
                <p className="text-body font-semibold">{t("ct.returnedNotes")}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.ceo_comment}</p>
              </div>
            ) : null}
            <InsetList title={t("mr.sectionMeeting")}>
              <InsetRow label={t("mr.meeting")}>{data.appointment_title}</InsetRow>
              <InsetRow label={t("mr.heldOn")}>{formatDate(data.held_on)}</InsetRow>
              <InsetRow label={t("mr.author")}>{data.author_name}</InsetRow>
              <InsetRow label={t("mr.attendees")}>{text(data.attendees)}</InsetRow>
            </InsetList>
            <InsetList title={t("mr.sectionReport")}>
              <InsetRow label={t("mr.summary")}>{text(data.summary)}</InsetRow>
              <InsetRow label={t("mr.decisions")}>{text(data.decisions)}</InsetRow>
              <InsetRow label={t("mr.nextSteps")}>{text(data.next_steps)}</InsetRow>
            </InsetList>
            <InsetList title={t("mr.sectionSigning")}>
              <InsetRow label={t("mr.signedBy")}>{data.signed_by_name ? `${data.signed_by_name} · ${formatDateTime(data.signed_at!)}` : empty}</InsetRow>
              <InsetRow label={t("mr.approvedBy")}>{data.ceo_by_name && data.status === "approved" ? `${data.ceo_by_name} · ${formatDateTime(data.ceo_at!)}` : empty}</InsetRow>
            </InsetList>
          </div>
        }
      />
      {sheet === "edit" ? <EditSheet report={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "sign" ? <SignSheet report={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "return" ? (
        <ReasonSheet<MeetingReport> path={`/meeting-reports/${data.id}/return/`} onClose={() => setSheet(null)} onDone={done} field="comment" title={t("ct.return.title")} intro={t("mr.returnText")} question={t("ct.return.comment")} confirm={t("ct.return.save")} done={t("ct.returned")} emptyKey="qt.err.comment" />
      ) : null}
      {sheet === "download" ? <DownloadSheet path={`/meeting-reports/${data.id}/document/`} fileBase={data.ref} onClose={() => setSheet(null)} /> : null}
    </>
  );
}

function EditSheet({ report, onClose, onDone }: { report: MeetingReport; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["summary", "attendees", "decisions", "next_steps"]);
  const [f, setF] = useState({ attendees: report.attendees, summary: report.summary, decisions: report.decisions, next_steps: report.next_steps });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLTextAreaElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    const saved = await action.run(() => api<MeetingReport>(`/meeting-reports/${report.id}/`, { method: "PATCH", body: f }));
    if (saved) {
      toast.success(t("mr.saved"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("mr.edit")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("mr.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <Textarea name="attendees" label={t("mr.attendees")} rows={2} value={f.attendees} onChange={set("attendees")} error={action.errors.attendees} />
        <Textarea name="summary" label={t("mr.summary")} required rows={5} value={f.summary} onChange={set("summary")} error={action.errors.summary} />
        <Textarea name="decisions" label={t("mr.decisions")} rows={3} value={f.decisions} onChange={set("decisions")} error={action.errors.decisions} />
        <Textarea name="next_steps" label={t("mr.nextSteps")} rows={3} value={f.next_steps} onChange={set("next_steps")} error={action.errors.next_steps} />
      </div>
    </Sheet>
  );
}

function SignSheet({ report, onClose, onDone }: { report: MeetingReport; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["signature", "stamp"]);
  const [signature, setSignature] = useState("");
  const [local, setLocal] = useState("");
  async function go() {
    if (!signature) return setLocal("sign.drawHere");
    setLocal("");
    const saved = await action.run(() => api<MeetingReport>(`/meeting-reports/${report.id}/sign/`, { method: "POST", body: { signature } }));
    if (saved) {
      toast.success(t("mr.signedDone"));
      onDone();
    }
  }
  return (
    <Sheet open alert onClose={onClose} title={t("mr.sign")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={go}>{t("mr.sign")}</Button></>}>
      <FormError message={action.formError} />
      <p className="mb-4 text-body text-ink-2">{t("mr.signText", { name: report.lead_company })}</p>
      <SignaturePad label={t("sign.pad")} onChange={(d) => { setSignature(d); setLocal(""); }} error={local ? t(local) : action.errors.signature ?? action.errors.stamp} />
    </Sheet>
  );
}
