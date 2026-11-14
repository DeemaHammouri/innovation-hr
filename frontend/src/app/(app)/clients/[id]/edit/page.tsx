"use client";

import { useParams } from "next/navigation";
import { ClientForm } from "@/components/clients/ClientForm";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import type { Client } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function EditClientPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const t = useT();
  const allowed = !!user?.permissions.manage_clients;
  const { data, error, loading, reload } = useFetch<Client>(allowed ? `/clients/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("clients.edit")} back={{ href: `/clients/${id}`, label: data?.company_name ?? t("clients.title") }} />
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <ClientForm editing={data} />
      ) : showSkeleton ? (
        <div className="max-w-2xl space-y-4" aria-busy="true">
          <Skeleton className="h-48 rounded-card" />
          <Skeleton className="h-48 rounded-card" />
        </div>
      ) : null}
    </>
  );
}
