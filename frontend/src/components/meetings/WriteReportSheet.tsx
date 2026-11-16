"use client";

import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type Appointment, type MeetingReport, type Page } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** Write a meeting report. From the reports page the person picks the meeting; from an appointment the meeting is already known (`fixed`). */
export function WriteReportSheet({ existing = [], fixed, onClose, onDone }: { existing?: MeetingReport[]; fixed?: Appointment; onClose: () => void; onDone: (created: MeetingReport) => void }) {
  const { t, formatDate } = useI18n();
  const toast = useToast();
  const action = useAction(["appointment", "summary", "attendees", "decisions", "next_steps"]);
  const done = useFetch<Page<Appointment>>(fixed ? null : "/appointments/?status=done&page_size=100");
  const have = new Set(existing.map((r) => r.appointment));
  const options = (done.data?.results ?? []).filter((a) => a.lead && !have.has(a.id));
  const [f, setF] = useState({ appointment: fixed ? String(fixed.id) : "", attendees: "", summary: "", decisions: "", next_steps: "" });
  const [local, setLocal] = useState("");
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLTextAreaElement | HTMLSelectElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    if (!f.appointment) return setLocal("mr.err.appointment");
    setLocal("");
    const saved = await action.run(() => api<MeetingReport>("/meeting-reports/", { method: "POST", body: { ...f, appointment: Number(f.appointment) } }));
    if (saved) {
      toast.success(t("mr.created"));
      onDone(saved);
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("mr.write")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("mr.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        {fixed ? (
          <p className="text-body font-medium text-ink">{fixed.lead_company ?? fixed.title} · {formatDate(fixed.starts_at)}</p>
        ) : (
          <Select name="appointment" label={t("mr.meeting")} required value={f.appointment} onChange={set("appointment")} placeholder={t("mr.chooseMeeting")} hint={options.length === 0 && done.data ? t("mr.noMeetings") : undefined} options={options.map((a) => ({ value: String(a.id), label: `${a.lead_company ?? a.title} · ${formatDate(a.starts_at)}` }))} error={local ? t(local) : action.errors.appointment} />
        )}
        <Textarea name="attendees" label={t("mr.attendees")} rows={2} value={f.attendees} onChange={set("attendees")} error={action.errors.attendees} />
        <Textarea name="summary" label={t("mr.summary")} required rows={5} value={f.summary} onChange={set("summary")} error={action.errors.summary} />
        <Textarea name="decisions" label={t("mr.decisions")} rows={3} value={f.decisions} onChange={set("decisions")} error={action.errors.decisions} />
        <Textarea name="next_steps" label={t("mr.nextSteps")} rows={3} value={f.next_steps} onChange={set("next_steps")} error={action.errors.next_steps} />
      </div>
    </Sheet>
  );
}
