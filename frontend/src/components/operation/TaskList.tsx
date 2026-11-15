"use client";

import { CheckCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/Card";
import type { TaskInstance } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { CompleteTaskSheet, SkipTaskSheet } from "./OpSheets";

/** Task instances as rows, with Complete and Skip for the ones the person may handle. */
export function TaskList({ tasks, onChanged, showClient = true }: { tasks: TaskInstance[]; onChanged: () => void; showClient?: boolean }) {
  const { t, formatDate, formatDateTime } = useI18n();
  const [sheet, setSheet] = useState<{ kind: "complete" | "skip"; task: TaskInstance } | null>(null);
  const done = () => {
    setSheet(null);
    onChanged();
  };
  return (
    <>
      <ul className="divide-y divide-line">
        {tasks.map((task) => (
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
                {task.status === "open" && task.overdue ? <StatusPill tone="danger">{t("op.task.overdue")}</StatusPill> : null}
                {task.status === "done" ? <StatusPill tone="success">{t("op.task.statusDone")}</StatusPill> : null}
                {task.status === "skipped" ? <StatusPill tone="neutral">{t("op.task.statusSkipped")}</StatusPill> : null}
                {task.can_work ? (
                  <>
                    <Button variant="secondary" icon={<CheckCircle size={18} aria-hidden />} onClick={() => setSheet({ kind: "complete", task })}>{t("op.task.complete")}</Button>
                    <Button variant="ghost" onClick={() => setSheet({ kind: "skip", task })}>{t("op.task.skip")}</Button>
                  </>
                ) : null}
              </div>
            </div>
            {task.status === "done" && task.completion_note ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{task.completion_note}</p> : null}
            {task.status === "skipped" ? <p className="mt-1 whitespace-pre-line text-label font-normal text-ink-2">{t("op.task.skippedBecause", { reason: task.skip_reason })}</p> : null}
            {task.closed_at ? <p className="mt-0.5 text-caption text-ink-2">{task.closed_by_name} · {formatDateTime(task.closed_at)}</p> : null}
          </li>
        ))}
      </ul>
      {sheet?.kind === "complete" ? <CompleteTaskSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet?.kind === "skip" ? <SkipTaskSheet task={sheet.task} onClose={() => setSheet(null)} onDone={done} /> : null}
    </>
  );
}
