"use client";

import { LeadsBrowser } from "@/components/leads/LeadsBrowser";
import { canAny } from "@/lib/can";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function PipelinePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  if (!user) return null;
  if (!canAny(user, "lead.manage", "lead.work_assigned")) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("lead.pipelineTitle")} description={t("lead.pipelineDescription")} />
      <LeadsBrowser board />
    </>
  );
}
