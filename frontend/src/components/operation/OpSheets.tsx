"use client";

import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type OpAssignee, type OpClient, type QAMeeting, type RecurringTask, type TaskInstance } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { FREQUENCIES } from "./opUi";

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function CompleteTaskSheet({ task, onClose, onDone }: { task: TaskInstance; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api(`/operations/tasks/${task.id}/complete/`, { method: "POST", body: { note: note.trim() } }));
    if (saved) {
      toast.success(t("op.task.completed"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("op.task.completeTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="complete-task-form" loading={action.saving}>{t("op.task.complete")}</Button>
        </>
      }
    >
      <form id="complete-task-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{task.title} · {task.client_name}</p>
        <Textarea name="note" label={t("op.task.note")} hint={t("op.task.noteHint")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

export function SkipTaskSheet({ task, onClose, onDone }: { task: TaskInstance; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<TaskInstance>
      path={`/operations/tasks/${task.id}/skip/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("op.task.skipTitle")}
      intro={`${task.title} · ${task.client_name}`}
      question={t("op.task.skipReason")}
      confirm={t("op.task.skip")}
      done={t("op.task.skipped")}
      emptyKey="op.err.skip"
    />
  );
}

export function NotApplicableSheet({ itemId, name, onClose, onDone }: { itemId: number; name: string; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet
      path={`/operations/checklist/${itemId}/not-applicable/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("op.na.title")}
      intro={name}
      question={t("op.na.reason")}
      confirm={t("op.na.save")}
      done={t("op.na.done")}
      emptyKey="op.err.na"
    />
  );
}

export function AddItemSheet({ client, onClose, onDone }: { client: OpClient; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [en, setEn] = useState("");
  const [ar, setAr] = useState("");
  const [required, setRequired] = useState(true);
  const [local, setLocal] = useState("");
  const action = useAction(["name_en", "name_ar"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!en.trim() || !ar.trim()) {
      setLocal("op.err.itemName");
      document.getElementById(en.trim() ? "field-name_ar" : "field-name_en")?.focus();
      return;
    }
    const saved = await action.run(() => api(`/operations/clients/${client.id}/checklist/`, { method: "POST", body: { name_en: en.trim(), name_ar: ar.trim(), required } }));
    if (saved) {
      toast.success(t("op.item.added"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("op.item.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="add-item-form" loading={action.saving}>{t("op.item.add")}</Button>
        </>
      }
    >
      <form id="add-item-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="name_en" label={t("op.item.nameEn")} required value={en} onChange={(e) => { setEn(e.target.value); setLocal(""); }} error={!en.trim() ? local || action.errors.name_en : action.errors.name_en} />
        <Input name="name_ar" label={t("op.item.nameAr")} required dir="rtl" lang="ar" value={ar} onChange={(e) => { setAr(e.target.value); setLocal(""); }} error={!ar.trim() ? local : undefined} />
        <label htmlFor="item-required" className="flex min-h-11 cursor-pointer items-center gap-3 text-label text-ink">
          <input id="item-required" type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} className="size-4 accent-[var(--color-primary)]" />
          {t("op.item.requiredHelp")}
        </label>
      </form>
    </Sheet>
  );
}

/** Create or edit a recurring client task. The server validates; the screen only explains. */
export function RecurringSheet({ client, task, onClose, onDone }: { client: OpClient; task?: RecurringTask; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { data: people } = useFetch<OpAssignee[]>("/operations/assignees/");
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [frequency, setFrequency] = useState<string>(task?.frequency ?? "monthly");
  const [days, setDays] = useState(task?.interval_days ? String(task.interval_days) : "");
  const [start, setStart] = useState(task?.start_date ?? todayIso());
  const [assignee, setAssignee] = useState(task?.assignee ? String(task.assignee) : "");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["title", "frequency", "interval_days", "start_date", "assignee", "description"]);
  const errors = { ...action.errors, ...local };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!title.trim()) found.title = "Enter a title for the task.";
    if (frequency === "custom" && !(Number(days) >= 1 && Number(days) <= 365)) found.interval_days = "Enter a number of days from 1 to 365.";
    if (!start) found.start_date = "Choose the first due date.";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const body = { client: client.id, title: title.trim(), description: description.trim(), frequency, interval_days: frequency === "custom" ? Number(days) : null, start_date: start, assignee: assignee ? Number(assignee) : null };
    const saved = await action.run(() => (task ? api(`/operations/recurring/${task.id}/`, { method: "PATCH", body }) : api("/operations/recurring/", { method: "POST", body })));
    if (saved) {
      toast.success(t(task ? "op.rec.updated" : "op.rec.created"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t(task ? "op.rec.editTitle" : "op.rec.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="recurring-form" loading={action.saving}>{t(task ? "common.save" : "op.rec.add")}</Button>
        </>
      }
    >
      <form id="recurring-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="title" label={t("op.rec.title")} required value={title} onChange={(e) => { setTitle(e.target.value); setLocal({}); }} error={errors.title} />
        <Textarea name="description" label={t("op.rec.description")} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} error={errors.description} />
        <Select name="frequency" label={t("op.rec.frequency")} required value={frequency} onChange={(e) => { setFrequency(e.target.value); setLocal({}); }} error={errors.frequency} options={FREQUENCIES.map((f) => ({ value: f, label: f === "custom" ? t("op.freq.custom") : t(`op.freq.${f}`) }))} />
        {frequency === "custom" ? <Input name="interval_days" label={t("op.rec.everyDays")} required inputMode="numeric" ltr value={days} onChange={(e) => { setDays(e.target.value); setLocal({}); }} error={errors.interval_days} /> : null}
        <Input name="start_date" label={t(task ? "op.rec.startDate" : "op.rec.firstDue")} type="date" required min={task ? undefined : todayIso()} value={start} onChange={(e) => { setStart(e.target.value); setLocal({}); }} error={errors.start_date} />
        <Select name="assignee" label={t("op.rec.assignee")} placeholder={t("op.rec.unassigned")} value={assignee} onChange={(e) => setAssignee(e.target.value)} error={errors.assignee} options={(people ?? []).map((p) => ({ value: String(p.id), label: p.full_name }))} />
      </form>
    </Sheet>
  );
}

export function MeetingSheet({ client, onClose, onDone }: { client: OpClient; onClose: () => void; onDone: (m: QAMeeting) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [held, setHeld] = useState(todayIso());
  const [notes, setNotes] = useState("");
  const [next, setNext] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["held_on", "notes", "next_date"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!held) found.held_on = "Choose the date the meeting took place.";
    if (!notes.trim()) found.notes = "Write what was discussed in the meeting.";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const saved = await action.run(() => api<QAMeeting>("/operations/meetings/", { method: "POST", body: { client: client.id, held_on: held, notes: notes.trim(), next_date: next || null } }));
    if (saved) {
      toast.success(t("op.meet.logged"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("op.meet.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="qa-form" loading={action.saving}>{t("op.meet.save")}</Button>
        </>
      }
    >
      <form id="qa-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="held_on" label={t("op.meet.date")} type="date" required max={todayIso()} value={held} onChange={(e) => { setHeld(e.target.value); setLocal({}); }} error={errors.held_on} />
        <Textarea name="notes" label={t("op.meet.notes")} required rows={4} value={notes} onChange={(e) => { setNotes(e.target.value); setLocal({}); }} error={errors.notes} />
        <Input name="next_date" label={t("op.meet.next")} type="date" min={held} hint={t("op.meet.nextHint", { days: client.qa_cadence_days })} value={next} onChange={(e) => setNext(e.target.value)} error={errors.next_date} />
      </form>
    </Sheet>
  );
}

export function CadenceSheet({ client, onClose, onDone }: { client: OpClient; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [days, setDays] = useState(String(client.qa_cadence_days));
  const action = useAction(["qa_cadence_days"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api(`/operations/clients/${client.id}/cadence/`, { method: "POST", body: { qa_cadence_days: Number(days) } }));
    if (saved) {
      toast.success(t("op.cadence.saved"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("op.cadence.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="cadence-form" loading={action.saving}>{t("common.save")}</Button>
        </>
      }
    >
      <form id="cadence-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="qa_cadence_days" label={t("op.cadence.days")} required inputMode="numeric" ltr hint={t("op.cadence.hint")} value={days} onChange={(e) => setDays(e.target.value)} error={action.errors.qa_cadence_days} />
      </form>
    </Sheet>
  );
}
