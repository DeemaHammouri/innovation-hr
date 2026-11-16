"use client";

import { DotsThreeVertical, Eye, FunnelSimple, Kanban, ListBullets, MagnifyingGlass, Megaphone, Pencil } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, SearchField } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { Pagination } from "@/components/ui/Pagination";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, ErrorState, RowsSkeleton, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import type { Assignee, BoardColumn, Lead, LeadStatus, Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useDebounced, useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";
import { moveForColumn, MoveMenu, useLeadMoves } from "./LeadMoves";
import { FollowUpChip, LeadStatusPill, STATUSES } from "./leadUi";

const PAGE_SIZE = 25;
const KEYS = ["q", "status", "assignee", "overdue", "archived", "page", "view", "batch"] as const;

/**
 * Leads as a list (everyone who can see leads) and, for the Commercial team, as a board.
 * Filters live in the address bar. Moving a lead by dragging and by the "Move to…" menu end in the same sheets.
 */
export function LeadsBrowser({ board, action }: { board: boolean; action?: React.ReactNode }) {
  const { user } = useAuth();
  const { t, formatNumber } = useI18n();
  const toast = useToast();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const debounced = useDebounced(search);
  const isHead = user?.role_key === "commercial_head";
  const isMember = user?.role_key === "commercial_member";
  // Phones start on the list: a board is wider than the screen. The choice is in the address bar once made.
  const [narrow] = useState(() => typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches);
  const view = board ? (params.view === "list" || (!params.view && narrow) ? "list" : "board") : "list";
  const assigneeFilter = params.assignee;

  const { data: people } = useQuery<Assignee[]>(isHead ? "/leads/assignees/" : null);

  const query = useMemo(() => {
    const q = new URLSearchParams();
    if (debounced.trim()) q.set("search", debounced.trim());
    if (view === "list" && params.status) q.set("status", params.status);
    if (assigneeFilter) q.set("assigned_to", assigneeFilter === "me" ? String(user?.id ?? "") : assigneeFilter);
    if (params.overdue === "1") q.set("overdue", "1");
    if (params.archived === "1") q.set("archived", "1");
    if (params.batch) q.set("batch", params.batch);
    return q;
  }, [debounced, params.status, assigneeFilter, params.overdue, params.archived, params.batch, view, user?.id]);

  const page = Math.max(1, Number(params.page) || 1);
  const listPath = view === "list" ? `/leads/?${new URLSearchParams([...query, ["page", String(page)], ["page_size", String(PAGE_SIZE)]])}` : null;
  const boardPath = view === "board" ? `/leads/board/?${query}` : null;
  const list = useQuery<Page<Lead>>(listPath);
  const boardData = useQuery<{ columns: BoardColumn[]; limit: number }>(boardPath);
  const reloadAll = () => {
    list.reload();
    boardData.reload();
  };
  const moves = useLeadMoves(reloadAll);
  const router = useRouter();

  const filtersActive = !!(params.q || params.status || params.assignee || params.overdue || params.archived || params.batch);
  const clear = () => {
    setSearch("");
    setParams({ q: "", status: "", assignee: "", overdue: "", archived: "", batch: "", page: "" });
  };
  const changeSearch = (v: string) => {
    setSearch(v);
    setParams({ q: v, page: "" });
  };
  const change = (patch: Partial<Record<(typeof KEYS)[number], string>>) => setParams({ ...patch, page: "" });

  const assigneeOptions = [
    { value: "", label: t("lead.allAssignees") },
    ...(isMember ? [] : [{ value: "me", label: t("lead.mine") }]),
    ...(isHead || user?.role_key === "ceo" ? [{ value: "none", label: t("lead.unassigned") }] : []),
    ...(people ?? []).filter((p) => p.id !== user?.id).map((p) => ({ value: String(p.id), label: p.full_name })),
  ];

  const filters = (
    <div className="space-y-3 border-b border-line p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <SearchField className="md:flex-1" label={t("lead.search")} value={search} onChange={changeSearch} placeholder={t("lead.searchPlaceholder")} />
        {board ? (
          <Segmented
            label={t("lead.view.label")}
            value={view}
            onChange={(v) => setParams({ view: v, page: "" })}
            segments={[
              { value: "board", label: <span className="inline-flex items-center gap-1.5"><Kanban size={16} aria-hidden />{t("lead.viewBoard")}</span> },
              { value: "list", label: <span className="inline-flex items-center gap-1.5"><ListBullets size={16} aria-hidden />{t("lead.viewList")}</span> },
            ]}
            className="w-full md:w-auto"
          />
        ) : null}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        {view === "list" ? (
          <div className="w-full sm:w-48">
            <Select name="filter-status" label={t("lead.filterStatus")} value={params.status} onChange={(e) => change({ status: e.target.value })} options={[{ value: "", label: t("lead.allStatuses") }, ...STATUSES.map((s) => ({ value: s, label: t(`lead.status.${s}`) }))]} />
          </div>
        ) : null}
        {!isMember ? (
          <div className="w-full sm:w-52">
            <Select name="filter-assignee" label={t("lead.filterAssignee")} value={assigneeFilter} onChange={(e) => change({ assignee: e.target.value })} options={assigneeOptions} />
          </div>
        ) : null}
        <Check id="filter-overdue" checked={params.overdue === "1"} onChange={(v) => change({ overdue: v ? "1" : "" })} label={t("lead.onlyOverdue")} />
        <Check id="filter-archived" checked={params.archived === "1"} onChange={(v) => change({ archived: v ? "1" : "" })} label={t("lead.showArchived")} />
        {filtersActive ? (
          <Button variant="ghost" onClick={clear} icon={<FunnelSimple size={18} aria-hidden />}>
            {t("common.clearFilters")}
          </Button>
        ) : null}
      </div>
    </div>
  );

  const countText = view === "list" && list.data ? (
    <p role="status" className="tnum border-b border-line px-4 py-2.5 text-label font-normal text-ink-2">{t("lead.count", { count: formatNumber(list.data.count) })}</p>
  ) : null;

  const empty = (
    filtersActive ? (
      <EmptyState icon={<MagnifyingGlass size={24} aria-hidden />} title={t("lead.noMatch")} description={t("lead.noMatchText")} action={<Button variant="secondary" onClick={clear}>{t("common.clearFilters")}</Button>} />
    ) : (
      <EmptyState
        icon={<Megaphone size={24} aria-hidden />}
        title={t(board || (user?.role_key ?? "").startsWith("commercial") ? "lead.emptyCommercialTitle" : "lead.emptyTitle")}
        description={t(board || (user?.role_key ?? "").startsWith("commercial") ? "lead.emptyCommercial" : "lead.emptyText")}
        action={action}
      />
    )
  );

  return (
    <>
      <Card className="overflow-hidden">
        {filters}
        {view === "list" ? (
          <>
            {countText}
            <ListBody state={list} empty={empty} page={page} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} moves={moves} onOpen={(l) => router.push(`/leads/${l.id}`)} />
          </>
        ) : (
          <BoardBody state={boardData} empty={empty} moves={moves} onBlocked={() => toast.error(t("lead.dropNotAllowed"))} />
        )}
      </Card>
      {moves.sheet}
    </>
  );
}

function Check({ id, checked, onChange, label }: { id: string; checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label htmlFor={id} className="flex h-11 cursor-pointer items-center gap-2.5 text-label text-ink md:h-10">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="size-4 accent-[var(--color-primary)]" />
      {label}
    </label>
  );
}

type Moves = ReturnType<typeof useLeadMoves>;

function ListBody({ state, empty, page, onPage, moves, onOpen }: { state: ReturnType<typeof useQuery<Page<Lead>>>; empty: React.ReactNode; page: number; onPage: (p: number) => void; moves: Moves; onOpen: (l: Lead) => void }) {
  const { t, formatDate } = useI18n();
  const router = useRouter();
  const showSkeleton = useDelayed(state.loading && !state.data);
  const dash = <span className="text-ink-3">{"—"}</span>;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data) return showSkeleton ? <RowsSkeleton /> : <div className="h-64" />;
  if (state.data.results.length === 0) return <>{empty}</>;
  const rows = state.data.results;

  const kebab = (l: Lead) => (
    <div className="flex items-center justify-end gap-1">
      <MoveMenu lead={l} onMove={(m) => moves.start(l, m)} compact />
      <Menu
        label={t("lead.actionsFor", { name: l.company_name })}
        trigger={({ open, ...props }) => (
          <IconButton label={t("lead.actionsFor", { name: l.company_name })} {...props} className={open ? "bg-canvas text-ink" : ""}>
            <DotsThreeVertical size={20} weight="bold" aria-hidden />
          </IconButton>
        )}
      >
        {(close) => (
          <>
            <MenuItem icon={<Eye size={20} aria-hidden />} onSelect={() => { close(); onOpen(l); }}>{t("lead.view")}</MenuItem>
            {l.permissions.can_edit ? (
              <MenuItem icon={<Pencil size={20} aria-hidden />} onSelect={() => { close(); router.push(`/leads/${l.id}/edit`); }}>{t("lead.edit")}</MenuItem>
            ) : null}
          </>
        )}
      </Menu>
    </div>
  );

  return (
    <div className={state.loading ? "opacity-70 transition-opacity" : ""}>
      <div className="hidden md:block">
        <table className="w-full text-start text-body">
          <caption className="sr-only">{t("lead.title")}</caption>
          <thead>
            <tr className="border-b border-line text-label text-ink-2">
              <th scope="col" className="w-[30%] px-4 py-3 text-start font-semibold">{t("lead.company")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.status")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("lead.assignee")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.phone")}</th>
              <th scope="col" className="hidden px-4 py-3 text-start font-semibold lg:table-cell">{t("lead.added")}</th>
              <th scope="col" className="px-4 py-3"><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((l) => (
              <tr key={l.id} className="hover:bg-canvas/60">
                <td className="max-w-0 px-4 py-3 align-middle">
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar name={l.company_name} />
                    <div className="min-w-0">
                      <Link href={`/leads/${l.id}`} className="block truncate font-semibold text-ink hover:text-primary-strong hover:underline">{l.company_name}</Link>
                      <p className="truncate text-label font-normal text-ink-2"><Ltr>{l.ref}</Ltr> · {l.contact_name || t("lead.noContact")}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 align-middle">
                  <div className="flex flex-col items-start gap-1">
                    <LeadStatusPill status={l.status} archived={!!l.archived_at} />
                    <FollowUpChip lead={l} />
                  </div>
                </td>
                <td className="px-4 py-3 align-middle">{l.assigned_to_name ?? <span className="text-ink-2">{t("lead.unassigned")}</span>}</td>
                <td className="tnum px-4 py-3 align-middle">{l.phone ? <Ltr>{l.phone}</Ltr> : dash}</td>
                <td className="hidden px-4 py-3 align-middle text-ink-2 lg:table-cell">{formatDate(l.created_at)}</td>
                <td className="px-2 py-2 align-middle">{kebab(l)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line md:hidden">
        {rows.map((l) => (
          <li key={l.id} className="px-4 py-3.5">
            <div className="flex items-start gap-3">
              <Avatar name={l.company_name} />
              <div className="min-w-0 flex-1">
                <Link href={`/leads/${l.id}`} className="block truncate font-semibold text-ink">{l.company_name}</Link>
                <p className="truncate text-label font-normal text-ink-2"><Ltr>{l.ref}</Ltr> · {l.contact_name || t("lead.noContact")}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <LeadStatusPill status={l.status} archived={!!l.archived_at} />
                  <FollowUpChip lead={l} />
                </div>
                <p className="mt-1.5 text-label font-normal text-ink-2">{l.assigned_to_name ?? t("lead.unassigned")}</p>
              </div>
            </div>
            <div className="mt-2.5 flex justify-end">
              <MoveMenu lead={l} onMove={(m) => moves.start(l, m)} />
            </div>
          </li>
        ))}
      </ul>
      <Pagination page={page} total={state.data.count} onPage={onPage} pageSize={PAGE_SIZE} />
    </div>
  );
}

function BoardBody({ state, empty, moves, onBlocked }: { state: ReturnType<typeof useQuery<{ columns: BoardColumn[]; limit: number }>>; empty: React.ReactNode; moves: Moves; onBlocked: () => void }) {
  const { t, formatNumber } = useI18n();
  const showSkeleton = useDelayed(state.loading && !state.data);
  const [dragging, setDragging] = useState<Lead | null>(null);
  const [over, setOver] = useState<string | null>(null);
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data) {
    return showSkeleton ? (
      <div className="flex gap-3 overflow-hidden p-4" aria-busy="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-64 w-72 shrink-0" />)}</div>
    ) : <div className="h-64" />;
  }
  const total = state.data.columns.reduce((n, c) => n + c.count, 0);
  if (total === 0) return <>{empty}</>;

  return (
    <div className={`flex snap-x snap-mandatory gap-3 overflow-x-auto p-4 ${state.loading ? "opacity-70 transition-opacity" : ""}`}>
      {state.data.columns.map((col) => {
        const target = dragging ? moveForColumn(dragging, col.status) : null;
        const highlight = over === col.status && target;
        return (
          <section
            key={col.status}
            aria-label={t("lead.board.column", { status: t(`lead.status.${col.status}`), count: formatNumber(col.count) })}
            onDragOver={(e) => { if (dragging) { e.preventDefault(); setOver(col.status); } }}
            onDragLeave={() => setOver((o) => (o === col.status ? null : o))}
            onDrop={(e) => {
              e.preventDefault();
              setOver(null);
              if (!dragging) return;
              if (target) moves.start(dragging, target);
              else if (dragging.status !== col.status) onBlocked();
              setDragging(null);
            }}
            className={`flex w-72 shrink-0 snap-start flex-col rounded-card border bg-canvas/60 ${highlight ? "border-primary bg-primary-tint/60" : "border-line"}`}
          >
            <header className="flex items-center justify-between gap-2 px-3.5 pt-3 pb-2">
              <LeadStatusPill status={col.status as LeadStatus} />
              <span className="tnum text-label text-ink-2">{formatNumber(col.count)}</span>
            </header>
            <ul className="flex flex-1 flex-col gap-2.5 p-2.5 pt-1">
              {col.results.length === 0 ? <li className="px-2 py-6 text-center text-label font-normal text-ink-2">{t("lead.board.empty")}</li> : null}
              {col.results.map((l) => (
                <li
                  key={l.id}
                  draggable={l.permissions.can_log || l.permissions.can_assign}
                  onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(l.id)); e.dataTransfer.effectAllowed = "move"; setDragging(l); }}
                  onDragEnd={() => { setDragging(null); setOver(null); }}
                  className={`rounded-control border border-line bg-surface p-3 shadow-card ${dragging?.id === l.id ? "opacity-50" : ""}`}
                >
                  <Link href={`/leads/${l.id}`} className="block truncate font-semibold text-ink hover:text-primary-strong">{l.company_name}</Link>
                  <p className="truncate text-label font-normal text-ink-2">{l.contact_name || t("lead.noContact")}</p>
                  <div className="mt-2 min-h-5"><FollowUpChip lead={l} /></div>
                  <div className="mt-2.5 flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2">
                      {l.assigned_to_name ? <Avatar name={l.assigned_to_name} size="sm" /> : null}
                      <span className="truncate text-caption text-ink-2">{l.assigned_to_name ?? t("lead.unassigned")}</span>
                    </span>
                    <MoveMenu lead={l} onMove={(m) => moves.start(l, m)} compact />
                  </div>
                </li>
              ))}
              {col.count > col.results.length ? (
                <li className="px-2 text-center text-caption text-ink-2">{t("lead.board.more", { shown: formatNumber(col.results.length), total: formatNumber(col.count) })}</li>
              ) : null}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
