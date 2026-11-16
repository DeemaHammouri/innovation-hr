"use client";

import { DotsThreeVertical } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { Button, IconButton } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/Card";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type TaskInstance, type TaskStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { CompleteTaskSheet, DeliverSheet, ProgressSheet, SkipTaskSheet, TaskDetailSheet, TaskReasonSheet } from "./OpSheets";

type Kind = "complete" | "skip" | "progress" | "wait" | "block" | "return" | "escalate" | "files" | "deliver";

const TONE: Record<TaskStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = {
  open: "neutral", in_progress: "primary", waiting: "warning", blocked: "danger", submitted: "primary", done: "success", skipped: "neutral",
};

/** Task rows with the whole life of a task: start, progress, wait, block, submit, then the reviewer approves or sends it back. */
export function TaskList({ tasks, onChanged, showClient = true }: { tasks: TaskInstance[]; onChanged: () => void; showClient?: boolean }) {
  const { t, msg, formatDate, formatDateTime } = useI18n();
  const toast = useToast();
  const [sheet, setSheet] = useState<{ kind: Kind; task: TaskInstance } | null>(null);
  const done = () => {
    setSheet(null);
    onChanged();
  };
  async function step(task: TaskInstance, action: string, message: string) {
    try {
      await api(`/operations/tasks/${task.id}/${action}/`, { method: "POST", body: {} });
      toast.success(message);
      onChanged();
    } catch (e) {
      toast.error(msg(errorMessage(e)));
    }
  }
  const open = (kind: Kind, task: TaskInstance) => setSheet({ kind, task });
  return (
    <>
      <ul className="divide-y divide-line">
        {tasks.map((task) => {
          const live = task.status === "open" || task.status === "in_progress" || task.status === "waiting" || task.status === "blocked";
          return (
            <li key={task.id} className="px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-body font-semibold text-ink">{task.title}</p>
                  <p className="text-label font-normal text-ink-2">
                    {showClient ? <><Link href={`/operation/${task.client}`} className="text-primary-strong underline-offset-2 hover:underline underline">{task.client_name}</Link> · </> : null}
                    {t("op.task.due", { date: formatDate(task.due_date) })} · {task.assignee_name ?? t("op.rec.unassigned")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {task.overdue ? <StatusPill tone="danger">{t("op.task.overdue")}</StatusPill> : null}
                  {task.escalation_level > 0 ? <StatusPill tone="warning">{t("op.task.escalatedTo", { who: t(task.escalation_level > 1 ? "op.task.toCeo" : "op.task.toHead") })}</StatusPill> : null}
                  <StatusPill tone={TONE[task.status]}>{t(`op.task.status.${task.status}`)}</StatusPill>
                  {task.can_work && task.status === "open" ? <Button onClick={() => step(task, "start", t("op.task.started"))}>{t("op.task.start")}</Button> : null}
                  {task.can_work && task.status === "in_progress" ? <Button onClick={() => open("progress", task)}>{t("op.task.progress")}</Button> : null}
                  {task.can_work && (task.status === "waiting" || task.status === "blocked") ? <Button onClick={() => step(task, "resume", t("op.task.resumed"))}>{t("op.task.resume")}</Button> : null}
                  {task.can_review ? (
                    <>
                      <Button onClick={() => step(task, "approve", t("op.task.approved"))}>{t("op.task.approve")}</Button>
                      <Button variant="secondary" onClick={() => open("return", task)}>{t("op.task.return")}</Button>
                    </>
                  ) : null}
                  <Menu
                    label={t("common.actions")}
                    trigger={({ open: isOpen, ...props }) => (
                      <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${isOpen ? "bg-canvas" : ""}`}>
                        <DotsThreeVertical size={20} weight="bold" aria-hidden />
                      </IconButton>
                    )}
                  >
                    {(close) => (
                      <>
                        <MenuItem onSelect={() => { close(); open("files", task); }}>{t("op.task.details")}</MenuItem>
                        {task.can_work && task.status === "in_progress" ? <MenuItem onSelect={() => { close(); void step(task, "submit", t("op.task.submitted")); }}>{t("op.task.submit")}</MenuItem> : null}
                        {task.can_work && task.status === "in_progress" ? <MenuItem onSelect={() => { close(); open("wait", task); }}>{t("op.task.wait")}</MenuItem> : null}
                        {task.can_work && task.status === "in_progress" ? <MenuItem onSelect={() => { close(); open("block", task); }}>{t("op.task.block")}</MenuItem> : null}
                        {task.can_escalate ? <MenuItem onSelect={() => { close(); open("escalate", task); }}>{t("op.task.escalate")}</MenuItem> : null}
                        {task.can_publish ? <MenuItem onSelect={() => { close(); open("deliver", task); }}>{t("op.task.deliver")}</MenuItem> : null}
                        {task.can_work && live ? <MenuItem onSelect={() => { close(); open("skip", task); }}>{t("op.task.skip")}</MenuItem> : null}
                        {task.can_work && live && task.can_complete ? <MenuItem onSelect={() => { close(); open("complete", task); }}>{t("op.task.complete")}</MenuItem> : null}
                      </>
                    )}
                  </Menu>
                </div>
              </div>
              {task.status === "in_progress" || task.status === "waiting" || task.status === "blocked" ? (
                <div className="mt-2" role="progressbar" aria-label={t("op.task.progressLabel")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={task.progress}>
                  <div className="h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-primary" style={{ width: `${task.progress}%` }} /></div>
                </div>
              ) : null}
              {task.status_reason && (task.status === "waiting" || task.status === "blocked") ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{task.status_reason}</p> : null}
              {task.review_note && task.status === "in_progress" ? <p className="mt-1 whitespace-pre-line text-label font-normal text-warning-ink">{t("op.task.returnedNote", { note: task.review_note })}</p> : null}
              {(task.status === "done" || task.status === "submitted") && task.completion_note ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{task.completion_note}</p> : null}
              {task.status === "skipped" ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{t("op.task.skippedBecause", { reason: task.skip_reason })}</p> : null}
              {task.deliverables.length ? (
                <p className="mt-1 text-label font-normal text-ink-2">
                  {task.deliverables.map((d) => `${d.title} · ${d.acknowledged_at ? t("op.task.ackedAt", { date: formatDateTime(d.acknowledged_at) }) : t("op.task.notAcked")}`).join(" | ")}
                </p>
              ) : null}
              {task.closed_at ? <p className="mt-0.5 text-caption text-ink-2">{task.closed_by_name} · {formatDateTime(task.closed_at)}</p> : null}
            </li>
          );
        })}
      </ul>
      {sheet?.kind === "complete" ? <CompleteTaskSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === "skip" ? <SkipTaskSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === "progress" ? <ProgressSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === "wait" || sheet?.kind === "block" || sheet?.kind === "return" || sheet?.kind === "escalate" ? <TaskReasonSheet kind={sheet.kind} task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === "files" ? <TaskDetailSheet task={sheet.task} onClose={done} /> : null}
      {sheet?.kind === "deliver" ? <DeliverSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
    </>
  );
}
