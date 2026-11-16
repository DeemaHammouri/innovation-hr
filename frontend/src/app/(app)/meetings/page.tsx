"use client";

import { Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { reportTone } from "@/components/meetings/reportUi";
import { WriteReportSheet } from "@/components/meetings/WriteReportSheet";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type MeetingReport, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can, canAny } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function MeetingReportsPage() {
  const { user } = useAuth();
  const { t, formatDate } = useI18n();
  const allowed = !!user && canAny(user, "meeting_report.write", "meeting_report.view_all");
  const reports = useFetch<Page<MeetingReport>>(allowed ? "/meeting-reports/?page_size=100" : null);
  const [writing, setWriting] = useState(false);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader
        title={t("mr.title")}
        description={t("mr.description")}
        action={can(user, "meeting_report.write") ? <Button icon={<Plus size={18} aria-hidden />} onClick={() => setWriting(true)}>{t("mr.write")}</Button> : undefined}
      />
      {reports.error ? <ErrorState message={reports.error} onRetry={reports.reload} /> : !reports.data ? <Skeleton className="h-48 max-w-2xl rounded-card" /> : reports.data.results.length === 0 ? (
        <Card className="max-w-2xl p-5"><p className="text-body text-ink-2">{t("mr.none")}</p></Card>
      ) : (
        <Card className="max-w-2xl overflow-hidden">
          <ul className="divide-y divide-line">
            {reports.data.results.map((r) => (
              <li key={r.id}>
                <Link href={`/meetings/${r.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-canvas/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body font-semibold text-ink">{r.lead_company}</p>
                    <p className="truncate text-label font-normal text-ink-2">{r.appointment_title} · {formatDate(r.held_on)} · {r.author_name}</p>
                  </div>
                  <StatusPill tone={reportTone(r.status)}>{t(`mr.status.${r.status}`)}</StatusPill>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {writing ? <WriteReportSheet existing={reports.data?.results ?? []} onClose={() => setWriting(false)} onDone={() => { setWriting(false); reports.reload(); }} /> : null}
    </>
  );
}
