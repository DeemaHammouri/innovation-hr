"use client";

import { Archive, ArrowCounterClockwise, DotsThreeVertical, Pencil, UserSwitch } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArchiveSheet, AssignSheet, ContactSheet, ReopenSheet } from "@/components/leads/LeadSheets";
import { FollowUpChip, LeadStatusPill, LeadStepper, useReasonName } from "@/components/leads/leadUi";
import { RequestQuotationSheet, SkipQuotationSheet } from "@/components/quotations/QuotationSheets";
import { QuoteStatusPill } from "@/components/quotations/quoteUi";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Avatar } from "@/components/ui/Avatar";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Interaction, type Lead } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Sheet = "contact" | "outcome" | "assign" | "reopen" | "archive" | "quote" | "skip" | null;

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const { t, formatDateTime, formatDate } = useI18n();
  const toast = useToast();
  const reasonName = useReasonName();
  const { data, error, loading, reload } = useFetch<Lead>(user ? `/leads/${id}/` : null);
  const interactions = useFetch<Interaction[] | { results: Interaction[] }>(user ? `/leads/${id}/interactions/` : null);
  const showSkeleton = useDelayed(loading);
  const [sheet, setSheet] = useState<Sheet>(null);

  if (!user) return null;
  const commercial = (user.role_key ?? "").startsWith("commercial");
  const back = { href: commercial ? "/pipeline" : "/leads", label: t(commercial ? "lead.pipelineTitle" : "lead.title") };
  if (error) return <><PageHeader title={t("lead.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) {
    return (
      <>
        <PageHeader title={t("lead.title")} back={back} />
        {showSkeleton ? <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-28 rounded-card" /><Skeleton className="h-48 rounded-card" /></div> : null}
      </>
    );
  }

  const p = data.permissions;
  const archived = !!data.archived_at;
  const refresh = () => {
    setSheet(null);
    reload();
    interactions.reload();
  };
  const empty = <span className="text-ink-3">{"—"}</span>;

  // The one primary action: the next step only. Everything else lives in the menu.
  let primary: { label: string; text: string; run: () => void } | null = null;
  if (!archived) {
    if (p.can_assign && !data.assigned_to) primary = { label: t("lead.next.assign"), text: t("lead.nextText.assign"), run: () => setSheet("assign") };
    else if (p.can_log && data.status === "new") primary = { label: t("lead.next.contact"), text: t("lead.nextText.contact"), run: () => setSheet("contact") };
    else if (p.can_log && data.status === "contacted") primary = { label: t("lead.next.outcome"), text: t("lead.nextText.outcome"), run: () => setSheet("outcome") };
    else if (p.can_log && data.status === "waiting") primary = { label: t("lead.next.waiting"), text: t("lead.nextText.waiting"), run: () => setSheet("contact") };
    else if (p.can_request_quotation) primary = { label: t("qt.request.title"), text: t("qt.nextText.request"), run: () => setSheet("quote") };
    else if (p.can_reopen && data.status === "rejected") primary = { label: t("lead.next.reopen"), text: t("lead.nextText.rejected"), run: () => setSheet("reopen") };
  }
  const note = primary ? primary.text : data.status === "qualified" ? t("lead.nextText.qualified") : data.status === "rejected" ? t("lead.nextText.rejected") : data.status === "waiting" ? t("lead.nextText.waitingOwner") : "";

  const hasMenu = p.can_skip_quotation || p.can_edit || (p.can_assign && !!data.assigned_to) || p.can_archive || p.can_restore || (p.can_log && data.status === "waiting" && !archived);
  const menu = hasMenu ? (
    <Menu
      label={t("common.actions")}
      trigger={({ open, ...props }) => (
        <IconButton label={t("common.actions")} variant="ghost" {...props} className={`border border-line ${open ? "bg-canvas" : ""}`}>
          <DotsThreeVertical size={20} weight="bold" aria-hidden />
        </IconButton>
      )}
    >
      {(close) => (
        <>
          {p.can_edit ? (
            <Link href={`/leads/${data.id}/edit`} role="menuitem" className="flex h-11 w-full items-center gap-3 rounded-control px-3 text-start text-body text-ink hover:bg-canvas md:h-10" onClick={close}>
              <Pencil size={20} aria-hidden className="opacity-80" />
              {t("lead.edit")}
            </Link>
          ) : null}
          {p.can_skip_quotation ? <MenuItem onSelect={() => { close(); setSheet("skip"); }}>{t("qt.skip.title")}</MenuItem> : null}
          {p.can_assign && data.assigned_to ? <MenuItem icon={<UserSwitch size={20} aria-hidden />} onSelect={() => { close(); setSheet("assign"); }}>{t("lead.assign.reassign")}</MenuItem> : null}
          {p.can_log && data.status === "waiting" && !archived ? <MenuItem onSelect={() => { close(); setSheet("outcome"); }}>{t("lead.next.outcome")}</MenuItem> : null}
          {p.can_archive ? <MenuItem danger icon={<Archive size={20} aria-hidden />} onSelect={() => { close(); setSheet("archive"); }}>{t("lead.archive")}</MenuItem> : null}
          {p.can_restore ? (
            <MenuItem
              icon={<ArrowCounterClockwise size={20} aria-hidden />}
              onSelect={async () => {
                close();
                try {
                  await api(`/leads/${data.id}/restore/`, { method: "POST" });
                  toast.success(t("lead.restored"));
                  reload();
                } catch {
                  toast.error(t("lead.saveFailed"));
                }
              }}
            >
              {t("lead.restore")}
            </MenuItem>
          ) : null}
        </>
      )}
    </Menu>
  ) : null;

  const list = Array.isArray(interactions.data) ? interactions.data : (interactions.data?.results ?? []);
  const reason = reasonName(data);

  return (
    <>
      <PageHeader
        back={back}
        title={data.company_name}
        leading={<Avatar name={data.company_name} size="lg" />}
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <span className="tnum text-label font-medium text-ink-2"><Ltr>{data.ref}</Ltr></span>
            <LeadStatusPill status={data.status} archived={archived} />
            <FollowUpChip lead={data} />
          </span>
        }
        action={
          <div className="flex items-center gap-2">
            {primary ? <Button onClick={primary.run}>{primary.label}</Button> : null}
            {menu}
          </div>
        }
      />
      <div className="max-w-2xl">
        <Card className="mb-5 space-y-3 p-4 md:mb-6 md:p-5">
          <LeadStepper lead={data} />
          {note ? <p className="text-label font-normal text-ink-2">{note}</p> : null}
        </Card>
      </div>
      <RecordTabs
        target={`lead:${data.id}`}
        canAttach={p.can_log || p.can_edit}
        overview={
          <div className="space-y-5 md:space-y-6">
            {data.status === "rejected" ? (
              <InsetList title={t("lead.sectionRejected")}>
                <InsetRow label={t("lead.rejectionReason")}>{reason || empty}</InsetRow>
                <InsetRow label={t("lead.rejectionNote")}>{data.rejection_note ? <span className="whitespace-pre-line">{data.rejection_note}</span> : empty}</InsetRow>
                <InsetRow label={t("lead.rejectedAt")}>{data.rejected_at ? formatDateTime(data.rejected_at) : empty}</InsetRow>
              </InsetList>
            ) : null}
            {archived ? (
              <InsetList title={t("lead.archivedPill")}>
                <InsetRow label={t("lead.archiveReason")}>{data.archive_reason || empty}</InsetRow>
                <InsetRow label={t("lead.archivedOn")}>{formatDateTime(data.archived_at!)}</InsetRow>
              </InsetList>
            ) : null}
            <InsetList title={t("lead.sectionCompany")}>
              <InsetRow label={t("lead.company")}>{data.company_name}</InsetRow>
              <InsetRow label={t("lead.source")}>{data.source || empty}</InsetRow>
              <InsetRow label={t("lead.assignee")}>{data.assigned_to_name ?? <span className="text-ink-2">{t("lead.unassigned")}</span>}</InsetRow>
              {data.status === "waiting" ? <InsetRow label={t("lead.followUp")}>{data.next_follow_up ? formatDate(data.next_follow_up) : empty}</InsetRow> : null}
            </InsetList>
            <InsetList title={t("lead.sectionContact")}>
              <InsetRow label={t("lead.contactName")}>{data.contact_name || empty}</InsetRow>
              <InsetRow label={t("common.phone")} ltr={!!data.phone}>{data.phone || empty}</InsetRow>
              <InsetRow label={t("common.email")} ltr={!!data.email}>{data.email || empty}</InsetRow>
              <InsetRow label={t("lead.notes")}>{data.notes ? <span className="whitespace-pre-line">{data.notes}</span> : empty}</InsetRow>
            </InsetList>
            {data.quotation || data.skipped_quotation_at ? (
              <InsetList title={t("qt.title")}>
                {data.quotation ? (
                  <InsetRow label={data.quotation.ref}>
                    <span className="flex items-center justify-end gap-2">
                      <QuoteStatusPill status={data.quotation.status} />
                      <Link href={`/quotations/${data.quotation.id}`} className="text-primary-strong hover:underline">{t("qt.open")}</Link>
                    </span>
                  </InsetRow>
                ) : null}
                {data.skipped_quotation_at ? <InsetRow label={t("qt.skippedLabel")}>{formatDateTime(data.skipped_quotation_at)}</InsetRow> : null}
              </InsetList>
            ) : null}
            <Card as="section" aria-labelledby="interactions" className="overflow-hidden">
              <div className="flex items-center justify-between gap-3 p-4 pb-3">
                <h2 id="interactions" className="text-section text-ink">{t("lead.interactions")}</h2>
                {p.can_log && !archived && data.status !== "new" && data.status !== "qualified" && data.status !== "rejected" ? (
                  <Button variant="secondary" onClick={() => setSheet("contact")}>{t("lead.logContact")}</Button>
                ) : null}
              </div>
              {interactions.loading && !interactions.data ? (
                <div className="px-4 pb-4"><Skeleton className="h-14" /></div>
              ) : list.length === 0 ? (
                <div className="border-t border-line px-4 py-6 text-center">
                  <p className="text-body text-ink">{t("lead.noInteractions")}</p>
                  <p className="text-label font-normal text-ink-2">{t("lead.noInteractionsText")}</p>
                </div>
              ) : (
                <ul className="divide-y divide-line border-t border-line">
                  {list.map((i) => (
                    <li key={i.id} className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusPill tone="primary" dot={false}>{t(`lead.type.${i.type}`)}</StatusPill>
                        {i.outcome ? <StatusPill tone={i.outcome === "accepted" ? "success" : i.outcome === "rejected" ? "danger" : "warning"}>{t(`lead.outcome.${i.outcome}`)}</StatusPill> : null}
                        <span className="text-label font-normal text-ink-2">{formatDateTime(i.occurred_at)} · {i.created_by_name}</span>
                      </div>
                      {i.notes ? <p className="mt-1.5 whitespace-pre-line text-body text-ink">{i.notes}</p> : null}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <InsetList title={t("lead.sectionRecord")}>
              <InsetRow label={t("lead.createdBy")}>{data.created_by_name}</InsetRow>
              <InsetRow label={t("lead.createdAt")}>{formatDateTime(data.created_at)}</InsetRow>
              {data.batch_ref ? <InsetRow label={t("lead.batch")}><Ltr>{data.batch_ref}</Ltr></InsetRow> : null}
              {data.assigned_at ? <InsetRow label={t("lead.assignedAt")}>{formatDateTime(data.assigned_at)}</InsetRow> : null}
              {data.first_contacted_at ? <InsetRow label={t("lead.firstContacted")}>{formatDateTime(data.first_contacted_at)}</InsetRow> : null}
              {data.qualified_at ? <InsetRow label={t("lead.qualifiedAt")}>{formatDateTime(data.qualified_at)}</InsetRow> : null}
            </InsetList>
          </div>
        }
      />
      {sheet === "contact" ? <ContactSheet lead={data} mode="contact" initialOutcome={data.status === "waiting" ? "waiting" : ""} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet === "outcome" ? <ContactSheet lead={data} mode="outcome" onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet === "assign" ? <AssignSheet lead={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet === "reopen" ? <ReopenSheet lead={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet === "quote" ? <RequestQuotationSheet lead={data} onClose={() => setSheet(null)} onDone={(q) => { setSheet(null); router.push(`/quotations/${q.id}`); }} /> : null}
      {sheet === "skip" ? <SkipQuotationSheet lead={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
      {sheet === "archive" ? <ArchiveSheet lead={data} onClose={() => setSheet(null)} onDone={refresh} /> : null}
    </>
  );
}
