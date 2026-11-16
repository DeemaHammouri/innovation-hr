"use client";

import { CheckSquareOffset, DotsThreeVertical, Plus } from "@phosphor-icons/react";
import { useMemo, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { TaskDetailSheet, TaskFormSheet } from "@/components/tasks/TaskSheets";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type GeneralTask, type GeneralTaskCounts, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const SIZE = 25;
const KEYS = ["view", "show", "page", "open"] as const;
const TILES = ["open", "due_today", "overdue", "done", "done_late"] as const;
type Counters = { mine: GeneralTaskCounts; team: GeneralTaskCounts | null };

export default function TasksPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!can(user, "gtask.access")) return <NoAccess />;
  return <TasksView />;
}

function TasksView() {
  const { t, msg, formatDate, formatDateTime, formatNumber } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const gives = !!user && (can(user, "gtask.assign_any") || can(user, "gtask.assign_team"));
  const [params, setParams] = useUrlParams(KEYS);
  const view = gives && (params.view === "team" || params.view === "given") ? params.view : "mine";
  const show = params.show === "done" ? "done" : params.show === "all" ? "all" : "open";
  const page = Math.max(1, Number(params.page) || 1);
  const [form, setForm] = useState<{ task?: GeneralTask } | null>(null);
  const [detail, setDetail] = useState<GeneralTask | null>(null);
  const path = useMemo(() => {
    const q = new URLSearchParams({ view, page: String(page), page_size: String(SIZE) });
    if (show !== "all") q.set("status", show);
    return `/tasks/?${q}`;
  }, [view, show, page]);
  const { data, error, loading, reload } = useQuery<Page<GeneralTask>>(path);
  const counters = useQuery<Counters>("/tasks/counters/");
  const showSkeleton = useDelayed(loading && !data);
  const numbers = counters.data ? (view === "mine" ? counters.data.mine : counters.data.team ?? counters.data.mine) : null;
  const single = useQuery<GeneralTask>(/^\d+$/.test(params.open) ? `/tasks/${params.open}/` : null);
  const opened = single.data && String(single.data.id) === params.open ? single.data : undefined;
  const changed = () => {
    reload();
    counters.reload();
  };
  async function markDone(task: GeneralTask) {
    try {
      await api(`/tasks/${task.id}/done/`, { method: "POST", body: {} });
      toast.success(t("gt.doneSaved"));
      changed();
    } catch (e) {
      toast.error(msg(errorMessage(e)));
    }
  }
  const views = [{ value: "mine", label: t("gt.view.mine") }, ...(gives ? [{ value: "team", label: t("gt.view.team") }, { value: "given", label: t("gt.view.given") }] : [])];

  return (
    <>
      <PageHeader
        title={t("gt.title")}
        description={t("gt.description")}
        action={gives ? <Button icon={<Plus size={20} aria-hidden />} onClick={() => setForm({})}>{t("gt.new")}</Button> : null}
      />
      <section aria-label={t("gt.counters")} className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {TILES.map((k) => (
          <Card key={k} className="p-4">
            <p className="text-label font-normal text-ink-2">{t(`gt.k.${k}`)}</p>
            {numbers ? <p className={`tnum text-2xl font-semibold ${k === "overdue" && numbers[k] > 0 ? "text-danger" : "text-ink"}`}>{formatNumber(numbers[k])}</p> : <Skeleton className="mt-1 h-8 w-12" />}
          </Card>
        ))}
      </section>
      {views.length > 1 ? <Segmented label={t("gt.views")} value={view} onChange={(v) => setParams({ view: v === "mine" ? "" : v, page: "" })} segments={views} className="mb-5 w-full md:w-fit" /> : null}
      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <div className="w-full sm:w-56">
            <Select name="filter-show" label={t("gt.show")} value={show} onChange={(e) => setParams({ show: e.target.value === "open" ? "" : e.target.value, page: "" })} options={[{ value: "open", label: t("gt.show.open") }, { value: "done", label: t("gt.show.done") }, { value: "all", label: t("gt.show.all") }]} />
          </div>
          {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("gt.count", { count: formatNumber(data.count) })}</p> : null}
        </div>
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          showSkeleton ? <RowsSkeleton /> : <div className="h-48" />
        ) : data.results.length === 0 ? (
          <EmptyState icon={<CheckSquareOffset size={24} aria-hidden />} title={t("gt.emptyTitle")} description={t(gives ? "gt.emptyGives" : "gt.emptyText")} />
        ) : (
          <div className={loading ? "opacity-70 transition-opacity" : ""}>
            <ul className="divide-y divide-line">
              {data.results.map((task) => (
                <li key={task.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-body font-semibold text-ink">{task.title}</p>
                      <p className="text-label font-normal text-ink-2">
                        {view === "mine" ? t("gt.from", { who: task.assigned_by_name }) : t("gt.to", { who: task.assignee_name })} · {t("gt.due", { date: formatDate(task.deadline) })}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {task.overdue ? <StatusPill tone="danger">{t("gt.overdue")}</StatusPill> : null}
                      {task.status === "done" ? <StatusPill tone={task.done_late ? "warning" : "success"}>{t(task.done_late ? "gt.doneLate" : "gt.done")}</StatusPill> : <StatusPill tone="neutral">{t("gt.open")}</StatusPill>}
                      {task.can_done ? <Button onClick={() => markDone(task)}>{t("gt.markDone")}</Button> : null}
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
                            <MenuItem onSelect={() => { close(); setDetail(task); }}>{t("gt.details.open")}</MenuItem>
                            {task.can_edit ? <MenuItem onSelect={() => { close(); setForm({ task }); }}>{t("common.edit")}</MenuItem> : null}
                          </>
                        )}
                      </Menu>
                    </div>
                  </div>
                  {task.status === "done" && task.done_at ? <p className="mt-0.5 text-caption text-ink-2">{t("gt.doneOn", { date: formatDateTime(task.done_at) })}</p> : null}
                </li>
              ))}
            </ul>
            <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
          </div>
        )}
      </Card>
      {form ? <TaskFormSheet task={form.task} onClose={() => setForm(null)} onDone={() => { setForm(null); changed(); }} /> : null}
      {detail ? <TaskDetailSheet task={detail} onClose={() => { setDetail(null); changed(); }} /> : null}
      {opened && !detail ? <TaskDetailSheet task={opened} onClose={() => setParams({ open: "" })} /> : null}
    </>
  );
}
