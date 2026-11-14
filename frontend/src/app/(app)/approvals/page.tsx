"use client";

import { SealCheck } from "@phosphor-icons/react";
import Link from "next/link";
import { ContractStatusPill } from "@/components/contracts/contractUi";
import { NoAccess } from "@/components/NoAccess";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import type { Contract, Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useQuery } from "@/lib/useQuery";

/** The CEO's inbox: everything that is waiting for a signature. Today that is contracts; later phases add to it. */
export default function ApprovalsPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role_key !== "ceo") return <NoAccess />;
  return <Inbox />;
}

function Inbox() {
  const { t, formatDateTime } = useI18n();
  const { data, error, loading, reload } = useQuery<Page<Contract>>("/contracts/?status=ceo_review&ordering=created_at&page_size=100");
  const show = useDelayed(loading && !data);
  return (
    <>
      <PageHeader title={t("ap.title")} description={t("ap.description")} />
      <Card className="overflow-hidden">
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data ? (
          show ? <RowsSkeleton /> : <div className="h-48" />
        ) : data.results.length === 0 ? (
          <EmptyState icon={<SealCheck size={24} aria-hidden />} title={t("ap.emptyTitle")} description={t("ap.emptyText")} />
        ) : (
          <>
            <h2 className="border-b border-line px-4 py-3 text-section text-ink">{t("ap.contracts", { count: data.count })}</h2>
            <ul className="divide-y divide-line">
              {data.results.map((c) => (
                <li key={c.id}>
                  <Link href={`/contracts/${c.id}`} className="flex items-center gap-3 px-4 py-3.5 hover:bg-canvas/60">
                    <Avatar name={c.lead_company} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold text-ink">{c.lead_company}</p>
                      <p className="truncate text-label font-normal text-ink-2"><Ltr>{c.ref}</Ltr> · {c.submitted_to_ceo_at ? t("ap.submittedOn", { date: formatDateTime(c.submitted_to_ceo_at) }) : ""}</p>
                    </div>
                    <ContractStatusPill status={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </>
  );
}
