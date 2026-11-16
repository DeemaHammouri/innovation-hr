"use client";

import Link from "next/link";
import { useState } from "react";
import { StaffSheet } from "@/components/handovers/StaffSheet";
import { Button } from "@/components/ui/Button";
import { NoAccess } from "@/components/NoAccess";
import { Card, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type Page, type Project } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** One project per accepted handover. */
export default function ProjectsPage() {
  const { user } = useAuth();
  const { t, formatDate } = useI18n();
  const allowed = !!user && can(user, "project.view");
  const [staffing, setStaffing] = useState<Project | null>(null);
  const list = useFetch<Page<Project>>(allowed ? "/projects/?page_size=100" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("prj.title")} description={t("prj.description")} />
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <Skeleton className="h-48 max-w-2xl rounded-card" /> : list.data.results.length === 0 ? (
        <Card className="max-w-2xl p-5"><p className="text-body text-ink-2">{t("prj.none")}</p></Card>
      ) : (
        <Card className="max-w-2xl overflow-hidden">
          <ul className="divide-y divide-line">
            {list.data.results.map((p) => (
              <li key={p.id} className="px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <Link href={`/operation/${p.client}`} className="truncate text-body font-semibold text-primary-strong hover:underline">{p.name}</Link>
                    <p className="truncate text-label font-normal text-ink-2"><Ltr>{p.ref}</Ltr> · <Link href={`/handovers/${p.handover_id}`} className="hover:underline"><Ltr>{p.handover_ref}</Ltr></Link>{p.start_date ? ` · ${formatDate(p.start_date)}` : ""}</p>
                  </div>
                  <StatusPill tone={p.status === "active" ? "success" : p.status === "on_hold" ? "warning" : "neutral"}>{t(`prj.status.${p.status}`)}</StatusPill>
                </div>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-label font-normal text-ink-2">
                    {(() => {
                      const live = p.staff.filter((s) => !s.ended_at);
                      const main = live.find((s) => s.role === "primary");
                      const rest = live.filter((s) => s.role === "support").map((s) => s.name);
                      return main ? `${t("prj.primary")}: ${main.name}${rest.length ? ` · ${t("prj.support")}: ${rest.join(", ")}` : ""}` : t("prj.noPrimary");
                    })()}
                  </p>
                  {p.can_staff ? <Button variant="secondary" onClick={() => setStaffing(p)}>{t("prj.staff")}</Button> : null}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {staffing ? <StaffSheet project={list.data?.results.find((x) => x.id === staffing.id) ?? staffing} onClose={() => setStaffing(null)} onDone={list.reload} /> : null}
    </>
  );
}
