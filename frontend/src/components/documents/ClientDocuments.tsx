"use client";

import { DownloadSimple, FileText } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";
import { DownloadSheet } from "@/components/documents/DownloadSheet";
import { Card, StatusPill } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/Button";
import { Ltr } from "@/components/ui/Ltr";
import { ErrorState, Skeleton } from "@/components/ui/States";
import type { DocumentItem } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** Every quotation, contract and meeting report of a client or lead, with each version. The server only returns what this person may see. */
export function ClientDocuments({ lead }: { lead: number }) {
  const { t, formatDate } = useI18n();
  const { data, error, reload } = useFetch<{ items: DocumentItem[] }>(`/documents/?lead=${lead}`);
  const [open, setOpen] = useState<DocumentItem | null>(null);
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-32 rounded-card" />;
  if (data.items.length === 0) return <Card className="p-5"><p className="text-body text-ink-2">{t("docs.none")}</p></Card>;
  return (
    <Card as="section" aria-labelledby="client-docs" className="overflow-hidden">
      <h2 id="client-docs" className="px-4 pt-4 text-section text-ink">{t("docs.title")}</h2>
      <ul className="mt-2 divide-y divide-line">
        {data.items.map((d) => (
          <li key={`${d.kind}-${d.id}`} className="flex items-start gap-3 px-4 py-3">
            <FileText size={22} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 text-body font-semibold text-ink">
                <Link href={d.link} className="text-primary-strong hover:underline"><Ltr>{d.ref}</Ltr></Link>
                <StatusPill tone="neutral">{t(`docs.kind.${d.kind}`)}</StatusPill>
              </p>
              <p className="text-label font-normal text-ink-2">{d.status.replace(/_/g, " ")} · {formatDate(d.date)}</p>
              {d.versions.length > 1 ? (
                <ul className="mt-1 space-y-0.5 text-caption text-ink-2">
                  {d.versions.map((v) => <li key={v.number}>{t("qt.versionN", { number: v.number })} · {v.by ?? "—"} · {formatDate(v.date)}</li>)}
                </ul>
              ) : null}
            </div>
            <IconButton label={t("doc.menu")} onClick={() => setOpen(d)}><DownloadSimple size={20} aria-hidden /></IconButton>
          </li>
        ))}
      </ul>
      {open ? <DownloadSheet path={`/${open.download.replace(/^\//, "")}`} fileBase={open.ref.replace(/\//g, "-")} onClose={() => setOpen(null)} /> : null}
    </Card>
  );
}
