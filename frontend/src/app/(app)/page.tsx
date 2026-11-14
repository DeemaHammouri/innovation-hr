"use client";

import { Buildings, Plus, UserPlus } from "@phosphor-icons/react";
import Link from "next/link";
import { MyWorkSection } from "@/components/home/MyWorkSection";
import { Avatar } from "@/components/ui/Avatar";
import { buttonClass } from "@/components/ui/Button";
import { Card, InsetList, InsetRow } from "@/components/ui/Card";
import { CountUp } from "@/components/ui/CountUp";
import { EmptyState, ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { PageHeader } from "@/components/ui/PageHeader";
import { type DashboardSummary, type SummaryClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-section text-ink">{children}</h2>
      {action}
    </div>
  );
}

function Time({ iso }: { iso: string }) {
  const { relativeTime, formatDateTime } = useI18n();
  return (
    <time dateTime={iso} title={formatDateTime(iso)} className="whitespace-nowrap text-label font-normal text-ink-2">
      {relativeTime(iso)}
    </time>
  );
}

function RecentClients({ rows }: { rows: SummaryClient[] }) {
  const { t, formatDate } = useI18n();
  if (rows.length === 0) {
    return (
      <EmptyState compact icon={<Buildings size={24} aria-hidden />} title={t("home.noClientsTitle")} description={t("home.noClientsText")} />
    );
  }
  return (
    <ul className="stagger divide-y divide-line">
      {rows.map((c) => (
        <li key={c.id}>
          <Link href={`/clients/${c.id}`} className="flex min-h-14 items-center gap-3 px-4 py-2.5 hover:bg-canvas">
            <Avatar name={c.company_name} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-body text-ink">{c.company_name}</span>
              <span className="block truncate text-label font-normal text-ink-2">{c.contact_person || t("home.noContact")}</span>
            </span>
            <span className="text-label font-normal text-ink-2">{formatDate(c.created_at)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function SignIns({ rows }: { rows: { key: string; name: string; timestamp: string }[] }) {
  const { t } = useI18n();
  if (rows.length === 0) return <p className="px-4 py-6 text-body text-ink-2">{t("home.noSignIns")}</p>;
  return (
    <ul className="stagger divide-y divide-line">
      {rows.map((r) => (
        <li key={r.key} className="flex min-h-14 items-center gap-3 px-4 py-2.5">
          <Avatar name={r.name} />
          <span className="min-w-0 flex-1 truncate text-body text-ink">{r.name}</span>
          <Time iso={r.timestamp} />
        </li>
      ))}
    </ul>
  );
}

function QuickActions({ users, clients }: { users: boolean; clients: boolean }) {
  const { t } = useI18n();
  return (
    <Card as="section" className="p-5">
      <SectionTitle>{t("home.quickActions")}</SectionTitle>
      <div className="flex flex-col gap-2">
        {users ? (
          <Link href="/users/new" className={buttonClass("primary", "w-full justify-start")}>
            <UserPlus size={20} aria-hidden />
            {t("users.add")}
          </Link>
        ) : null}
        {clients ? (
          <Link href="/clients/new" className={buttonClass(users ? "secondary" : "primary", "w-full justify-start")}>
            <Plus size={20} aria-hidden />
            {t("clients.add")}
          </Link>
        ) : null}
      </div>
    </Card>
  );
}

function Figure({ value, caption }: { value: number; caption: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[length:var(--text-large-title)] leading-none font-bold text-ink">
        <CountUp value={value} />
      </p>
      <p className="mt-2 text-label font-normal text-ink-2">{caption}</p>
    </div>
  );
}

function CeoHome({ s }: { s: NonNullable<DashboardSummary["ceo"]> }) {
  const { t, dept } = useI18n();
  const max = Math.max(1, ...s.users_by_department.map((d) => d.count));
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-6">
      <div className="space-y-4 lg:space-y-6">
        <Card as="section" className="p-5 md:p-6" aria-labelledby="overview">
          <h2 id="overview" className="mb-6 text-section text-ink">{t("home.overview")}</h2>
          <div className="grid grid-cols-3 gap-4">
            <Figure value={s.active_users} caption={t("home.activeUsers")} />
            <Figure value={s.pending_password_users} caption={t("home.pendingPasswords")} />
            <Figure value={s.total_clients} caption={t("home.totalClients")} />
          </div>
        </Card>

        <Card as="section" className="p-5 md:p-6" aria-labelledby="by-dept">
          <h2 id="by-dept" className="mb-4 text-section text-ink">{t("home.byDepartment")}</h2>
          <ul className="space-y-3.5">
            {s.users_by_department.map((d) => (
              <li key={d.department} className="grid grid-cols-[7rem_minmax(0,1fr)_2rem] items-center gap-3 sm:grid-cols-[9rem_minmax(0,1fr)_2rem]">
                <span className="truncate text-body text-ink">{dept(d.department)}</span>
                <span className="h-2 overflow-hidden rounded-full bg-canvas" aria-hidden>
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${(d.count / max) * 100}%` }} />
                </span>
                <span className="tnum text-end text-label text-ink">{d.count}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card as="section" aria-labelledby="recent-clients" className="overflow-hidden">
          <div className="p-5 pb-2 md:px-6 md:pt-6">
            <SectionTitle
              action={
                <Link href="/clients" className="text-label text-primary-strong hover:underline">
                  {t("home.viewAll")}
                </Link>
              }
            >
              <span id="recent-clients">{t("home.recentClients")}</span>
            </SectionTitle>
          </div>
          <RecentClients rows={s.recent_clients} />
        </Card>
      </div>

      <div className="space-y-4 lg:space-y-6">
        <QuickActions users clients />
        <Card as="section" aria-labelledby="recent-signins" className="overflow-hidden">
          <div className="p-5 pb-2">
            <SectionTitle>
              <span id="recent-signins">{t("home.recentSignIns")}</span>
            </SectionTitle>
          </div>
          <SignIns rows={s.recent_sign_ins.map((r, i) => ({ key: `${r.user_id}-${i}`, name: r.full_name, timestamp: r.timestamp }))} />
        </Card>
      </div>
    </div>
  );
}

function OperationHome({ s, mine }: { s: NonNullable<DashboardSummary["operation"]>; mine: DashboardSummary["my_sign_ins"] }) {
  const { t } = useI18n();
  const me = useAuth().user;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-6">
      <div className="space-y-4 lg:space-y-6">
        <Card as="section" className="p-5 md:p-6" aria-labelledby="clients-figures">
          <h2 id="clients-figures" className="mb-6 text-section text-ink">{t("home.clientsHeading")}</h2>
          <div className="grid grid-cols-2 gap-4">
            <Figure value={s.total_clients} caption={t("home.totalClients")} />
            <Figure value={s.clients_this_month} caption={t("home.addedThisMonth")} />
          </div>
        </Card>
        <Card as="section" aria-labelledby="recent-clients" className="overflow-hidden">
          <div className="p-5 pb-2 md:px-6 md:pt-6">
            <SectionTitle
              action={
                <Link href="/clients" className="text-label text-primary-strong hover:underline">
                  {t("home.viewAll")}
                </Link>
              }
            >
              <span id="recent-clients">{t("home.recentClients")}</span>
            </SectionTitle>
          </div>
          <RecentClients rows={s.recent_clients} />
        </Card>
      </div>
      <div className="space-y-4 lg:space-y-6">
        <QuickActions users={false} clients />
        <MySignIns rows={mine} name={me?.full_name ?? ""} />
      </div>
    </div>
  );
}

function MySignIns({ rows, name }: { rows: DashboardSummary["my_sign_ins"]; name: string }) {
  const { t } = useI18n();
  return (
    <Card as="section" aria-labelledby="my-signins" className="overflow-hidden">
      <div className="p-5 pb-2">
        <SectionTitle>
          <span id="my-signins">{t("home.yourSignIns")}</span>
        </SectionTitle>
      </div>
      <SignIns rows={rows.map((r, i) => ({ key: String(i), name, timestamp: r.timestamp }))} />
    </Card>
  );
}

/** Line illustration made of plain shapes: three modules waiting to be plugged in. */
function ModulesIllustration() {
  return (
    <svg width="144" height="104" viewBox="0 0 144 104" fill="none" aria-hidden className="text-primary">
      <rect x="8" y="48" width="56" height="48" rx="10" stroke="currentColor" strokeWidth="2" />
      <rect x="80" y="48" width="56" height="48" rx="10" stroke="currentColor" strokeWidth="2" />
      <rect x="44" y="8" width="56" height="48" rx="10" stroke="currentColor" strokeWidth="2" strokeDasharray="5 5" className="opacity-60" />
      <path d="M24 72h24M96 72h24M60 32h24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="opacity-60" />
      <circle cx="72" cy="32" r="3" fill="currentColor" />
    </svg>
  );
}

function MemberHome({ s }: { s: DashboardSummary }) {
  const { t, dept, role, formatDateTime } = useI18n();
  const { user } = useAuth();
  if (!user) return null;
  const last = s.my_sign_ins[0];
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-6">
      <div className="space-y-4 lg:space-y-6">
        <InsetList title={t("home.yourAccount")}>
          <InsetRow label={t("common.department")}>{dept(user.department_name)}</InsetRow>
          <InsetRow label={t("common.role")}>{role(user.role)}</InsetRow>
          <InsetRow label={t("profile.lastSignIn")}>{last ? formatDateTime(last.timestamp) : t("common.none")}</InsetRow>
        </InsetList>
        <Card>
          <EmptyState
            icon={<Buildings size={24} aria-hidden />}
            title={t("home.emptyTitle")}
            description={t("home.emptyText")}
            action={<ModulesIllustration />}
          />
        </Card>
      </div>
      <MySignIns rows={s.my_sign_ins} name={user.full_name} />
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-6" aria-busy="true">
      <div className="space-y-4 lg:space-y-6">
        <Skeleton className="h-44 rounded-card" />
        <Skeleton className="h-56 rounded-card" />
      </div>
      <div className="space-y-4 lg:space-y-6">
        <Skeleton className="h-32 rounded-card" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const { t, greeting, formatLongDate } = useI18n();
  const { data, error, loading, reload } = useFetch<DashboardSummary>("/dashboard/summary/");
  const showSkeleton = useDelayed(loading);
  if (!user) return null;
  const firstName = user.full_name.split(" ")[0];
  return (
    <>
      <PageHeader title={t("home.greeting", { greeting: greeting(), name: firstName })} description={formatLongDate(new Date())} />
      <MyWorkSection />
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        data.ceo ? (
          <CeoHome s={data.ceo} />
        ) : data.operation ? (
          <OperationHome s={data.operation} mine={data.my_sign_ins} />
        ) : (
          <MemberHome s={data} />
        )
      ) : showSkeleton ? (
        <HomeSkeleton />
      ) : null}
    </>
  );
}
