"use client";

import { NoAccess } from "@/components/NoAccess";
import { InsetList, InsetRow } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type PortalMe } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** The client's home. Everything here comes from /portal/me/, which only ever returns the signed-in client's own company. */
export default function PortalPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { data, error, reload } = useFetch<PortalMe>(user && can(user, "portal.access") ? "/portal/me/" : null);
  if (!user) return null;
  if (!can(user, "portal.access")) return <NoAccess />;
  const empty = <span className="text-ink-2">—</span>;
  return (
    <>
      <PageHeader title={t("portal.title")} description={t("portal.description")} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? (
        <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-48 rounded-card" /></div>
      ) : (
        <div className="max-w-2xl space-y-5 md:space-y-6">
          <InsetList title={t("portal.company")}>
            <InsetRow label={t("clients.company")}>{data.client.company_name}</InsetRow>
            <InsetRow label={t("clients.contactPerson")}>{data.client.contact_person || empty}</InsetRow>
            <InsetRow label={t("common.phone")} ltr={!!data.client.phone}>{data.client.phone || empty}</InsetRow>
            <InsetRow label={t("common.email")} ltr={!!data.client.email}>{data.client.email || empty}</InsetRow>
          </InsetList>
        </div>
      )}
    </>
  );
}
