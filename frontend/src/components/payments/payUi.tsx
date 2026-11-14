"use client";

import { StatusPill } from "@/components/ui/Card";
import type { InstalmentStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const TONE: Record<InstalmentStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = {
  expected: "neutral",
  partially_paid: "primary",
  paid: "success",
  overdue: "danger",
  cancelled: "neutral",
};

export function InstalmentPill({ status }: { status: InstalmentStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={TONE[status]}>{t(`pay.status.${status}`)}</StatusPill>;
}

/** One headline number with a label, for the four totals on a statement. */
export function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-label font-normal text-ink-2">{label}</p>
      <p dir="ltr" className={`tnum mt-1 text-section ${tone === "danger" ? "text-danger-ink" : "text-ink"} text-start`}>{value}</p>
    </div>
  );
}
