"use client";

import Link from "next/link";
import { NoAccess } from "@/components/NoAccess";
import { Card, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type TaskStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Counts = { open: number; in_progress: number; waiting: number; blocked: number; submitted: number; overdue: number };
type Monitoring = {
  today: string;
  totals: Counts & { unassigned: number };
  people: ({ id: number; name: string } & Counts)[];
  attention: { id: number; title: string; client: number; client_name: string; assignee_name: string | null; status: TaskStatus; due_date: string; overdue: boolean; escalation_level: number }[];
  escalations_open: number;
};
const KEYS = ["open", "in_progress", "waiting", "blocked", "submitted", "overdue"] as const;

/** Who has how much, and what is late, stuck, escalated or waiting for a review. For the Operation head and the CEO. */
export default function MonitoringPage() {
  const { user } = useAuth();
  const { t, formatNumber, formatDate } = useI18n();
  const allowed = !!user && can(user, "operation.monitor");
  const { data, error, reload } = useFetch<Monitoring>(allowed ? "/operations/monitoring/" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("mon.title")} description={t("mon.description")} back={{ href: "/operation", label: t("nav.operation") }} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <Skeleton className="h-48 max-w-3xl rounded-card" /> : (
        <div className="max-w-3xl space-y-5 md:space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {KEYS.map((k) => (
              <Card key={k} className="p-4">
                <p className="text-label font-normal text-ink-2">{t(`mon.k.${k}`)}</p>
                <p className={`tnum text-2xl font-semibold ${k === "overdue" && data.totals[k] > 0 ? "text-danger" : "text-ink"}`}>{formatNumber(data.totals[k])}</p>
              </Card>
            ))}
          </div>
          <Card as="section" className="overflow-hidden">
            <h2 className="px-4 pt-4 text-section text-ink">{t("mon.people")}</h2>
            {data.people.length === 0 ? <p className="p-4 text-body text-ink-2">{t("mon.noPeople")}</p> : (
              <ul className="divide-y divide-line">
                {data.people.map((p) => (
                  <li key={p.id} className="px-4 py-3">
                    <p className="text-body font-semibold text-ink">{p.name}</p>
                    <p className="text-label font-normal text-ink-2">{KEYS.map((k) => `${t(`mon.k.${k}`)}: ${formatNumber(p[k])}`).join(" · ")}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card as="section" className="overflow-hidden">
            <h2 className="px-4 pt-4 text-section text-ink">{t("mon.attention")}</h2>
            {data.attention.length === 0 ? <p className="p-4 text-body text-ink-2">{t("mon.nothing")}</p> : (
              <ul className="divide-y divide-line">
                {data.attention.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-body font-semibold text-ink">{a.title}</p>
                      <p className="truncate text-label font-normal text-ink-2"><Link href={`/operation/${a.client}`} className="text-primary-strong hover:underline">{a.client_name}</Link> · {a.assignee_name ?? t("op.rec.unassigned")} · <Ltr>{formatDate(a.due_date)}</Ltr></p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {a.overdue ? <StatusPill tone="danger">{t("op.task.overdue")}</StatusPill> : null}
                      {a.escalation_level > 0 ? <StatusPill tone="warning">{t("op.task.escalatedTo", { who: t(a.escalation_level > 1 ? "op.task.toCeo" : "op.task.toHead") })}</StatusPill> : null}
                      <StatusPill tone="neutral">{t(`op.task.status.${a.status}`)}</StatusPill>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
