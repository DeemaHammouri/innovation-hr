"use client";

import { StatusPill } from "@/components/ui/Card";
import type { ChecklistStatus, Frequency, OpClientStatus, RecurringTask } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const CLIENT_TONE: Record<OpClientStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = { onboarding: "warning", active: "success", inactive: "neutral" };
const ITEM_TONE: Record<ChecklistStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = { pending: "neutral", uploaded: "primary", verified: "success", expired: "danger", not_applicable: "neutral" };

export const FREQUENCIES: Frequency[] = ["daily", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom"];

export function ClientStatusPill({ status }: { status: OpClientStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={CLIENT_TONE[status]}>{t(`op.status.${status}`)}</StatusPill>;
}

export function ItemStatusPill({ status }: { status: ChecklistStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={ITEM_TONE[status]}>{t(`op.item.${status}`)}</StatusPill>;
}

/** "Every 2 weeks", "Every 45 days", ... in the active language. */
export function useFrequencyLabel() {
  const { t } = useI18n();
  return (r: Pick<RecurringTask, "frequency" | "interval_days">) => (r.frequency === "custom" ? t("op.freq.customN", { days: r.interval_days ?? 0 }) : t(`op.freq.${r.frequency}`));
}
