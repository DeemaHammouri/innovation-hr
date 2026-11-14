"use client";

import { useParams } from "next/navigation";
import { LeadForm } from "@/components/leads/LeadForm";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import type { Lead } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function EditLeadPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const { data, error, loading, reload } = useFetch<Lead>(user ? `/leads/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  if (!user) return null;
  const back = { href: `/leads/${id}`, label: data?.company_name ?? t("lead.title") };
  if (error) return <><PageHeader title={t("lead.edit")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) return <><PageHeader title={t("lead.edit")} back={back} />{showSkeleton ? <Skeleton className="h-64 max-w-2xl rounded-card" /> : null}</>;
  if (!data.permissions.can_edit) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("lead.edit")} back={back} />
      <LeadForm editing={data} />
    </>
  );
}
