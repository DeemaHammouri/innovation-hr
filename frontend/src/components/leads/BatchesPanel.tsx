"use client";

import { ArrowUUpLeft, FileCsv } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { Pagination } from "@/components/ui/Pagination";
import { Sheet } from "@/components/ui/Sheet";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, type ImportBatch, type Page } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useQuery } from "@/lib/useQuery";

const SIZE = 25;

/** Every CSV import, newest first. Its owner can undo it while nobody has contacted its leads. */
export function BatchesPanel({ canImport }: { canImport: boolean }) {
  const { t, msg, formatDateTime, formatNumber } = useI18n();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useQuery<Page<ImportBatch>>(`/import-batches/?page=${page}&page_size=${SIZE}`);
  const showSkeleton = useDelayed(loading && !data);
  const [undoing, setUndoing] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function undo() {
    if (!undoing) return;
    setBusy(true);
    setProblem("");
    try {
      await api(`/import-batches/${undoing.id}/undo/`, { method: "POST" });
      toast.success(t("lead.batch.undoDone"));
      setUndoing(null);
      reload();
    } catch (err) {
      setProblem(errorMessage(err, "lead.saveFailed"));
    }
    setBusy(false);
  }

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return showSkeleton ? <RowsSkeleton /> : <div className="h-64" />;
  if (data.results.length === 0) {
    return (
      <EmptyState
        icon={<FileCsv size={24} aria-hidden />}
        title={t("lead.batchesEmptyTitle")}
        description={t("lead.batchesEmptyText")}
        action={canImport ? <Link href="/leads/import" className={buttonClass("primary")}>{t("lead.import")}</Link> : undefined}
      />
    );
  }

  return (
    <Card className="overflow-hidden">
      <ul className="divide-y divide-line">
        {data.results.map((b) => (
          <li key={b.id} className="flex flex-col gap-3 px-4 py-3.5 md:flex-row md:items-center">
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2">
                <span className="truncate font-semibold text-ink"><Ltr>{b.filename}</Ltr></span>
                <StatusPill tone={b.status === "active" ? "success" : "neutral"}>{t(`lead.batch.status.${b.status}`)}</StatusPill>
              </p>
              <p className="tnum text-label font-normal text-ink-2">
                <Ltr>{b.ref}</Ltr> · {t("lead.batch.counts", { imported: formatNumber(b.imported_count), total: formatNumber(b.total_rows) })} · {b.created_by_name} · {formatDateTime(b.created_at)}
              </p>
              {b.skipped_errors || b.skipped_duplicates ? (
                <p className="tnum text-label font-normal text-ink-2">{t("lead.batch.skipped", { errors: formatNumber(b.skipped_errors), duplicates: formatNumber(b.skipped_duplicates) })}</p>
              ) : null}
              {b.status === "active" && b.contacted_count > 0 ? <p className="text-label font-normal text-ink-2">{t("lead.batch.undoBlocked")}</p> : null}
            </div>
            <div className="flex gap-2">
              <Link href={`/leads?batch=${b.id}`} className={buttonClass("secondary")}>{t("lead.batch.viewLeads")}</Link>
              {b.can_undo ? (
                <Button variant="secondary" icon={<ArrowUUpLeft size={18} aria-hidden />} onClick={() => setUndoing(b)}>{t("lead.batch.undo")}</Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <Pagination page={page} total={data.count} onPage={setPage} pageSize={SIZE} />
      {undoing ? (
        <Sheet
          open
          alert
          title={t("lead.batch.undoTitle")}
          onClose={() => setUndoing(null)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setUndoing(null)}>{t("common.cancel")}</Button>
              <Button variant="danger" loading={busy} onClick={undo}>{t("lead.batch.undo")}</Button>
            </>
          }
        >
          {problem ? <p role="alert" className="mb-3 rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">{msg(problem)}</p> : null}
          <p className="text-body text-ink-2">{t("lead.batch.undoText", { count: formatNumber(undoing.imported_count), file: undoing.filename })}</p>
        </Sheet>
      ) : null}
    </Card>
  );
}
