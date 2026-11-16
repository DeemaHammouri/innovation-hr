"use client";

import { Buildings, DotsThreeVertical, Eye, MagnifyingGlass, Pencil, Plus } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { Avatar } from "@/components/ui/Avatar";
import { Button, buttonClass, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { SearchField } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { PAGE_SIZE, Pagination } from "@/components/ui/Pagination";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Client } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useList } from "@/lib/useList";
import { useUrlParams } from "@/lib/useUrlParams";

export default function ClientsPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!can(user, "client.manage")) return <NoAccess />;
  return <ClientsView />;
}

const KEYS = ["q", "page"] as const;

function ClientsView() {
  const router = useRouter();
  const { t, formatDate, formatNumber } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const { data, error, loading, reload } = useList<Client>("/clients/", search);
  const showSkeleton = useDelayed(loading && !data);

  const all = data ?? [];
  const lastPage = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, Number(params.page) || 1), lastPage);
  const rows = all.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const changeSearch = (v: string) => {
    setSearch(v);
    setParams({ q: v, page: "" });
  };

  const dash = (v: string, ltr = false) => (v ? ltr ? <Ltr>{v}</Ltr> : v : <span className="text-ink-3">{"—"}</span>);

  function kebab(c: Client) {
    return (
      <Menu
        label={t("clients.actionsFor", { name: c.company_name })}
        trigger={({ open, ...props }) => (
          <IconButton label={t("clients.actionsFor", { name: c.company_name })} {...props} className={open ? "bg-canvas text-ink" : ""}>
            <DotsThreeVertical size={20} weight="bold" aria-hidden />
          </IconButton>
        )}
      >
        {(close) => (
          <>
            <MenuItem icon={<Eye size={20} aria-hidden />} onSelect={() => { close(); router.push(`/clients/${c.id}`); }}>
              {t("clients.view")}
            </MenuItem>
            <MenuItem icon={<Pencil size={20} aria-hidden />} onSelect={() => { close(); router.push(`/clients/${c.id}/edit`); }}>
              {t("clients.edit")}
            </MenuItem>
          </>
        )}
      </Menu>
    );
  }

  const addButton = (
    <Link href="/clients/new" className={buttonClass("primary")}>
      <Plus size={20} aria-hidden />
      {t("clients.add")}
    </Link>
  );

  const body = error ? (
    <ErrorState message={error} onRetry={reload} />
  ) : loading && !data ? (
    showSkeleton ? <RowsSkeleton /> : <div className="h-64" />
  ) : data && rows.length > 0 ? (
    <>
      <div className="hidden md:block">
        <table className="w-full text-start text-body">
          <caption className="sr-only">{t("clients.title")}</caption>
          <thead>
            <tr className="border-b border-line text-label text-ink-2">
              <th scope="col" className="w-[40%] px-4 py-3 text-start font-semibold">{t("clients.company")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("clients.contact")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.phone")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("clients.added")}</th>
              <th scope="col" className="w-14 px-4 py-3"><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody className="stagger divide-y divide-line">
            {rows.map((c) => (
              <tr key={c.id} className="hover:bg-canvas/60">
                <td className="max-w-0 px-4 py-3 align-middle">
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar name={c.company_name} />
                    <div className="min-w-0">
                      <Link href={`/clients/${c.id}`} className="block truncate font-semibold text-ink hover:text-primary-strong hover:underline">
                        {c.company_name}
                      </Link>
                      <p className="truncate text-label font-normal text-ink-2">{c.email ? <Ltr>{c.email}</Ltr> : null}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 align-middle">{dash(c.contact_person)}</td>
                <td className="tnum px-4 py-3 align-middle">{dash(c.phone, true)}</td>
                <td className="px-4 py-3 align-middle text-ink-2">{formatDate(c.created_at)}</td>
                <td className="px-2 py-2 text-end align-middle">{kebab(c)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="stagger divide-y divide-line md:hidden">
        {rows.map((c) => (
          <li key={c.id} className="flex items-start gap-2 px-4 py-3.5">
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <Avatar name={c.company_name} />
              <div className="min-w-0">
                <Link href={`/clients/${c.id}`} className="block truncate font-semibold text-ink">
                  {c.company_name}
                </Link>
                <p className="truncate text-label font-normal text-ink-2">{c.contact_person || t("home.noContact")}</p>
                {c.phone ? (
                  <p className="tnum text-label font-normal text-ink-2">
                    <Ltr>{c.phone}</Ltr>
                  </p>
                ) : null}
              </div>
            </div>
            {kebab(c)}
          </li>
        ))}
      </ul>
      <Pagination page={page} total={all.length} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} />
    </>
  ) : data ? (
    search.trim() ? (
      <EmptyState
        icon={<MagnifyingGlass size={24} aria-hidden />}
        title={t("clients.noMatch")}
        description={t("clients.noMatchText")}
        action={<Button variant="secondary" onClick={() => changeSearch("")}>{t("common.clearSearch")}</Button>}
      />
    ) : (
      <EmptyState icon={<Buildings size={24} aria-hidden />} title={t("clients.emptyTitle")} description={t("clients.emptyText")} action={addButton} />
    )
  ) : null;

  return (
    <>
      <PageHeader title={t("clients.title")} description={t("clients.description")} action={addButton} />
      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <SearchField label={t("clients.search")} value={search} onChange={changeSearch} placeholder={t("clients.searchPlaceholder")} />
          {data ? (
            <p role="status" className="tnum text-label font-normal text-ink-2">
              {t("clients.count", { count: formatNumber(all.length) })}
            </p>
          ) : null}
        </div>
        {body}
      </Card>
    </>
  );
}
