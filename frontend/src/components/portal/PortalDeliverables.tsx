"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, downloadFile, errorMessage } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Deliverable = { id: number; title: string; published_at: string; acknowledged_at: string | null; filename: string };

/** Files Operation has finished for this client. The client opens them and confirms they received them. */
export function PortalDeliverables() {
  const { t, msg, formatDate, formatDateTime } = useI18n();
  const toast = useToast();
  const list = useFetch<Deliverable[]>("/portal/deliverables/");
  async function open(d: Deliverable) {
    try {
      await downloadFile(`/portal/deliverables/${d.id}/download/`, d.filename);
    } catch (e) {
      toast.error(msg(errorMessage(e)));
    }
  }
  async function confirm(d: Deliverable) {
    try {
      await api(`/portal/deliverables/${d.id}/acknowledge/`, { method: "POST", body: {} });
      toast.success(t("portal.files.confirmed"));
      list.reload();
    } catch (e) {
      toast.error(msg(errorMessage(e)));
    }
  }
  return (
    <section aria-labelledby="portal-files" className="space-y-3">
      <h2 id="portal-files" className="text-section text-ink">{t("portal.files")}</h2>
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <Skeleton className="h-24 rounded-card" /> : list.data.length === 0 ? (
        <Card className="p-5"><p className="text-body text-ink-2">{t("portal.files.none")}</p></Card>
      ) : list.data.map((d) => (
        <Card key={d.id} className="space-y-3 p-4 md:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-body font-semibold text-ink">{d.title}</p>
              <p className="text-label font-normal text-ink-2">{t("portal.files.sent", { date: formatDate(d.published_at) })}</p>
            </div>
            {d.acknowledged_at ? <StatusPill tone="success">{t("portal.files.received", { date: formatDateTime(d.acknowledged_at) })}</StatusPill> : <StatusPill tone="warning">{t("portal.files.new")}</StatusPill>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<DownloadSimple size={18} aria-hidden />} onClick={() => open(d)}>{t("portal.files.open")}</Button>
            {d.acknowledged_at ? null : <Button onClick={() => confirm(d)}>{t("portal.files.confirm")}</Button>}
          </div>
        </Card>
      ))}
    </section>
  );
}
