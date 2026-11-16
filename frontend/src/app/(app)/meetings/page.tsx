"use client";

import { Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { NoAccess } from "@/components/NoAccess";
import { reportTone } from "@/components/meetings/reportUi";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Select, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Appointment, type MeetingReport, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can, canAny } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function MeetingReportsPage() {
  const { user } = useAuth();
  const { t, formatDate } = useI18n();
  const allowed = !!user && canAny(user, "meeting_report.write", "meeting_report.view_all");
  const reports = useFetch<Page<MeetingReport>>(allowed ? "/meeting-reports/?page_size=100" : null);
  const [writing, setWriting] = useState(false);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader
        title={t("mr.title")}
        description={t("mr.description")}
        action={can(user, "meeting_report.write") ? <Button icon={<Plus size={18} aria-hidden />} onClick={() => setWriting(true)}>{t("mr.write")}</Button> : undefined}
      />
      {reports.error ? <ErrorState message={reports.error} onRetry={reports.reload} /> : !reports.data ? <Skeleton className="h-48 max-w-2xl rounded-card" /> : reports.data.results.length === 0 ? (
        <Card className="max-w-2xl p-5"><p className="text-body text-ink-2">{t("mr.none")}</p></Card>
      ) : (
        <Card className="max-w-2xl overflow-hidden">
          <ul className="divide-y divide-line">
            {reports.data.results.map((r) => (
              <li key={r.id}>
                <Link href={`/meetings/${r.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-canvas/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body font-semibold text-ink">{r.lead_company}</p>
                    <p className="truncate text-label font-normal text-ink-2">{r.appointment_title} · {formatDate(r.held_on)} · {r.author_name}</p>
                  </div>
                  <StatusPill tone={reportTone(r.status)}>{t(`mr.status.${r.status}`)}</StatusPill>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {writing ? <WriteSheet existing={reports.data?.results ?? []} onClose={() => setWriting(false)} onDone={() => { setWriting(false); reports.reload(); }} /> : null}
    </>
  );
}

function WriteSheet({ existing, onClose, onDone }: { existing: MeetingReport[]; onClose: () => void; onDone: () => void }) {
  const { t, formatDate } = useI18n();
  const toast = useToast();
  const action = useAction(["appointment", "summary", "attendees", "decisions", "next_steps"]);
  const done = useFetch<Page<Appointment>>("/appointments/?status=done&page_size=100");
  const have = new Set(existing.map((r) => r.appointment));
  const options = (done.data?.results ?? []).filter((a) => a.lead && !have.has(a.id));
  const [f, setF] = useState({ appointment: "", attendees: "", summary: "", decisions: "", next_steps: "" });
  const [local, setLocal] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLTextAreaElement | HTMLSelectElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    if (!f.appointment) return setLocal("mr.err.appointment");
    setLocal("");
    const saved = await action.run(() => api<MeetingReport>("/meeting-reports/", { method: "POST", body: { ...f, appointment: Number(f.appointment) } }));
    if (saved) {
      toast.success(t("mr.created"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("mr.write")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("mr.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <Select name="appointment" label={t("mr.meeting")} required value={f.appointment} onChange={set("appointment")} placeholder={t("mr.chooseMeeting")} hint={options.length === 0 && done.data ? t("mr.noMeetings") : undefined} options={options.map((a) => ({ value: String(a.id), label: `${a.lead_company ?? a.title} · ${formatDate(a.starts_at)}` }))} error={local ? t(local) : action.errors.appointment} />
        <Textarea name="attendees" label={t("mr.attendees")} rows={2} value={f.attendees} onChange={set("attendees")} error={action.errors.attendees} />
        <Textarea name="summary" label={t("mr.summary")} required rows={5} value={f.summary} onChange={set("summary")} error={action.errors.summary} />
        <Textarea name="decisions" label={t("mr.decisions")} rows={3} value={f.decisions} onChange={set("decisions")} error={action.errors.decisions} />
        <Textarea name="next_steps" label={t("mr.nextSteps")} rows={3} value={f.next_steps} onChange={set("next_steps")} error={action.errors.next_steps} />
      </div>
    </Sheet>
  );
}
