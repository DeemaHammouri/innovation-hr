"use client";

import { Target as TargetIcon } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type LeadsDashboard, type TargetProgress } from "@/lib/api";
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

/** One bar per day. The chart is drawn from the same numbers the table underneath shows, so it never disagrees with them. */
function Bars({ days, label }: { days: { date: string; count: number | null }[]; label: string }) {
  const { formatNumber, formatDate } = useI18n();
  const max = Math.max(1, ...days.map((d) => d.count ?? 0));
  return (
    <figure>
      <div className="flex h-36 items-end gap-0.5" role="img" aria-label={label}>
        {days.map((d) => (
          <div key={d.date} className="flex h-full min-w-0 flex-1 items-end" title={`${formatDate(d.date)}: ${formatNumber(d.count ?? 0)}`}>
            <div className={`w-full rounded-t-sm ${d.count === null ? "bg-line" : "bg-primary"}`} style={{ height: `${d.count === null ? 3 : Math.max(3, ((d.count ?? 0) / max) * 100)}%` }} />
          </div>
        ))}
      </div>
      <figcaption className="mt-2 flex justify-between text-caption text-ink-2">
        <span>{formatDate(days[0].date)}</span>
        <span>{formatDate(days[days.length - 1].date)}</span>
      </figcaption>
    </figure>
  );
}

function TargetSheet({ month, current, onClose, onDone }: { month: string; current: number; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [value, setValue] = useState(current ? String(current) : "");
  const action = useAction(["target", "month"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<TargetProgress>("/leads/target/", { method: "PUT", body: { month, target: value } }));
    if (saved) {
      toast.success(t("dash.targetSaved"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("dash.setTarget")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button type="submit" form="target-form" loading={action.saving}>{t("appt.save")}</Button></>}>
      <form id="target-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <Input name="target" label={t("dash.targetLabel")} hint={t("dash.targetHint")} type="number" inputMode="numeric" min={1} value={value} onChange={(e) => setValue(e.target.value)} error={action.errors.target} required />
      </form>
    </Sheet>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t, formatNumber } = useI18n();
  const [sheet, setSheet] = useState(false);
  const dash = useFetch<LeadsDashboard>(user ? "/leads/dashboard/" : null);
  const target = useFetch<TargetProgress>(user ? "/leads/target/" : null);
  if (!user) return null;
  if (!can(user, "lead.dashboard")) return <NoAccess />;
  const d = dash.data;
  const g = target.data;
  const pct = (n: number) => `${formatNumber(n)}%`;
  const month = g ? `${g.year}-${String(g.month).padStart(2, "0")}` : "";

  return (
    <>
      <PageHeader title={t("dash.title")} description={t("dash.description")} />
      {dash.error ? <ErrorState message={dash.error} onRetry={dash.reload} /> : !d ? (
        <div className="space-y-4" aria-busy="true"><Skeleton className="h-32 rounded-card" /><Skeleton className="h-48 rounded-card" /></div>
      ) : (
        <div className="space-y-4 md:space-y-6">
          {g ? (
            <Card as="section" className="p-5 md:p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-section text-ink">{t("dash.targetTitle")}</h2>
                  <p className="text-label font-normal text-ink-2">{g.set ? t("dash.targetSetBy", { name: g.set_by ?? "" }) : t("dash.targetNone")}</p>
                </div>
                {can(user, "lead.target_manage") ? <Button variant="secondary" icon={<TargetIcon size={20} aria-hidden />} onClick={() => setSheet(true)}>{t("dash.setTarget")}</Button> : null}
              </div>
              {g.set ? (
                <>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <span className="tnum text-title text-ink">{formatNumber(g.added)} / {formatNumber(g.target)}</span>
                    <StatusPill tone={g.on_track ? "success" : "warning"}>{t(g.on_track ? "dash.onTrack" : "dash.behind")}</StatusPill>
                  </div>
                  <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, g.percent)} aria-label={t("dash.targetTitle")}>
                    <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, g.percent)}%` }} />
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
                    {[
                      [t("dash.progress"), pct(g.percent)],
                      [t("dash.remaining"), formatNumber(g.remaining)],
                      [t("dash.daysElapsed"), `${formatNumber(g.days_elapsed)} / ${formatNumber(g.days_in_month)}`],
                      [t("dash.daysLeft"), formatNumber(g.days_left)],
                      [t("dash.expected"), formatNumber(g.expected_by_today)],
                    ].map(([k, v]) => (
                      <div key={k}><dt className="text-label font-normal text-ink-2">{k}</dt><dd className="tnum text-body font-semibold text-ink">{v}</dd></div>
                    ))}
                    {g.required_per_day !== null ? <div><dt className="text-label font-normal text-ink-2">{t("dash.requiredPerDay")}</dt><dd className="tnum text-body font-semibold text-ink">{formatNumber(g.required_per_day)}</dd></div> : null}
                  </dl>
                  <div className="mt-5"><Bars days={g.days} label={t("dash.perDayChart")} /></div>
                </>
              ) : null}
            </Card>
          ) : null}

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
      {sheet && g ? <TargetSheet month={month} current={g.target} onClose={() => setSheet(false)} onDone={() => { setSheet(false); target.reload(); }} /> : null}
    </>
  );
}
