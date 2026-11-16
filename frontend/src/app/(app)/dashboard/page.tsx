"use client";

import Link from "next/link";
import { NoAccess } from "@/components/NoAccess";
import { Bars, Targets } from "@/components/leads/Targets";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type LeadsDashboard } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can, canAny } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

function Stat({ label, value, hint, href }: { label: string; value: string; hint?: string; href?: string }) {
  const body = (
    <Card className="h-full p-4">
      <p className="text-label font-normal text-ink-2">{label}</p>
      <p className="tnum mt-1 text-title text-ink">{value}</p>
      {hint ? <p className="mt-0.5 text-caption text-ink-2">{hint}</p> : null}
    </Card>
  );
  return href ? <Link href={href} className="block rounded-card focus-visible:outline-2">{body}</Link> : body;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t, formatNumber } = useI18n();
  const dash = useFetch<LeadsDashboard>(user ? "/leads/dashboard/" : null);
  if (!user) return null;
  if (!can(user, "lead.dashboard")) return <NoAccess />;
  const d = dash.data;
  const pct = (n: number) => `${formatNumber(n)}%`;

  return (
    <>
      <PageHeader title={t("dash.title")} description={t("dash.description")} />
      {dash.error ? <ErrorState message={dash.error} onRetry={dash.reload} /> : !d ? (
        <div className="space-y-4" aria-busy="true"><Skeleton className="h-32 rounded-card" /><Skeleton className="h-48 rounded-card" /></div>
      ) : (
        <div className="space-y-4 md:space-y-6">
          <Targets />

          <section aria-label={t("dash.title")} className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label={t("dash.total")} value={formatNumber(d.total)} />
            <Stat label={t("dash.addedToday")} value={formatNumber(d.added.today)} />
            <Stat label={t("dash.added7")} value={formatNumber(d.added.last_7_days)} />
            <Stat label={t("dash.addedMonth")} value={formatNumber(d.added.this_month)} />
            <Stat label={t("dash.contactRate")} value={pct(d.contact_rate)} hint={t("dash.contactRateHint")} />
            <Stat label={t("dash.acceptanceRate")} value={pct(d.acceptance_rate)} hint={t("dash.acceptanceRateHint")} />
            <Stat label={t("dash.dueToday")} value={formatNumber(d.follow_ups.due_today)} />
            <Stat label={t("dash.overdue")} value={formatNumber(d.follow_ups.overdue)} hint={t("dash.overdueHint")} href={d.follow_ups.overdue ? `${canAny(user, "lead.manage", "lead.work_assigned") ? "/pipeline" : "/leads"}?overdue=1` : undefined} />
          </section>

          <Card as="section" className="p-5 md:p-6">
            <h2 className="text-section text-ink">{t("dash.perDay")}</h2>
            <div className="mt-4"><Bars days={d.per_day} label={t("dash.perDay")} /></div>
          </Card>

          <div className="grid gap-4 md:grid-cols-3 md:gap-6">
            <Card as="section" className="p-5">
              <h2 className="text-section text-ink">{t("dash.byStatus")}</h2>
              <ul className="mt-3 space-y-2">
                {d.by_status.map((r) => (
                  <li key={r.status} className="flex items-center justify-between text-body"><span>{t(`lead.status.${r.status}`)}</span><span className="tnum font-semibold">{formatNumber(r.count)}</span></li>
                ))}
              </ul>
            </Card>
            <Card as="section" className="p-5">
              <h2 className="text-section text-ink">{t("dash.bySource")}</h2>
              <ul className="mt-3 space-y-2">
                {d.by_source.length === 0 ? <li className="text-label font-normal text-ink-2">{t("dash.none")}</li> : d.by_source.map((r) => (
                  <li key={r.source} className="flex items-center justify-between gap-3 text-body"><span className="truncate">{r.source || t("dash.noSource")}</span><span className="tnum font-semibold">{formatNumber(r.count)}</span></li>
                ))}
              </ul>
            </Card>
            <Card as="section" className="p-5">
              <h2 className="text-section text-ink">{t("dash.contributors")}</h2>
              <ol className="mt-3 space-y-2">
                {d.top_contributors.length === 0 ? <li className="text-label font-normal text-ink-2">{t("dash.none")}</li> : d.top_contributors.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 text-body"><span className="truncate">{r.name}</span><span className="tnum font-semibold">{formatNumber(r.count)}</span></li>
                ))}
              </ol>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
