"use client";

import { Pencil } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { NoAccess } from "@/components/NoAccess";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Avatar } from "@/components/ui/Avatar";
import { Button, buttonClass } from "@/components/ui/Button";
import { Ltr } from "@/components/ui/Ltr";
import { useToast } from "@/components/ui/Toast";
import { InsetList, InsetRow } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { api, type Client } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { pushRecent } from "@/lib/recent";
import { useFetch } from "@/lib/useFetch";

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDateTime } = useI18n();
  const allowed = can(user, "client.manage");
  const { data, error, loading, reload } = useFetch<Client>(allowed ? `/clients/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  const toast = useToast();

  async function sendPortal() {
    try {
      const res = await api<{ portal_status: NonNullable<Client["portal_status"]> }>(`/clients/${id}/portal/`, { method: "POST" });
      if (res.portal_status === "sent") toast.success(t("clients.portalSent"));
      else toast.error(t(`clients.portal.${res.portal_status}`));
      reload();
    } catch {
      toast.error(t("lead.saveFailed"));
    }
  }

  useEffect(() => {
    if (user && data) {
      pushRecent(user.id, { kind: "client", id: data.id, title: data.company_name, subtitle: data.contact_person || data.email || data.phone, href: `/clients/${data.id}` });
    }
  }, [user, data]);

  if (!user) return null;
  if (!allowed) return <NoAccess />;
  const back = { href: "/clients", label: t("clients.title") };
  if (error) {
    return (
      <>
        <PageHeader title={t("clients.title")} back={back} />
        <ErrorState message={error} onRetry={reload} />
      </>
    );
  }
  if (!data) {
    return (
      <>
        <PageHeader title={t("clients.title")} back={back} />
        {showSkeleton ? (
          <div className="max-w-2xl space-y-4" aria-busy="true">
            <Skeleton className="h-48 rounded-card" />
            <Skeleton className="h-32 rounded-card" />
          </div>
        ) : null}
      </>
    );
  }

  const empty = <span className="text-ink-3">{"—"}</span>;
  return (
    <>
      <PageHeader
        back={back}
        title={data.company_name}
        leading={<Avatar name={data.company_name} size="lg" />}
        action={
          <Link href={`/clients/${data.id}/edit`} className={buttonClass("secondary")}>
            <Pencil size={20} aria-hidden />
            {t("clients.edit")}
          </Link>
        }
      />
      <RecordTabs
        target={`client:${data.id}`}
        canAttach={allowed}
        overview={
          <div className="space-y-5 md:space-y-6">
            <InsetList title={t("clients.sectionCompany")}>
              <InsetRow label={t("clients.company")}>{data.company_name}</InsetRow>
              <InsetRow label={t("clients.contactPerson")}>{data.contact_person || empty}</InsetRow>
              <InsetRow label={t("common.phone")} ltr={!!data.phone}>{data.phone || empty}</InsetRow>
              <InsetRow label={t("common.email")} ltr={!!data.email}>{data.email || empty}</InsetRow>
              <InsetRow label={t("clients.address")}>{data.address ? <span className="whitespace-pre-line">{data.address}</span> : empty}</InsetRow>
              {data.lead_ref ? <InsetRow label={t("clients.fromLead")}><Ltr>{data.lead_ref}</Ltr></InsetRow> : null}
              <InsetRow label={t("clients.portal")}>
                <span className="flex flex-wrap items-center gap-3">{data.portal_status ? t(`clients.portal.${data.portal_status}`) : empty}<Button variant="secondary" onClick={sendPortal}>{t("clients.portalResend")}</Button></span>
              </InsetRow>
              <InsetRow label={t("clients.notes")}>{data.notes ? <span className="whitespace-pre-line">{data.notes}</span> : empty}</InsetRow>
            </InsetList>
            <InsetList title={t("clients.sectionRecord")}>
              <InsetRow label={t("clients.createdBy")}>{data.created_by_name}</InsetRow>
              <InsetRow label={t("clients.createdAt")}>{formatDateTime(data.created_at)}</InsetRow>
            </InsetList>
          </div>
        }
      />
    </>
  );
}
