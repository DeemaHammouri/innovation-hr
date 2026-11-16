"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { handoverTone } from "@/components/handovers/handoverUi";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button } from "@/components/ui/Button";
import { InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Handover } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type SheetKind = "edit" | "return" | "escalate" | null;

export default function HandoverPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDate, formatDateTime } = useI18n();
  const toast = useToast();
  const { data, error, reload } = useFetch<Handover>(user ? `/handovers/${id}/` : null);
  const [sheet, setSheet] = useState<SheetKind>(null);
  const [busy, setBusy] = useState<"submit" | "accept" | null>(null);
  if (!user) return null;
  const back = { href: "/handovers", label: t("ho.title") };
  if (error) return <><PageHeader title={t("ho.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={t("ho.title")} back={back} /><Skeleton className="h-48 max-w-2xl rounded-card" /></>;
  const p = data.permissions;
  const done = () => { setSheet(null); reload(); };
  async function step(kind: "submit" | "accept", okKey: string) {
    setBusy(kind);
    try {
      await api(`/handovers/${data!.id}/${kind}/`, { method: "POST" });
      toast.success(t(okKey));
      reload();
    } catch (e) {
      const fields = (e as { fields?: Record<string, string[]> }).fields;
      toast.error(fields ? Object.values(fields)[0]?.[0] ?? t("qt.saveFailed") : t("qt.saveFailed"));
    }
    setBusy(null);
  }
  const empty = <span className="text-ink-3">{"—"}</span>;
  const text = (v: string) => (v ? <span className="whitespace-pre-line">{v}</span> : empty);
  return (
    <>
      <PageHeader
        back={back}
        title={`${data.ref} · ${data.client_name}`}
        meta={<StatusPill tone={handoverTone(data.status)}>{t(`ho.status.${data.status}`)}</StatusPill>}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {p.can_edit ? <Button variant="secondary" onClick={() => setSheet("edit")}>{t("ho.edit")}</Button> : null}
            {p.can_escalate ? <Button variant="secondary" onClick={() => setSheet("escalate")}>{t("ho.escalate")}</Button> : null}
            {p.can_return ? <Button variant="secondary" onClick={() => setSheet("return")}>{t("ho.return")}</Button> : null}
            {p.can_accept ? <Button loading={busy === "accept"} onClick={() => step("accept", "ho.accepted")}>{t("ho.accept")}</Button> : null}
            {p.can_submit ? <Button loading={busy === "submit"} onClick={() => step("submit", "ho.submitted")}>{t("ho.submit")}</Button> : null}
          </div>
        }
      />
      <RecordTabs
        target={`handover:${data.id}`}
        canAttach={false}
        overview={
          <div className="space-y-5 md:space-y-6">
            {data.status === "returned" && data.decision_comment ? (
              <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
                <p className="text-body font-semibold">{t("ho.returnedNotes")}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.decision_comment}</p>
              </div>
            ) : null}
            {data.status === "escalated" ? (
              <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
                <p className="text-body font-semibold">{t("ho.escalatedNotes", { name: data.escalated_by_name ?? "" })}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.escalation_reason}</p>
              </div>
            ) : null}
            {data.project ? (
              <div role="note" className="rounded-control border border-success/30 bg-success-bg p-4 text-success-ink">
                <p className="text-body font-semibold">{t("ho.projectCreated")} <Link href="/projects" className="underline"><Ltr>{data.project.ref}</Ltr></Link></p>
              </div>
            ) : null}
            <InsetList title={t("ho.sectionClient")}>
              <InsetRow label={t("ho.client")}><Link href={`/operation/${data.client}`} className="text-primary-strong hover:underline">{data.client_name}</Link></InsetRow>
              <InsetRow label={t("clients.contact")}>{data.contact_person || empty}</InsetRow>
              <InsetRow label={t("op.phone")}>{data.phone ? <Ltr>{data.phone}</Ltr> : empty}</InsetRow>
              <InsetRow label={t("op.email")}>{data.email ? <Ltr>{data.email}</Ltr> : empty}</InsetRow>
              <InsetRow label={t("ho.preparedBy")}>{data.prepared_by_name}</InsetRow>
            </InsetList>
            <InsetList title={t("ho.sectionWork")}>
              <InsetRow label={t("ho.services")}>{text(data.services)}</InsetRow>
              <InsetRow label={t("ho.scope")}>{text(data.scope_notes)}</InsetRow>
              <InsetRow label={t("ho.contacts")}>{text(data.contacts)}</InsetRow>
              <InsetRow label={t("ho.requirements")}>{text(data.special_requirements)}</InsetRow>
              <InsetRow label={t("ho.startDate")}>{data.start_date ? formatDate(data.start_date) : empty}</InsetRow>
            </InsetList>
            <InsetList title={t("ho.sectionDecision")}>
              <InsetRow label={t("ho.submittedAt")}>{data.submitted_at ? formatDateTime(data.submitted_at) : empty}</InsetRow>
              <InsetRow label={t("ho.decidedBy")}>{data.status === "accepted" && data.decided_by_name ? `${data.decided_by_name} · ${formatDateTime(data.decided_at!)}` : empty}</InsetRow>
            </InsetList>
          </div>
        }
      />
      {sheet === "edit" ? <EditSheet handover={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "return" ? (
        <ReasonSheet<Handover> path={`/handovers/${data.id}/return/`} onClose={() => setSheet(null)} onDone={done} field="comment" title={t("ho.return")} intro={t("ho.returnText")} question={t("ct.return.comment")} confirm={t("ct.return.save")} done={t("ho.returned")} emptyKey="qt.err.comment" />
      ) : null}
      {sheet === "escalate" ? (
        <ReasonSheet<Handover> path={`/handovers/${data.id}/escalate/`} onClose={() => setSheet(null)} onDone={done} field="reason" title={t("ho.escalate")} intro={t("ho.escalateText")} question={t("ho.escalateReason")} confirm={t("ho.escalateSave")} done={t("ho.escalated")} emptyKey="ho.err.reason" />
      ) : null}
    </>
  );
}

function EditSheet({ handover, onClose, onDone }: { handover: Handover; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["services", "scope_notes", "contacts", "special_requirements", "start_date"]);
  const [f, setF] = useState({ services: handover.services, scope_notes: handover.scope_notes, contacts: handover.contacts, special_requirements: handover.special_requirements, start_date: handover.start_date ?? "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    const saved = await action.run(() => api<Handover>(`/handovers/${handover.id}/save/`, { method: "POST", body: f }));
    if (saved) {
      toast.success(t("ho.saved"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("ho.edit")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("common.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-label font-normal text-ink-2">{t("ho.noPrices")}</p>
        <Textarea name="services" label={t("ho.services")} required rows={4} value={f.services} onChange={set("services")} error={action.errors.services} />
        <Textarea name="scope_notes" label={t("ho.scope")} required rows={4} value={f.scope_notes} onChange={set("scope_notes")} error={action.errors.scope_notes} />
        <Textarea name="contacts" label={t("ho.contacts")} rows={3} value={f.contacts} onChange={set("contacts")} error={action.errors.contacts} />
        <Textarea name="special_requirements" label={t("ho.requirements")} rows={3} value={f.special_requirements} onChange={set("special_requirements")} error={action.errors.special_requirements} />
        <Input name="start_date" label={t("ho.startDate")} type="date" value={f.start_date} onChange={set("start_date")} error={action.errors.start_date} />
      </div>
    </Sheet>
  );
}
