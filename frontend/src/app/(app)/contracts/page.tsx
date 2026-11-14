"use client";

import { MagnifyingGlass, Signature } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CONTRACT_STATUSES, ContractStatusPill } from "@/components/contracts/contractUi";
import { NoAccess } from "@/components/NoAccess";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SearchField, Select } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Contract, Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useDebounced, useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const SIZE = 25;
const KEYS = ["q", "status", "page"] as const;

export default function ContractsPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!user.role_key || user.role_key === "marketing") return <NoAccess />;
  return <ContractsView />;
}

function ContractsView() {
  const { t, formatNumber, formatDate } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const debounced = useDebounced(search);
  const page = Math.max(1, Number(params.page) || 1);
  const path = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(SIZE) });
    if (debounced.trim()) q.set("search", debounced.trim());
    if (params.status) q.set("status", params.status);
    return `/contracts/?${q}`;
  }, [debounced, params.status, page]);
  const { data, error, loading, reload } = useQuery<Page<Contract>>(path);
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
      <EmptyState icon={<MagnifyingGlass size={24} aria-hidden />} title={t("ct.noMatch")} description={t("lead.noMatchText")} action={<Button variant="secondary" onClick={clear}>{t("common.clearFilters")}</Button>} />
    ) : (
      <EmptyState icon={<Signature size={24} aria-hidden />} title={t("ct.emptyTitle")} description={t("ct.emptyText")} />
    )
  ) : (
    <div className={loading ? "opacity-70 transition-opacity" : ""}>
      <ul className="divide-y divide-line">
        {data.results.map((c) => (
          <li key={c.id}>
            <Link href={`/contracts/${c.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-canvas/60">
              <Avatar name={c.lead_company} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-ink">{c.lead_company}</p>
                <p className="truncate text-label font-normal text-ink-2"><Ltr>{c.ref}</Ltr> · {c.assigned_to_name ?? c.requested_by_name} · {formatDate(c.created_at)}</p>
              </div>
              <ContractStatusPill status={c.status} />
            </Link>
          </li>
        ))}
      </ul>
      <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
    </div>
  );

  return (
    <>
      <PageHeader title={t("ct.title")} description={t("ct.description")} />
      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <SearchField label={t("ct.search")} value={search} onChange={(v) => { setSearch(v); setParams({ q: v, page: "" }); }} placeholder={t("qt.searchPlaceholder")} />
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-56">
              <Select name="filter-status" label={t("common.status")} value={params.status} onChange={(e) => setParams({ status: e.target.value, page: "" })} options={[{ value: "", label: t("lead.allStatuses") }, ...CONTRACT_STATUSES.map((s) => ({ value: s, label: t(`ct.status.${s}`) }))]} />
            </div>
            {active ? <Button variant="ghost" onClick={clear}>{t("common.clearFilters")}</Button> : null}
          </div>
          {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("ct.count", { count: formatNumber(data.count) })}</p> : null}
        </div>
        {body}
      </Card>
    </>
  );
}
