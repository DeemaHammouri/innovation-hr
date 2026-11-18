"use client";

import { StatusPill } from "@/components/ui/Card";
import type { ChecklistStatus, DayRule, Frequency, OpClientStatus, RecurringTask, WeekendPolicy } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const CLIENT_TONE: Record<OpClientStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = { onboarding: "warning", active: "success", inactive: "neutral" };
const ITEM_TONE: Record<ChecklistStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = { pending: "neutral", uploaded: "primary", verified: "success", expired: "danger", not_applicable: "neutral" };

export const FREQUENCIES: Frequency[] = ["daily", "workdays", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom"];

export function ClientStatusPill({ status }: { status: OpClientStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={CLIENT_TONE[status]}>{t(`op.status.${status}`)}</StatusPill>;
}

export function ItemStatusPill({ status }: { status: ChecklistStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={ITEM_TONE[status]}>{t(`op.item.${status}`)}</StatusPill>;
}

/** Frequencies that step by months, the only ones a day of the month can be chosen for. */
export const MONTH_FREQUENCIES: Frequency[] = ["monthly", "quarterly", "semiannual", "yearly"];
export const DAY_RULES: DayRule[] = ["date", "first_workday", "last_workday", "nth_weekday"];
export const POLICIES: WeekendPolicy[] = ["next", "previous", "keep", "skip"];
export const NTH_VALUES = [1, 2, 3, 4, -1];
export const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]; // Monday to Sunday, as the server counts them

/** "Every 2 weeks", "Every 45 days", "Every month · Last working day", "Every month · 2nd Tuesday" ... in the active language. */
export function useFrequencyLabel() {
  const { t } = useI18n();
  return (r: Pick<RecurringTask, "frequency" | "interval_days"> & Partial<Pick<RecurringTask, "day_rule" | "nth" | "weekday">>) => {
    const base = r.frequency === "custom" ? t("op.freq.customN", { days: r.interval_days ?? 0 }) : t(`op.freq.${r.frequency}`);
    if (!r.day_rule || r.day_rule === "date") return base;
    if (r.day_rule === "nth_weekday") return `${base} · ${t(`op.nth.${r.nth === -1 ? "last" : r.nth}`)} ${t(`op.weekday.${r.weekday}`)}`;
    return `${base} · ${t(`op.dayrule.${r.day_rule}`)}`;
  };
}
