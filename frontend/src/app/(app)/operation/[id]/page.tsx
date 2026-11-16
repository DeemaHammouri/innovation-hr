"use client";

import { CalendarCheck, PencilSimple, Plus } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { ChecklistPanel } from "@/components/operation/ChecklistPanel";
import { CadenceSheet, MeetingSheet, RecurringSheet } from "@/components/operation/OpSheets";
import { ClientStatusPill, useFrequencyLabel } from "@/components/operation/opUi";
import { TaskList } from "@/components/operation/TaskList";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { api, errorMessage, type OpClient, type Page, type QAMeeting, type RecurringTask, type TaskInstance } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useToast } from "@/components/ui/Toast";

type Sheet = { kind: "meeting" | "cadence" } | { kind: "recurring"; task?: RecurringTask } | null;

export default function OperationClientPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDate, formatDateTime, msg } = useI18n();
  const toast = useToast();
  const freq = useFrequencyLabel();
  const { data, error, loading, reload } = useFetch<OpClient>(user ? `/operations/clients/${id}/` : null);
  const tasks = useFetch<Page<TaskInstance>>(user ? `/operations/tasks/?client=${id}&page_size=20` : null);
  const meetings = useFetch<Page<QAMeeting>>(user ? `/operations/meetings/?client=${id}&page_size=20` : null);
  const showSkeleton = useDelayed(loading);
  const [sheet, setSheet] = useState<Sheet>(null);

  if (!user) return null;
  const back = { href: "/operation", label: t("op.title") };
  if (error) return <><PageHeader title={t("op.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) {
    return (
      <>
        <PageHeader title={t("op.title")} back={back} />
        {showSkeleton ? <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-24 rounded-card" /><Skeleton className="h-48 rounded-card" /></div> : null}
      </>
    );
  }
  if (!can(user, "operation.access")) return <NoAccess />;
  const { can_work: work, can_manage: manage } = data.permissions;
  const refresh = () => {
    setSheet(null);
    reload();
    tasks.reload();
    meetings.reload();
  };
  const empty = <span className="text-ink-3">{"—"}</span>;

  async function toggle(r: RecurringTask) {
    try {
      await api(`/operations/recurring/${r.id}/`, { method: "PATCH", body: { active: !r.active } });
      toast.success(t(r.active ? "op.rec.paused" : "op.rec.resumed"));
      reload();
    } catch (err) {
      toast.error(msg(errorMessage(err)));
    }
  }

  return (
    <>
      <PageHeader
        back={back}
        title={data.company_name}
        meta={<span className="flex flex-wrap items-center gap-2"><ClientStatusPill status={data.status} />{data.qa_overdue ? <StatusPill tone="warning">{t("op.qaOverdue")}</StatusPill> : null}</span>}
        action={work ? <Button icon={<CalendarCheck size={20} aria-hidden />} onClick={() => setSheet({ kind: "meeting" })}>{t("op.meet.log")}</Button> : null}
      />
      <RecordTabs
        target={`client:${data.id}`}
        canAttach={work}
        overview={
          <div className="space-y-5 md:space-y-6">
            <ChecklistPanel client={data} onChanged={refresh} />

            <Card as="section" aria-labelledby="op-recurring" className="overflow-hidden">
              <div className="flex items-center justify-between gap-3 p-4">
                <h2 id="op-recurring" className="text-section text-ink">{t("op.rec.title.section")}</h2>
                {manage ? <Button variant="secondary" icon={<Plus size={18} aria-hidden />} onClick={() => setSheet({ kind: "recurring" })}>{t("op.rec.add")}</Button> : null}
              </div>
              {(data.recurring_tasks ?? []).length === 0 ? (
                <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("op.rec.empty")}</p>
              ) : (
                <ul className="divide-y divide-line border-t border-line">
                  {(data.recurring_tasks ?? []).map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                      <div className="min-w-0">
                        <p className="text-body font-semibold text-ink">{r.title}</p>
                        <p className="text-label font-normal text-ink-2">{freq(r)} · {r.assignee_name ?? t("op.rec.unassigned")} · {r.active ? t("op.rec.nextDue", { date: formatDate(r.next_due) }) : t("op.rec.pausedLabel")}</p>
                      </div>
                      {manage ? (
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" onClick={() => toggle(r)}>{t(r.active ? "op.rec.pause" : "op.rec.resume")}</Button>
                          <IconButton label={t("common.edit")} onClick={() => setSheet({ kind: "recurring", task: r })}><PencilSimple size={20} aria-hidden /></IconButton>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card as="section" aria-labelledby="op-tasks" className="overflow-hidden">
              <h2 id="op-tasks" className="p-4 text-section text-ink">{t("op.tab.tasks")}</h2>
              {(tasks.data?.results ?? []).length === 0 ? (
                <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("op.task.emptyClient")}</p>
              ) : (
                <div className="border-t border-line"><TaskList tasks={tasks.data!.results} onChanged={refresh} showClient={false} /></div>
              )}
            </Card>

            <Card as="section" aria-labelledby="op-meetings" className="overflow-hidden">
              <div className="flex items-center justify-between gap-3 p-4">
                <div>
                  <h2 id="op-meetings" className="text-section text-ink">{t("op.meet.section")}</h2>
                  <p className="text-label font-normal text-ink-2">{t("op.cadence.every", { days: data.qa_cadence_days })}{data.next_qa_due ? ` · ${t("op.nextQa", { date: formatDate(data.next_qa_due) })}` : ""}</p>
                </div>
                {manage ? <Button variant="ghost" onClick={() => setSheet({ kind: "cadence" })}>{t("op.cadence.change")}</Button> : null}
              </div>
              {(meetings.data?.results ?? []).length === 0 ? (
                <p className="border-t border-line px-4 py-6 text-center text-label font-normal text-ink-2">{t("op.meet.empty")}</p>
              ) : (
                <ul className="divide-y divide-line border-t border-line">
                  {meetings.data!.results.map((m) => (
                    <li key={m.id} className="px-4 py-3">
                      <p className="text-body font-semibold text-ink">{formatDate(m.held_on)}</p>
                      <p className="whitespace-pre-line text-label font-normal text-ink-2">{m.notes}</p>
                      <p className="mt-0.5 text-caption text-ink-2">{m.logged_by_name}{m.next_date ? ` · ${t("op.meet.nextOn", { date: formatDate(m.next_date) })}` : ""}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <InsetList title={t("op.contact")}>
              <InsetRow label={t("clients.contact")}>{data.contact_person || empty}</InsetRow>
              <InsetRow label={t("op.phone")}>{data.phone ? <Ltr>{data.phone}</Ltr> : empty}</InsetRow>
              <InsetRow label={t("op.email")}>{data.email ? <Ltr>{data.email}</Ltr> : empty}</InsetRow>
              {data.activated_at ? <InsetRow label={t("op.activatedOn")}>{formatDateTime(data.activated_at)}</InsetRow> : null}
              {(data.handovers ?? []).length ? <InsetRow label={t("ho.title")}><span className="flex flex-wrap justify-end gap-2">{data.handovers!.map((h) => <Link key={h.id} href={`/handovers/${h.id}`} className="text-primary-strong hover:underline"><Ltr>{h.ref}</Ltr></Link>)}</span></InsetRow> : null}
              {(data.projects ?? []).length ? <InsetRow label={t("prj.title")}><span className="flex flex-wrap justify-end gap-2">{data.projects!.map((k) => <Link key={k.id} href="/projects" className="text-primary-strong hover:underline"><Ltr>{k.ref}</Ltr></Link>)}</span></InsetRow> : null}
            </InsetList>
          </div>
        }
      />
      {sheet?.kind === "meeting" ? <MeetingSheet client={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet?.kind === "cadence" ? <CadenceSheet client={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet?.kind === "recurring" ? <RecurringSheet client={data} task={sheet.task} onClose={() => setSheet(null)} onDone={refresh} /> : null}
    </>
  );
}
