"use client";

import { DotsThreeVertical, Printer, Prohibit } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { QuotationEditor } from "@/components/quotations/QuotationEditor";
import { CancelSheet, ChangesSheet, OutcomeSheet } from "@/components/quotations/QuotationSheets";
import { QuoteStatusPill, QuoteStepper, useMoney } from "@/components/quotations/quoteUi";
import { VersionsPanel } from "@/components/quotations/VersionsPanel";
import { RecordTabs } from "@/components/records/RecordTabs";
import { Button, buttonClass, IconButton } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Menu, MenuItem } from "@/components/ui/Popover";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type Quotation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Sheet = "changes" | "outcome" | "cancel" | "sign" | null;

export default function QuotationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, formatDate, formatDateTime, lang } = useI18n();
  const toast = useToast();
  const money = useMoney();
  const { data, error, loading, reload } = useFetch<Quotation>(user ? `/quotations/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  const back = { href: "/quotations", label: t("qt.title") };
  if (error) return <><PageHeader title={t("qt.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>;
  if (!data) {
    return (
      <>
        <PageHeader title={t("qt.title")} back={back} />
        {showSkeleton ? <div className="max-w-2xl space-y-4" aria-busy="true"><Skeleton className="h-24 rounded-card" /><Skeleton className="h-48 rounded-card" /></div> : null}
      </>
    );
  }

  const p = data.permissions;
  const done = () => {
    setSheet(null);
    reload();
  };
  const versions = data.versions ?? [];
  const draft = versions.find((v) => v.is_draft);
  const shown = versions.find((v) => v.number === data.signed_version) ?? versions[versions.length - 1];

  async function post(path: string, message: string) {
    setBusy(true);
    try {
      await api(`/quotations/${data!.id}/${path}/`, { method: "POST" });
      toast.success(message);
      reload();
    } catch {
      toast.error(t("qt.saveFailed"));
    }
    setBusy(false);
  }

  let primary: React.ReactNode = null;
  let secondary: React.ReactNode = null;
  if (p.can_start) primary = <Button loading={busy} onClick={() => post("start", t("qt.started"))}>{t(data.status === "requested" ? "qt.next.start" : "qt.next.newVersion")}</Button>;
  else if (p.can_review) {
    primary = <Button onClick={() => setSheet("sign")}>{t("qt.next.sign")}</Button>;
    secondary = <Button variant="secondary" onClick={() => setSheet("changes")}>{t("qt.next.changes")}</Button>;
  } else if (p.can_send) primary = <Button loading={busy} onClick={() => post("send", t("qt.sentDone"))}>{t("qt.next.send")}</Button>;
  else if (p.can_outcome) primary = <Button onClick={() => setSheet("outcome")}>{t("qt.next.outcome")}</Button>;

  const hint =
    p.can_start ? t(data.status === "requested" ? "qt.hint.start" : "qt.hint.newVersion")
    : p.can_edit ? t("qt.hint.edit")
    : p.can_review ? t("qt.hint.review")
    : p.can_send ? t("qt.hint.send")
    : p.can_outcome ? t("qt.hint.outcome")
    : data.status === "in_review" ? t("qt.hint.inReview")
    : data.status === "in_preparation" || data.status === "requested" || data.status === "changes_requested" ? t("qt.hint.withHr")
    : "";

  const menu = p.can_cancel || p.can_print ? (
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
          {p.can_print ? (
            <Link href={`/quotations/${data.id}/print`} role="menuitem" onClick={close} className="flex h-11 w-full items-center gap-3 rounded-control px-3 text-start text-body text-ink hover:bg-canvas md:h-10">
              <Printer size={20} aria-hidden className="opacity-80" />
              {t("qt.print")}
            </Link>
          ) : null}
          {p.can_cancel ? <MenuItem danger icon={<Prohibit size={20} aria-hidden />} onSelect={() => { close(); setSheet("cancel"); }}>{t("qt.cancel.title")}</MenuItem> : null}
        </>
      )}
    </Menu>
  ) : null;
  const empty = <span className="text-ink-3">{"—"}</span>;
  const reasonName = lang === "ar" ? data.rejection_reason_ar : data.rejection_reason_en;

  return (
    <>
      <PageHeader
        back={back}
        title={`${data.ref} · ${data.lead_company}`}
        meta={<span className="flex flex-wrap items-center gap-2"><QuoteStatusPill status={data.status} />{data.follow_up_overdue ? <StatusPill tone="danger">{t("lead.overdueFollowUp")}</StatusPill> : null}</span>}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {p.can_print ? <Link href={`/quotations/${data.id}/print`} className={buttonClass("secondary")}><Printer size={20} aria-hidden />{t("qt.print")}</Link> : null}
            {secondary}
            {primary}
            {menu}
          </div>
        }
      />
      <div className="max-w-2xl">
        <Card className="mb-5 space-y-3 p-4 md:mb-6 md:p-5">
          <QuoteStepper quotation={data} />
          {hint ? <p className="text-label font-normal text-ink-2">{hint}</p> : null}
        </Card>
      </div>
      {p.can_edit && draft ? <QuotationEditor key={draft.id} quotation={data} version={draft} onChanged={reload} /> : null}
      <RecordTabs
        target={`quotation:${data.id}`}
        canAttach={p.can_start || p.can_edit || p.can_send || p.can_outcome}
        overview={
          <div className="space-y-5 md:space-y-6">
            {data.status === "changes_requested" && data.review_comment ? (
              <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
                <p className="text-body font-semibold">{t("qt.changesAsked")}</p>
                <p className="mt-1 whitespace-pre-line text-label font-normal">{data.review_comment}</p>
              </div>
            ) : null}
            {shown ? (
              <Card className="flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-label font-normal text-ink-2">{data.signed_version ? t("qt.signedTotal") : t("qt.latestTotal", { number: shown.number })}</p>
                  <p className="tnum text-title font-semibold text-ink" dir="ltr">{money(shown.total, shown.currency)}</p>
                </div>
                {shown.valid_until ? <p className="text-label font-normal text-ink-2">{t("qt.validUntilOn", { date: formatDate(shown.valid_until) })}</p> : null}
              </Card>
            ) : null}
            <InsetList title={t("qt.sectionClient")}>
              <InsetRow label={t("lead.company")}>{["ceo", "marketing", "commercial_head", "commercial_member"].includes(user?.role_key ?? "") ? <Link href={`/leads/${data.lead}`} className="text-primary-strong underline underline-offset-2">{data.lead_company}</Link> : data.lead_company}</InsetRow>
              <InsetRow label={t("lead.reference")}><Ltr>{data.lead_ref}</Ltr></InsetRow>
              <InsetRow label={t("lead.contactName")}>{data.lead_contact || empty}</InsetRow>
              <InsetRow label={t("lead.assignee")}>{data.assigned_to_name ?? empty}</InsetRow>
            </InsetList>
            <InsetList title={t("qt.sectionRequest")}>
              <InsetRow label={t("qt.requestedBy")}>{data.requested_by_name}</InsetRow>
              <InsetRow label={t("qt.requestedOn")}>{formatDateTime(data.created_at)}</InsetRow>
              <InsetRow label={t("qt.requestNote")}>{data.request_note ? <span className="whitespace-pre-line">{data.request_note}</span> : empty}</InsetRow>
              <InsetRow label={t("qt.preparedBy")}>{data.prepared_by_name ?? empty}</InsetRow>
            </InsetList>
            {data.signed_by_name ? (
              <InsetList title={t("qt.sectionSignature")}>
                <InsetRow label={t("qt.signedBy")}>{data.signed_by_name}</InsetRow>
                <InsetRow label={t("qt.signedOn")}>{data.signed_at ? formatDateTime(data.signed_at) : empty}</InsetRow>
                <InsetRow label={t("qt.signedVersionLabel")}>{t("qt.versionN", { number: data.signed_version ?? 0 })}</InsetRow>
                {data.sent_at ? <InsetRow label={t("qt.sentOn")}>{formatDateTime(data.sent_at)}</InsetRow> : null}
              </InsetList>
            ) : null}
            {["waiting", "confirmed", "rejected", "cancelled"].includes(data.status) ? (
              <InsetList title={t("qt.sectionOutcome")}>
                <InsetRow label={t("common.status")}><QuoteStatusPill status={data.status} /></InsetRow>
                {data.status === "waiting" ? <InsetRow label={t("lead.followUp")}>{data.next_follow_up ? formatDate(data.next_follow_up) : empty}</InsetRow> : null}
                {data.status === "rejected" ? <InsetRow label={t("lead.rejectionReason")}>{reasonName || empty}</InsetRow> : null}
                {data.status === "rejected" && data.rejection_note ? <InsetRow label={t("lead.rejectionNote")}><span className="whitespace-pre-line">{data.rejection_note}</span></InsetRow> : null}
                {data.status === "cancelled" ? <InsetRow label={t("qt.cancel.reason")}>{data.cancel_reason || empty}</InsetRow> : null}
                {data.outcome_at ? <InsetRow label={t("qt.decidedOn")}>{formatDateTime(data.outcome_at)}</InsetRow> : null}
              </InsetList>
            ) : null}
            <VersionsPanel quotation={data} />
          </div>
        }
      />
      {sheet === "sign" ? <SignSheet quotation={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "changes" ? <ChangesSheet quotation={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "outcome" ? <OutcomeSheet quotation={data} onClose={() => setSheet(null)} onDone={done} /> : null}
      {sheet === "cancel" ? <CancelSheet quotation={data} onClose={() => setSheet(null)} onDone={done} /> : null}
    </>
  );
}

/** Signing is the one step that cannot be taken back, so it asks once, naming exactly what is being signed. */
function SignSheet({ quotation, onClose, onDone }: { quotation: Quotation; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const money = useMoney();
  const action = useAction([]);
  const v = quotation.versions?.[quotation.versions.length - 1];
  async function sign() {
    const saved = await action.run(() => api<Quotation>(`/quotations/${quotation.id}/sign/`, { method: "POST" }));
    if (saved) {
      toast.success(t("qt.signedDone"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      alert
      onClose={onClose}
      title={t("qt.sign.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={action.saving} onClick={sign}>{t("qt.sign.save")}</Button>
        </>
      }
    >
      <FormError message={action.formError} />
      <p className="text-body text-ink-2">{t("qt.sign.text", { version: v?.number ?? 1, total: v ? money(v.total, v.currency) : "", name: quotation.lead_company })}</p>
      <p className="mt-3 text-label font-normal text-ink-2">{t("qt.sign.note")}</p>
    </Sheet>
  );
}
