"use client";

import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type GeneralTask } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Person = { id: number; full_name: string; department: string | null };
const todayIso = () => new Date().toLocaleDateString("en-CA");

/** Give a task to someone, or change an open one. Changing the deadline starts a new overdue alert on the server. */
export function TaskFormSheet({ task, onClose, onDone }: { task?: GeneralTask; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { data: people } = useFetch<Person[]>("/tasks/assignees/");
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [assignee, setAssignee] = useState(task ? String(task.assignee) : "");
  const [deadline, setDeadline] = useState(task?.deadline ?? "");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["title", "assignee", "deadline", "description"]);
  const errors = { ...action.errors, ...local };

  async function save() {
    const found: Record<string, string> = {};
    if (!title.trim()) found.title = "gt.err.title";
    if (!assignee) found.assignee = "gt.err.assignee";
    if (!deadline) found.deadline = "gt.err.deadline";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const body = { title: title.trim(), description: description.trim(), assignee: Number(assignee), deadline };
    const saved = await action.run(() => (task ? api(`/tasks/${task.id}/`, { method: "PATCH", body }) : api("/tasks/", { method: "POST", body })));
    if (saved) {
      toast.success(t(task ? "gt.updated" : "gt.created"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t(task ? "gt.editTitle" : "gt.newTitle")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("common.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <Input name="title" label={t("gt.title.field")} required value={title} onChange={(e) => { setTitle(e.target.value); setLocal({}); }} error={errors.title} />
        <Textarea name="description" label={t("gt.details")} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} error={errors.description} />
        <Select
          name="assignee"
          label={t("gt.assignee")}
          required
          value={assignee}
          placeholder={t("gt.pickPerson")}
          onChange={(e) => { setAssignee(e.target.value); setLocal({}); }}
          error={errors.assignee}
          options={(people ?? []).map((p) => ({ value: String(p.id), label: p.department ? `${p.full_name} · ${p.department}` : p.full_name }))}
        />
        <Input name="deadline" label={t("gt.deadline")} type="date" required min={task ? undefined : todayIso()} value={deadline} onChange={(e) => { setDeadline(e.target.value); setLocal({}); }} error={errors.deadline} hint={task ? t("gt.deadlineHint") : undefined} />
      </div>
    </Sheet>
  );
}

/** Notes, files and history for one task. The assignee and whoever manages it can add files while it is open. */
export function TaskDetailSheet({ task, onClose }: { task: GeneralTask; onClose: () => void }) {
  const { t, formatDate } = useI18n();
  return (
    <Sheet open onClose={onClose} title={task.title} footer={<Button onClick={onClose}>{t("common.done")}</Button>}>
      <RecordTabs
        target={`gtask:${task.id}`}
        canAttach={task.can_attach}
        overview={
          <div className="space-y-2">
            <p className="text-body text-ink-2">{task.assigned_by_name} → {task.assignee_name} · {t("gt.due", { date: formatDate(task.deadline) })}</p>
            {task.description ? <p className="whitespace-pre-line text-body text-ink">{task.description}</p> : null}
          </div>
        }
      />
    </Sheet>
  );
}
