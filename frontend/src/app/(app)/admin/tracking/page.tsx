"use client";

import Link from "next/link";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { Card, InsetList, InsetRow } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type FeedEntry, type Page, type Tracking } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const LINKS: Record<string, string> = { lead: "/leads/", quotation: "/quotations/", contract: "/contracts/", "meeting report": "/meetings/", client: "/clients/" };

/** Process tracking for the administration: what moved today, what is late, who is doing what, and the whole activity feed. */
export default function TrackingPage() {
  const { user } = useAuth();
  const { t, formatDate, formatDateTime } = useI18n();
  const allowed = !!user && can(user, "tracking.view");
  const { data, error, reload } = useFetch<Tracking>(allowed ? "/admin/tracking/" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  const none = <span className="text-ink-2">{t("track.none")}</span>;
  return (
    <>
      <PageHeader title={t("track.title")} description={t("track.description")} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? (
        <div className="max-w-3xl space-y-4" aria-busy="true"><Skeleton className="h-40 rounded-card" /><Skeleton className="h-40 rounded-card" /></div>
      ) : (
        <div className="max-w-3xl space-y-5 md:space-y-6">
          <InsetList title={t("track.pipeline")}>
            {Object.entries(data.pipeline.leads).map(([k, n]) => <InsetRow key={`l-${k}`} label={t("track.leadsIn", { status: t(`lead.status.${k}`) })}>{n}</InsetRow>)}
            {Object.entries(data.pipeline.clients).map(([k, n]) => <InsetRow key={`c-${k}`} label={t("track.clientsIn", { status: k === "undecided" ? t("track.undecided") : t(`client.decision.${k}`) })}>{n}</InsetRow>)}
          </InsetList>
          <Card as="section" aria-labelledby="late-q" className="p-4">
            <h2 id="late-q" className="text-section text-ink">{t("track.lateQuotations")}</h2>
            <p className="text-label font-normal text-ink-2">{t("track.thresholds", { hr: data.thresholds.hr, commercial: data.thresholds.commercial })}</p>
            {data.late_quotations.length === 0 ? <p className="mt-2 text-body">{none}</p> : (
              <ul className="mt-2 divide-y divide-line">
                {data.late_quotations.map((q) => (
                  <li key={`${q.id}-${q.stage}`} className="py-2.5">
                    <Link href={`/quotations/${q.id}`} className="text-body font-semibold text-primary-strong hover:underline"><Ltr>{q.ref}</Ltr> · {q.company}</Link>
                    <p className="text-label font-normal text-ink-2">{t(`track.stage.${q.stage}`)}{q.person ? ` · ${q.person}` : ""} · {t("track.lateBy", { minutes: q.minutes_late })}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card as="section" aria-labelledby="missed" className="p-4">
            <h2 id="missed" className="text-section text-ink">{t("track.missed")}</h2>
            {data.missed_appointments.length === 0 ? <p className="mt-2 text-body">{none}</p> : (
              <ul className="mt-2 divide-y divide-line">
                {data.missed_appointments.map((a) => (
                  <li key={a.id} className="py-2.5">
                    <p className="text-body font-semibold text-ink">{a.title}{a.lead ? ` · ${a.lead}` : ""}</p>
                    <p className="text-label font-normal text-ink-2">{a.owner} · {formatDateTime(a.starts_at)}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card as="section" aria-labelledby="overdue" className="p-4">
            <h2 id="overdue" className="text-section text-ink">{t("track.overdue")}</h2>
            {data.overdue_follow_ups.length === 0 ? <p className="mt-2 text-body">{none}</p> : (
              <ul className="mt-2 divide-y divide-line">
                {data.overdue_follow_ups.map((l) => (
                  <li key={l.id} className="py-2.5">
                    <Link href={`/leads/${l.id}`} className="text-body font-semibold text-primary-strong hover:underline"><Ltr>{l.ref}</Ltr> · {l.company}</Link>
                    <p className="text-label font-normal text-ink-2">{l.owner ?? "—"} · {formatDate(l.due)}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <InsetList title={t("track.team")}>
            {data.team.length === 0 ? <InsetRow label={t("track.none")}>—</InsetRow> : data.team.map((m) => <InsetRow key={m.id} label={m.name}>{t("track.teamCounts", { today: m.today, week: m.week })}</InsetRow>)}
          </InsetList>
          <Card as="section" aria-labelledby="today" className="p-4">
            <h2 id="today" className="text-section text-ink">{t("track.today")}</h2>
            {data.changed_today.length === 0 ? <p className="mt-2 text-body">{none}</p> : <FeedList items={data.changed_today} />}
          </Card>
          <Feed />
        </div>
      )}
    </>
  );
}

function FeedList({ items }: { items: FeedEntry[] }) {
  const { t, formatDateTime } = useI18n();
  return (
    <ul className="mt-2 divide-y divide-line">
      {items.map((e) => {
        const href = LINKS[e.kind] ? `${LINKS[e.kind]}${e.object_id}` : null;
        return (
          <li key={e.id} className="py-2.5">
            <p className="text-body text-ink">
              <span className="font-semibold">{e.actor_name ?? t("track.system")}</span> · {e.action.replace(/_/g, " ")}
              {e.to_value ? <> → <Ltr>{e.to_value}</Ltr></> : null}
              {href ? <> · <Link href={href} className="text-primary-strong hover:underline">{e.kind} #{e.object_id}</Link></> : null}
            </p>
            <p className="text-caption text-ink-2">{formatDateTime(e.created_at)}</p>
          </li>
        );
      })}
    </ul>
  );
}

/** The whole activity feed, filterable by employee and by action type. */
function Feed() {
  const { t } = useI18n();
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const filters = useFetch<{ people: { id: number; name: string }[]; actions: string[] }>("/admin/activity/filters/");
  const qs = new URLSearchParams({ page_size: "30", ...(actor ? { actor } : {}), ...(action ? { action } : {}) }).toString();
  const feed = useFetch<Page<FeedEntry>>(`/admin/activity/?${qs}`);
  return (
    <Card as="section" aria-labelledby="feed" className="p-4">
      <h2 id="feed" className="text-section text-ink">{t("track.feed")}</h2>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select name="feed-actor" label={t("track.employee")} value={actor} onChange={(e) => setActor(e.target.value)} options={[{ value: "", label: t("track.everyone") }, ...(filters.data?.people ?? []).map((p) => ({ value: String(p.id), label: p.name }))]} />
        <Select name="feed-action" label={t("track.actionType")} value={action} onChange={(e) => setAction(e.target.value)} options={[{ value: "", label: t("track.allActions") }, ...(filters.data?.actions ?? []).map((a) => ({ value: a, label: a.replace(/_/g, " ") }))]} />
      </div>
      {feed.error ? <ErrorState message={feed.error} onRetry={feed.reload} /> : !feed.data ? <Skeleton className="mt-3 h-32 rounded-card" /> : feed.data.results.length === 0 ? <p className="mt-3 text-body text-ink-2">{t("track.none")}</p> : <FeedList items={feed.data.results} />}
    </Card>
  );
}
