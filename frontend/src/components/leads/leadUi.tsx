"use client";

import { Check } from "@phosphor-icons/react";
import { StatusPill } from "@/components/ui/Card";
import type { Lead, LeadStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export const STATUSES: LeadStatus[] = ["new", "contacted", "waiting", "qualified", "rejected"];

const TONE: Record<LeadStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = {
  new: "neutral",
  contacted: "primary",
  waiting: "warning",
  qualified: "success",
  rejected: "danger",
};

export function LeadStatusPill({ status, archived }: { status: LeadStatus; archived?: boolean }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <StatusPill tone={TONE[status]}>{t(`lead.status.${status}`)}</StatusPill>
      {archived ? <StatusPill tone="neutral" dot={false}>{t("lead.archivedPill")}</StatusPill> : null}
    </span>
  );
}

/** The one chip a card or row needs: overdue follow-up (red), a follow-up date, or "needs first contact". */
export function FollowUpChip({ lead }: { lead: Pick<Lead, "status" | "next_follow_up" | "follow_up_overdue" | "first_contact_overdue"> }) {
  const { t, formatDate } = useI18n();
  if (lead.status === "waiting" && lead.next_follow_up) {
    return lead.follow_up_overdue ? (
      <StatusPill tone="danger">{t("lead.overdueFollowUp")} · {formatDate(lead.next_follow_up)}</StatusPill>
    ) : (
      <StatusPill tone="neutral" dot={false}>{t("lead.dueOn", { date: formatDate(lead.next_follow_up) })}</StatusPill>
    );
  }
  if (lead.status === "new" && lead.first_contact_overdue) return <StatusPill tone="warning">{t("lead.firstContactLate")}</StatusPill>;
  return null;
}

export function useReasonName() {
  const { lang } = useI18n();
  return (lead: Pick<Lead, "rejection_reason_en" | "rejection_reason_ar">) => (lang === "ar" ? lead.rejection_reason_ar : lead.rejection_reason_en) || "";
}

/** The next step a person can take. Used by the detail page (primary action) and the pipeline "Move to…" menu. */
export type Move = "assign" | "contacted" | "waiting" | "qualified" | "rejected";

export function movesFor(lead: Lead): Move[] {
  const p = lead.permissions;
  const out: Move[] = [];
  if (p.can_assign) out.push("assign");
  if (!p.can_log || lead.archived_at) return out;
  if (lead.status === "new") out.push("contacted", "waiting", "qualified", "rejected");
  else if (lead.status === "contacted") out.push("waiting", "qualified", "rejected");
  else if (lead.status === "waiting") out.push("waiting", "qualified", "rejected");
  return out;
}

const STEP_KEYS = ["new", "contacted", "decision"] as const;

/** Where the lead is: New → Contacted → Decision (Waiting, Qualified or Rejected). */
export function LeadStepper({ lead }: { lead: Lead }) {
  const { t } = useI18n();
  const at = lead.status === "new" ? 0 : lead.status === "contacted" ? 1 : 2;
  const decided = lead.status === "qualified" || lead.status === "rejected";
  const decisionLabel = lead.status === "new" || lead.status === "contacted" ? t("lead.step.decision") : t(`lead.status.${lead.status}`);
  return (
    <ol aria-label={t("lead.stepper")} className="flex items-center gap-1.5 sm:gap-2">
      {STEP_KEYS.map((key, i) => {
        const label = key === "decision" ? decisionLabel : t(`lead.step.${key}`);
        const done = i < at || (i === at && decided);
        const current = i === at && !decided;
        const danger = key === "decision" && lead.status === "rejected";
        return (
          <li key={key} className="flex min-w-0 flex-1 items-center gap-1.5 last:flex-none" aria-current={current ? "step" : undefined}>
            <span className="sr-only">{done ? t("lead.stepDone", { label }) : current ? t("lead.stepCurrent", { label }) : label}</span>
            <span
              aria-hidden
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption ${
                danger ? "bg-danger text-white" : done ? "bg-primary-strong text-white" : current ? "border-2 border-primary bg-surface text-primary-strong" : "border border-line bg-surface text-ink-3"
              }`}
            >
              {done && !danger ? <Check size={14} weight="bold" /> : i + 1}
            </span>
            <span aria-hidden className={`text-label ${current || done ? "text-ink" : "text-ink-3"}`}>{label}</span>
            {i < STEP_KEYS.length - 1 ? <span aria-hidden className={`h-px min-w-2 flex-1 ${i < at ? "bg-primary" : "bg-line"}`} /> : null}
          </li>
        );
      })}
    </ol>
  );
}
