"use client";

import { LeadForm } from "@/components/leads/LeadForm";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function NewLeadPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  if (!user) return null;
  if (user.role_key !== "marketing") return <NoAccess />;
  return (
    <>
      <PageHeader title={t("lead.add")} back={{ href: "/leads", label: t("lead.title") }} />
      <LeadForm editing={null} />
    </>
  );
}
