"use client";

import { FileCsv, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BatchesPanel } from "@/components/leads/BatchesPanel";
import { LeadsBrowser } from "@/components/leads/LeadsBrowser";
import { NoAccess } from "@/components/NoAccess";
import { buttonClass } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const ROLES = ["ceo", "marketing", "commercial_head", "commercial_member"];

export default function LeadsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const search = useSearchParams();
  if (!user) return null;
  if (!ROLES.includes(user.role_key ?? "")) return <NoAccess />;
  const marketing = user.role_key === "marketing";
  const canSeeBatches = marketing || user.role_key === "ceo";
  const tab = canSeeBatches && search.get("tab") === "imports" ? "imports" : "leads";

  const actions = marketing ? (
    <div className="flex flex-wrap gap-2">
      <Link href="/leads/import" className={buttonClass("secondary")}>
        <FileCsv size={20} aria-hidden />
        {t("lead.import")}
      </Link>
      <Link href="/leads/new" className={buttonClass("primary")}>
        <Plus size={20} aria-hidden />
        {t("lead.add")}
      </Link>
    </div>
  ) : null;

  return (
    <>
      <PageHeader title={t("lead.title")} description={t("lead.description")} action={actions} />
      {canSeeBatches ? (
        <Segmented
          label={t("lead.tabs")}
          mode="radiogroup"
          value={tab}
          onChange={(v) => {
            const next = new URLSearchParams(window.location.search);
            if (v === "imports") next.set("tab", "imports");
            else next.delete("tab");
            const qs = next.toString();
            window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}`);
          }}
          segments={[
            { value: "leads", label: t("lead.tab.leads") },
            { value: "imports", label: t("lead.tab.batches") },
          ]}
          className="mb-5 w-full md:w-fit"
        />
      ) : null}
      {tab === "leads" ? <LeadsBrowser board={false} action={actions} /> : <BatchesPanel canImport={marketing} />}
    </>
  );
}
