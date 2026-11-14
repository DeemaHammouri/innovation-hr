"use client";

import { CurrencyCircleDollar, MagnifyingGlass } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { useMoney } from "@/components/quotations/quoteUi";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { SearchField, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Page, PayOverviewRow } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useDebounced, useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const SIZE = 25;
const KEYS = ["q", "filter", "page"] as const;

export default function PaymentsPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role_key !== "ceo" && user.role_key !== "commercial_head") return <NoAccess />;
  return <Overview />;
}

function Overview() {
  const { t, formatDate, formatNumber } = useI18n();
  const money = useMoney();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const debounced = useDebounced(search);
  const page = Math.max(1, Number(params.page) || 1);
  const path = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(SIZE) });
    if (debounced.trim()) q.set("search", debounced.trim());
    if (params.filter) q.set("filter", params.filter);
    return `/payments/overview/?${q}`;
  }, [debounced, params.filter, page]);
  const { data, error, loading, reload } = useQuery<Page<PayOverviewRow>>(path);
  const showSkeleton = useDelayed(loading && !data);
  const active = !!(params.q || params.filter);
  const clear = () => {
    setSearch("");
    setParams({ q: "", filter: "", page: "" });
  };

  const body = error ? (
    <ErrorState message={error} onRetry={reload} />
  ) : !data ? (
    showSkeleton ? <RowsSkeleton /> : <div className="h-64" />
  ) : data.results.length === 0 ? (
    active ? (
      <EmptyState icon={<MagnifyingGlass size={24} aria-hidden />} title={t("pay.noMatch")} description={t("lead.noMatchText")} action={<Button variant="secondary" onClick={clear}>{t("common.clearFilters")}</Button>} />
    ) : (
      <EmptyState icon={<CurrencyCircleDollar size={24} aria-hidden />} title={t("pay.emptyTitle")} description={t("pay.emptyText")} />
    )
  ) : (
    <div className={loading ? "opacity-70 transition-opacity" : ""}>
      <ul className="divide-y divide-line">
        {data.results.map((r) => (
          <li key={r.client}>
            <Link href={`/payments/${r.client}`} className="flex items-start gap-3 px-4 py-3.5 hover:bg-canvas/60">
              <Avatar name={r.company_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-ink">{r.company_name}</p>
                <p className="text-label font-normal text-ink-2">
                  {t("pay.balanceOf", { balance: money(r.balance, r.currency), total: money(r.total, r.currency) })}
                  {r.next_due ? ` · ${t("pay.nextDue", { date: formatDate(r.next_due) })}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {r.overdue_count ? <StatusPill tone="danger">{t("pay.overdueCount", { count: formatNumber(r.overdue_count), amount: money(r.overdue_amount, r.currency) })}</StatusPill> : null}
                  {!r.overdue_count && Number(r.balance) === 0 ? <StatusPill tone="success">{t("pay.settled")}</StatusPill> : null}
                  {!r.overdue_count && Number(r.balance) > 0 ? <StatusPill tone="neutral" dot={false}>{t("pay.open")}</StatusPill> : null}
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
    <>
      <PageHeader title={t("pay.title")} description={t("pay.description")} />
      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <SearchField label={t("pay.search")} value={search} onChange={(v) => { setSearch(v); setParams({ q: v, page: "" }); }} placeholder={t("pay.searchPlaceholder")} />
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-56">
              <Select name="filter-pay" label={t("pay.show")} value={params.filter} onChange={(e) => setParams({ filter: e.target.value, page: "" })} options={[{ value: "", label: t("pay.filter.all") }, { value: "overdue", label: t("pay.filter.overdue") }, { value: "open", label: t("pay.filter.open") }, { value: "settled", label: t("pay.filter.settled") }]} />
            </div>
            {active ? <Button variant="ghost" onClick={clear}>{t("common.clearFilters")}</Button> : null}
          </div>
          {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("pay.count", { count: formatNumber(data.count) })}</p> : null}
        </div>
        {body}
      </Card>
    </>
  );
}
