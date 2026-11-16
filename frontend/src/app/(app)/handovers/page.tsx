"use client";

import Link from "next/link";
import { NoAccess } from "@/components/NoAccess";
import { handoverTone } from "@/components/handovers/handoverUi";
import { Card, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type Handover, type Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** Handovers from Commercial to Operation. Each person sees the ones their role is meant to see. */
export default function HandoversPage() {
  const { user } = useAuth();
  const { t, formatDate } = useI18n();
  const allowed = !!user && can(user, "handover.view");
  const list = useFetch<Page<Handover>>(allowed ? "/handovers/?page_size=100" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("ho.title")} description={t("ho.description")} />
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <Skeleton className="h-48 max-w-2xl rounded-card" /> : list.data.results.length === 0 ? (
        <Card className="max-w-2xl p-5"><p className="text-body text-ink-2">{t("ho.none")}</p></Card>
      ) : (
        <Card className="max-w-2xl overflow-hidden">
          <ul className="divide-y divide-line">
            {list.data.results.map((h) => (
              <li key={h.id}>
                <Link href={`/handovers/${h.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-canvas/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body font-semibold text-ink">{h.client_name}</p>
                    <p className="truncate text-label font-normal text-ink-2">{h.ref} · {h.prepared_by_name} · {formatDate(h.created_at)}</p>
                  </div>
                  <StatusPill tone={handoverTone(h.status)}>{t(`ho.status.${h.status}`)}</StatusPill>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
