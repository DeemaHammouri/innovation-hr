"use client";

import { DotsThreeVertical, Eye, LockKey, Pencil, Plus, SlidersHorizontal, UserMinus, Users as UsersIcon, X, MagnifyingGlass, UserCheck } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { useUserActions } from "@/components/users/UserActions";
import { Avatar } from "@/components/ui/Avatar";
import { Button, buttonClass, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { SearchField } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { PAGE_SIZE, Pagination } from "@/components/ui/Pagination";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Sheet } from "@/components/ui/Sheet";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { api, type Department, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useList } from "@/lib/useList";
import { useUrlParams } from "@/lib/useUrlParams";

export default function UsersPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (!user.permissions.manage_users) return <NoAccess />;
  return <UsersView me={user} />;
}

const KEYS = ["q", "dept", "role", "status", "page"] as const;

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
  all,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  all: string;
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1 block text-caption text-ink-2">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full rounded-control border border-line bg-surface px-3 text-body text-ink focus-visible:outline-offset-0 focus:border-primary md:h-10"
      >
        <option value="">{all}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function UsersView({ me }: { me: User }) {
  const router = useRouter();
  const { t, dept, role, formatNumber } = useI18n();
  const [params, setParams] = useUrlParams(KEYS);
  const [search, setSearch] = useState(params.q);
  const { data, error, loading, reload } = useList<User>("/users/", search);
  const showSkeleton = useDelayed(loading && !data);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [sheet, setSheet] = useState(false);
  const actions = useUserActions(reload);

  useEffect(() => {
    api<Department[]>("/departments/").then(setDepartments).catch(() => setDepartments([]));
  }, []);

  const changeSearch = (v: string) => {
    setSearch(v);
    setParams({ q: v, page: "" });
  };
  const setFilter = (patch: Partial<Record<(typeof KEYS)[number], string>>) => setParams({ ...patch, page: "" });

  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (u) =>
          (!params.dept || String(u.department) === params.dept) &&
          (!params.role || u.role === params.role) &&
          (!params.status || (params.status === "active" ? u.is_active : !u.is_active)),
      ),
    [data, params.dept, params.role, params.status],
  );

  const lastPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, Number(params.page) || 1), lastPage);
  const rows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const deptOptions = departments.map((d) => ({ value: String(d.id), label: dept(d.name) }));
  const roleOptions = [
    { value: "head", label: role("head") },
    { value: "member", label: role("member") },
  ];
  const statusOptions = [
    { value: "active", label: t("common.active") },
    { value: "inactive", label: t("common.inactive") },
  ];

  const chips = [
    params.dept ? { key: "dept", label: deptOptions.find((o) => o.value === params.dept)?.label ?? "" } : null,
    params.role ? { key: "role", label: roleOptions.find((o) => o.value === params.role)?.label ?? "" } : null,
    params.status ? { key: "status", label: statusOptions.find((o) => o.value === params.status)?.label ?? "" } : null,
  ].filter((c): c is { key: "dept" | "role" | "status"; label: string } => c !== null && c.label !== "");

  const filtersActive = chips.length > 0 || search.trim() !== "";
  const clearAll = () => {
    setSearch("");
    setParams({ q: "", dept: "", role: "", status: "", page: "" });
  };

  const filterFields = (idPrefix: string) => (
    <>
      <FilterSelect id={`${idPrefix}-dept`} label={t("common.department")} value={params.dept} onChange={(v) => setFilter({ dept: v })} options={deptOptions} all={t("users.allDepartments")} />
      <FilterSelect id={`${idPrefix}-role`} label={t("common.role")} value={params.role} onChange={(v) => setFilter({ role: v })} options={roleOptions} all={t("users.allRoles")} />
      <FilterSelect id={`${idPrefix}-status`} label={t("common.status")} value={params.status} onChange={(v) => setFilter({ status: v })} options={statusOptions} all={t("users.allStatuses")} />
    </>
  );

  function kebab(u: User) {
    return (
      <Menu
        label={t("users.actionsFor", { name: u.full_name })}
        trigger={({ open, ...props }) => (
          <IconButton label={t("users.actionsFor", { name: u.full_name })} {...props} className={open ? "bg-canvas text-ink" : ""}>
            <DotsThreeVertical size={20} weight="bold" aria-hidden />
          </IconButton>
        )}
      >
        {(close) => (
          <>
            <MenuItem icon={<Eye size={20} aria-hidden />} onSelect={() => { close(); router.push(`/users/${u.id}`); }}>
              {t("users.view")}
            </MenuItem>
            <MenuItem icon={<Pencil size={20} aria-hidden />} onSelect={() => { close(); router.push(`/users/${u.id}/edit`); }}>
              {t("users.edit")}
            </MenuItem>
            <MenuItem icon={<LockKey size={20} aria-hidden />} onSelect={() => { close(); actions.askReset(u); }}>
              {t("users.resetPassword")}
            </MenuItem>
            {u.is_active ? (
              u.id !== me.id ? (
                <MenuItem danger icon={<UserMinus size={20} aria-hidden />} onSelect={() => { close(); actions.askDeactivate(u); }}>
                  {t("users.deactivate")}
                </MenuItem>
              ) : null
            ) : (
              <MenuItem icon={<UserCheck size={20} aria-hidden />} onSelect={() => { close(); void actions.activate(u); }}>
                {t("users.activate")}
              </MenuItem>
            )}
          </>
        )}
      </Menu>
    );
  }

  const statusPills = (u: User) => (
    <span className="flex flex-wrap gap-1.5">
      <StatusPill tone={u.is_active ? "success" : "neutral"}>{u.is_active ? t("common.active") : t("common.inactive")}</StatusPill>
      {u.must_change_password ? <StatusPill tone="warning">{t("users.needsPassword")}</StatusPill> : null}
    </span>
  );

  const identity = (u: User) => (
    <div className="flex min-w-0 items-center gap-3">
      <Avatar name={u.full_name} />
      <div className="min-w-0">
        <p className="flex items-center gap-2">
          <Link href={`/users/${u.id}`} className="truncate text-body font-semibold text-ink hover:text-primary-strong hover:underline">
            {u.full_name}
          </Link>
          {u.id === me.id ? <StatusPill tone="primary" dot={false}>{t("users.you")}</StatusPill> : null}
        </p>
        <p className="truncate text-label font-normal text-ink-2">
          <Ltr>{u.email}</Ltr>
        </p>
      </div>
    </div>
  );

  const addButton = (
    <Link href="/users/new" className={buttonClass("primary")}>
      <Plus size={20} aria-hidden />
      {t("users.add")}
    </Link>
  );

  const body = error ? (
    <ErrorState message={error} onRetry={reload} />
  ) : showSkeleton || (loading && !data) ? (
    showSkeleton ? <RowsSkeleton /> : <div className="h-64" />
  ) : data && rows.length > 0 ? (
    <>
      {/* Tablet and desktop: a table. */}
      <div className="hidden md:block">
        <table className="w-full text-start text-body">
          <caption className="sr-only">{t("users.title")}</caption>
          <thead>
            <tr className="border-b border-line text-label text-ink-2">
              <th scope="col" className="w-[42%] px-4 py-3 text-start font-semibold">{t("users.employee")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.department")}</th>
              <th scope="col" className="hidden px-4 py-3 text-start font-semibold lg:table-cell">{t("common.role")}</th>
              <th scope="col" className="px-4 py-3 text-start font-semibold">{t("common.status")}</th>
              <th scope="col" className="w-14 px-4 py-3"><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody className="stagger divide-y divide-line">
            {rows.map((u) => (
              <tr key={u.id} className="hover:bg-canvas/60">
                <td className="max-w-0 px-4 py-3 align-middle">{identity(u)}</td>
                <td className="px-4 py-3 align-middle">
                  {dept(u.department_name)}
                  <span className="block text-label font-normal text-ink-2 lg:hidden">{role(u.role)}</span>
                </td>
                <td className="hidden px-4 py-3 align-middle lg:table-cell">{role(u.role)}</td>
                <td className="px-4 py-3 align-middle">{statusPills(u)}</td>
                <td className="px-2 py-2 text-end align-middle">{kebab(u)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Phones: the same people as cards. */}
      <ul className="stagger divide-y divide-line md:hidden">
        {rows.map((u) => (
          <li key={u.id} className="flex items-start gap-2 px-4 py-3.5">
            <div className="min-w-0 flex-1 space-y-2">
              {identity(u)}
              <p className="text-label font-normal text-ink-2">
                {dept(u.department_name)} · {role(u.role)}
              </p>
              {statusPills(u)}
            </div>
            {kebab(u)}
          </li>
        ))}
      </ul>
      <Pagination page={page} total={filtered.length} onPage={(p) => setParams({ page: p > 1 ? String(p) : "" })} />
    </>
  ) : data ? (
    filtersActive ? (
      <EmptyState
        icon={<MagnifyingGlass size={24} aria-hidden />}
        title={t("users.noMatch")}
        description={t("users.noMatchText")}
        action={<Button variant="secondary" onClick={clearAll}>{t("common.clearFilters")}</Button>}
      />
    ) : (
      <EmptyState icon={<UsersIcon size={24} aria-hidden />} title={t("users.emptyTitle")} description={t("users.emptyText")} action={addButton} />
    )
  ) : null;

  return (
    <>
      <PageHeader title={t("users.title")} description={t("users.description")} action={addButton} />

      <Card className="overflow-hidden">
        <div className="space-y-3 border-b border-line p-4">
          <div className="flex gap-2">
            <SearchField label={t("users.search")} value={search} onChange={changeSearch} placeholder={t("users.searchPlaceholder")} className="min-w-0 flex-1" />
            <Button variant="secondary" className="md:hidden" onClick={() => setSheet(true)} icon={<SlidersHorizontal size={20} aria-hidden />} aria-label={t("users.filters")}>
              {chips.length > 0 ? <span className="tnum">{formatNumber(chips.length)}</span> : null}
            </Button>
          </div>
          <div className="hidden grid-cols-3 gap-3 md:grid">{filterFields("f")}</div>
          {chips.length > 0 ? (
            <ul className="flex flex-wrap gap-2" aria-label={t("users.activeFilters")}>
              {chips.map((c) => (
                <li key={c.key}>
                  <button
                    type="button"
                    onClick={() => setFilter({ [c.key]: "" })}
                    className="inline-flex h-8 items-center gap-1.5 rounded-full border border-primary-line bg-primary-tint ps-3 pe-2 text-label text-primary-hover"
                  >
                    {c.label}
                    <X size={14} aria-hidden />
                    <span className="sr-only">{t("users.removeFilter")}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {data ? (
            <p role="status" className="tnum text-label font-normal text-ink-2">
              {t("users.count", { count: formatNumber(filtered.length) })}
            </p>
          ) : null}
        </div>
        {body}
      </Card>

      <Sheet
        open={sheet}
        title={t("users.filters")}
        onClose={() => setSheet(false)}
        footer={
          <>
            <Button variant="secondary" onClick={clearAll}>{t("common.clearFilters")}</Button>
            <Button onClick={() => setSheet(false)}>{t("users.showResults", { count: formatNumber(filtered.length) })}</Button>
          </>
        }
      >
        <div className="space-y-4">{filterFields("m")}</div>
      </Sheet>

      {actions.dialogs}
    </>
  );
}

