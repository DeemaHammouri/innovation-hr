"use client";

import { MagnifyingGlass, Receipt } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { FollowUpChip } from "@/components/leads/leadUi";
import { NoAccess } from "@/components/NoAccess";
import { QUOTE_STATUSES, QuoteStatusPill, useMoney } from "@/components/quotations/quoteUi";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { SearchField, Select } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Page, Quotation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useDebounced, useQuery } from "@/lib/useQuery";
import { useUrlParams } from "@/lib/useUrlParams";

const ROLES = ["ceo", "commercial_head", "commercial_member", "hr_head", "hr_member"];
const SIZE = 25;
const KEYS = ["q", "status", "overdue", "page"] as const;

export default function QuotationsPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!ROLES.includes(user.role_key ?? "")) return <NoAccess />;
  return <QuotationsView />;
}

function QuotationsView() {
  const { t, formatNumber, formatDate } = useI18n();
  const money = useMoney();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const debounced = useDebounced(search);
  const page = Math.max(1, Number(params.page) || 1);
  const path = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(SIZE) });
    if (debounced.trim()) q.set("search", debounced.trim());
    if (params.status) q.set("status", params.status);
    if (params.overdue === "1") q.set("overdue", "1");
    return `/quotations/?${q}`;
  }, [debounced, params.status, params.overdue, page]);
  const { data, error, loading, reload } = useQuery<Page<Quotation>>(path);
  const showSkeleton = useDelayed(loading && !data);
  const active = !!(params.q || params.status || params.overdue);
  const clear = () => {
    setSearch("");
    setParams({ q: "", status: "", overdue: "", page: "" });
  };

  const total = (q: Quotation) => (q.latest ? <span className="tnum" dir="ltr">{money(q.latest.total, q.latest.currency)}</span> : <span className="text-ink-3">{"—"}</span>);

  const body = error ? (
    <ErrorState message={error} onRetry={reload} />
  ) : !data ? (
    showSkeleton ? <RowsSkeleton /> : <div className="h-64" />
  ) : data.results.length === 0 ? (
    active ? (
      <EmptyState icon={<MagnifyingGlass size={24} aria-hidden />} title={t("qt.noMatch")} description={t("lead.noMatchText")} action={<Button variant="secondary" onClick={clear}>{t("common.clearFilters")}</Button>} />
    ) : (
      <EmptyState icon={<Receipt size={24} aria-hidden />} title={t("qt.emptyTitle")} description={t("qt.emptyText")} />
    )
  ) : (
    <div className={loading ? "opacity-70 transition-opacity" : ""}>
      <div className="hidden md:block">
        <table className="w-full text-start text-body">
          <caption className="sr-only">{t("qt.title")}</caption>
          <thead>
            <tr className="border-b border-line text-label text-ink-2">
              <th scope="col" className="w-[32%] px-4 py-3 text-start font-semibold">{t("qt.client")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.status")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("qt.total")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("qt.validUntil")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("qt.requestedOn")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.results.map((q) => (
              <tr key={q.id} className="hover:bg-canvas/60">
                <td className="max-w-0 px-4 py-3 align-middle">
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar name={q.lead_company} />
                    <div className="min-w-0">
                      <Link href={`/quotations/${q.id}`} className="block truncate font-semibold text-ink hover:text-primary-strong hover:underline">{q.lead_company}</Link>
                      <p className="truncate text-label font-normal text-ink-2"><Ltr>{q.ref}</Ltr> · {q.assigned_to_name ?? q.requested_by_name}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 align-middle">
                  <div className="flex flex-col items-start gap-1">
                    <QuoteStatusPill status={q.status} />
                    {q.follow_up_overdue ? <StatusPill tone="danger">{t("lead.overdueFollowUp")}</StatusPill> : q.status === "waiting" && q.next_follow_up ? <FollowUpChip lead={{ status: "waiting", next_follow_up: q.next_follow_up, follow_up_overdue: false, first_contact_overdue: false }} /> : null}
                  </div>
                </td>
                <td className="px-4 py-3 align-middle">{total(q)}</td>
                <td className="px-4 py-3 align-middle text-ink-2">{q.latest?.valid_until ? formatDate(q.latest.valid_until) : "—"}</td>
                <td className="px-4 py-3 align-middle text-ink-2">{formatDate(q.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line md:hidden">
        {data.results.map((q) => (
          <li key={q.id}>
            <Link href={`/quotations/${q.id}`} className="flex items-start gap-3 px-4 py-3.5">
              <Avatar name={q.lead_company} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-ink">{q.lead_company}</p>
                <p className="truncate text-label font-normal text-ink-2"><Ltr>{q.ref}</Ltr> · {q.assigned_to_name ?? q.requested_by_name}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <QuoteStatusPill status={q.status} />
                  {q.follow_up_overdue ? <StatusPill tone="danger">{t("lead.overdueFollowUp")}</StatusPill> : null}
                </div>
              </div>
              <span className="shrink-0 text-body font-semibold text-ink">{total(q)}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Pagination page={page} total={data.count} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} pageSize={SIZE} />
    </div>
  );

  return (
    <>
      <PageHeader title={t("qt.title")} description={t("qt.description")} />
      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <SearchField label={t("qt.search")} value={search} onChange={(v) => { setSearch(v); setParams({ q: v, page: "" }); }} placeholder={t("qt.searchPlaceholder")} />
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-full sm:w-56">
              <Select name="filter-status" label={t("common.status")} value={params.status} onChange={(e) => setParams({ status: e.target.value, page: "" })} options={[{ value: "", label: t("lead.allStatuses") }, ...QUOTE_STATUSES.map((s) => ({ value: s, label: t(`qt.status.${s}`) }))]} />
            </div>
            <label htmlFor="qt-overdue" className="flex h-11 cursor-pointer items-center gap-2.5 text-label text-ink md:h-10">
              <input id="qt-overdue" type="checkbox" checked={params.overdue === "1"} onChange={(e) => setParams({ overdue: e.target.checked ? "1" : "", page: "" })} className="size-4 accent-[var(--color-primary)]" />
              {t("lead.onlyOverdue")}
            </label>
            {active ? <Button variant="ghost" onClick={clear}>{t("common.clearFilters")}</Button> : null}
          </div>
          {data ? <p role="status" className="tnum text-label font-normal text-ink-2">{t("qt.count", { count: formatNumber(data.count) })}</p> : null}
        </div>
        {body}
      </Card>
    </>
  );
}
