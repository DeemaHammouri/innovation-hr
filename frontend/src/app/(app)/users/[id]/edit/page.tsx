"use client";

import { useParams } from "next/navigation";
import { can } from "@/lib/can";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { UserForm } from "@/components/users/UserForm";
import type { User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function EditUserPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const t = useT();
  const allowed = can(user, "user.manage");
  const { data, error, loading, reload } = useFetch<User>(allowed ? `/users/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("users.edit")} back={{ href: `/users/${id}`, label: data?.full_name ?? t("users.title") }} />
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : data ? (
        <UserForm editing={data} me={user} />
      ) : showSkeleton ? (
        <div className="max-w-2xl space-y-4" aria-busy="true">
          <Skeleton className="h-48 rounded-card" />
          <Skeleton className="h-48 rounded-card" />
        </div>
      ) : null}
    </>
  );
}
