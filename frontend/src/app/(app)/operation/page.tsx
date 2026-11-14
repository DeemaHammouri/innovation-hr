"use client";

import { ListChecks, MagnifyingGlass } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { ClientStatusPill } from "@/components/operation/opUi";
import { TaskList } from "@/components/operation/TaskList";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { SearchField, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { OpClient, Page, TaskInstance } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useDebounced, useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const ROLES = ["ceo", "commercial_head", "commercial_member", "operation_head", "operation_member"];
const SIZE = 25;
const KEYS = ["tab", "q", "status", "mine", "show", "page"] as const;

export default function OperationPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!ROLES.includes(user.role_key ?? "")) return <NoAccess />;
  return <OperationView isOp={user.role_key === "operation_head" || user.role_key === "operation_member"} />;
}

function OperationView({ isOp }: { isOp: boolean }) {
  const { t } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  const tab = params.tab === "tasks" ? "tasks" : "clients";
  return (
    <>
      <PageHeader title={t("op.title")} description={t("op.description")} />
      <Segmented
        label={t("op.tabs")}
        value={tab}
        onChange={(v) => setParams({ tab: v === "tasks" ? "tasks" : "", page: "" })}
        segments={[{ value: "clients", label: t("op.tab.clients") }, { value: "tasks", label: t("op.tab.tasks") }]}
        className="mb-5 w-full md:w-fit"
      />
      {tab === "clients" ? <ClientsTab params={params} setParams={setParams} /> : <TasksTab params={params} setParams={setParams} isOp={isOp} />}
    </>
  );
}

type Tabs = { params: Record<(typeof KEYS)[number], string>; setParams: (p: Partial<Record<(typeof KEYS)[number], string>>) => void };

function ClientsTab({ params, setParams }: Tabs) {
  const { t, formatDate, formatNumber } = useI18n();
  const [search, setSearch] = useState(params.q);
  const debounced = useDebounced(search);
  const page = Math.max(1, Number(params.page) || 1);
  const path = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(SIZE) });
    if (debounced.trim()) q.set("search", debounced.trim());
    if (params.status) q.set("status", params.status);
    return `/operations/clients/?${q}`;
  }, [debounced, params.status, page]);
  const { data, error, loading, reload } = useQuery<Page<OpClient>>(path);
  const showSkeleton = useDelayed(loading && !data);
  const active = !!(params.q || params.status);
  const clear = () => {
    setSearch("");
    setParams({ q: "", status: "", page: "" });
  };

  const body = error ? (
    <ErrorState message={error} onRetry={reload} />
  ) : !data ? (
    showSkeleton ? <RowsSkeleton /> : <div className="h-64" />
  ) : data.results.length === 0 ? (
    active ? (
      <EmptyState icon={<MagnifyingGlass size={24} aria-hidden />} title={t("op.noMatch")} description={t("lead.noMatchText")} action={<Button variant="secondary" onClick={clear}>{t("common.clearFilters")}</Button>} />
    ) : (
      <EmptyState icon={<ListChecks size={24} aria-hidden />} title={t("op.emptyTitle")} description={t("op.emptyText")} />
    )
  ) : (
    <div className={loading ? "opacity-70 transition-opacity" : ""}>
      <ul className="divide-y divide-line">
        {data.results.map((c) => (
          <li key={c.id}>
            <Link href={`/operation/${c.id}`} className="flex items-start gap-3 px-4 py-3.5 hover:bg-canvas/60">
              <Avatar name={c.company_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-ink">{c.company_name}</p>
                <p className="truncate text-label font-normal text-ink-2">
                  {t("op.checklist.progress", { done: formatNumber(c.required_done), total: formatNumber(c.required_total) })}
                  {c.next_qa_due ? ` · ${t("op.nextQa", { date: formatDate(c.next_qa_due) })}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <ClientStatusPill status={c.status} />
                  {c.overdue_tasks ? <StatusPill tone="danger">{t("op.overdueTasks", { count: c.overdue_tasks })}</StatusPill> : c.open_tasks ? <StatusPill tone="neutral" dot={false}>{t("op.openTasks", { count: c.open_tasks })}</StatusPill> : null}
                  {c.qa_overdue ? <StatusPill tone="warning">{t("op.qaOverdue")}</StatusPill> : null}
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
    </div>
  );

  return (
    <Card className="overflow-hidden">
      <div className="space-y-3 border-b border-line p-4">
        <SearchField label={t("op.search")} value={search} onChange={(v) => { setSearch(v); setParams({ q: v, page: "" }); }} placeholder={t("op.searchPlaceholder")} />
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-56">
            <Select name="filter-status" label={t("common.status")} value={params.status} onChange={(e) => setParams({ status: e.target.value, page: "" })} options={[{ value: "", label: t("lead.allStatuses") }, ...(["onboarding", "active", "inactive"] as const).map((s) => ({ value: s, label: t(`op.status.${s}`) }))]} />
          </div>
          {active ? <Button variant="ghost" onClick={clear}>{t("common.clearFilters")}</Button> : null}
        </div>
        {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("op.count", { count: formatNumber(data.count) })}</p> : null}
      </div>
      {body}
    </Card>
  );
}

function TasksTab({ params, setParams, isOp }: Tabs & { isOp: boolean }) {
  const { t, formatNumber } = useI18n();
  const show = params.show === "all" ? "all" : params.show === "done" ? "done" : "open";
  const page = Math.max(1, Number(params.page) || 1);
  const path = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(SIZE) });
    if (show === "open") q.set("status", "open");
    if (show === "done") q.set("status", "done,skipped");
    if (params.mine === "1") q.set("mine", "1");
    return `/operations/tasks/?${q}`;
  }, [show, params.mine, page]);
  const { data, error, loading, reload } = useQuery<Page<TaskInstance>>(path);
  const showSkeleton = useDelayed(loading && !data);

  return (
    <Card className="overflow-hidden">
      <div className="space-y-3 border-b border-line p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-56">
            <Select name="filter-show" label={t("op.task.show")} value={show} onChange={(e) => setParams({ show: e.target.value === "open" ? "" : e.target.value, page: "" })} options={[{ value: "open", label: t("op.task.showOpen") }, { value: "done", label: t("op.task.showDone") }, { value: "all", label: t("op.task.showAll") }]} />
          </div>
          {isOp ? (
            <label htmlFor="task-mine" className="flex h-11 cursor-pointer items-center gap-2.5 text-label text-ink md:h-10">
              <input id="task-mine" type="checkbox" checked={params.mine === "1"} onChange={(e) => setParams({ mine: e.target.checked ? "1" : "", page: "" })} className="size-4 accent-[var(--color-primary)]" />
              {t("op.task.onlyMine")}
            </label>
          ) : null}
        </div>
        {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("op.task.count", { count: formatNumber(data.count) })}</p> : null}
      </div>
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        showSkeleton ? <RowsSkeleton /> : <div className="h-48" />
      ) : data.results.length === 0 ? (
        <EmptyState icon={<ListChecks size={24} aria-hidden />} title={t("op.task.emptyTitle")} description={t("op.task.emptyText")} />
      ) : (
        <div className={loading ? "opacity-70 transition-opacity" : ""}>
          <TaskList tasks={data.results} onChanged={reload} />
          <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
        </div>
      )}
    </Card>
  );
}
