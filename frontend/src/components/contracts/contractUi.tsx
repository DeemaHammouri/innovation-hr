"use client";

import { Check } from "@phosphor-icons/react";
import { StatusPill } from "@/components/ui/Card";
import type { Contract, ContractStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export const CONTRACT_STATUSES: ContractStatus[] = ["requested", "drafting", "with_commercial", "confirmed", "sent", "ceo_review", "returned", "signed", "handed_over", "cancelled"];

const TONE: Record<ContractStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = {
  requested: "neutral",
  drafting: "primary",
  with_commercial: "primary",
  confirmed: "primary",
  sent: "primary",
  ceo_review: "warning",
  returned: "warning",
  signed: "success",
  handed_over: "success",
  cancelled: "neutral",
};

export function ContractStatusPill({ status }: { status: ContractStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={TONE[status]}>{t(`ct.status.${status}`)}</StatusPill>;
}

const STEPS = ["request", "draft", "commercial", "sent", "ceo", "signed", "handover"] as const;

function stepIndex(status: ContractStatus) {
  switch (status) {
    case "requested": return 0;
    case "drafting":
    case "returned": return 1;
    case "with_commercial":
    case "confirmed": return 2;
    case "sent": return 3;
    case "ceo_review": return 4;
    case "signed": return 5;
    default: return 6;
  }
}

/** Request → Draft → Commercial → Sent → CEO → Signed → Handover. Shown on every contract page. */
export function ContractStepper({ contract }: { contract: Pick<Contract, "status"> }) {
  const { t } = useI18n();
  const at = stepIndex(contract.status);
  const finished = contract.status === "handed_over";
  const cancelled = contract.status === "cancelled";
  return (
    <ol aria-label={t("ct.stepper")} className="flex items-center gap-1.5">
      {STEPS.map((key, i) => {
        const last = i === STEPS.length - 1;
        const label = t(`ct.step.${key}`);
        const done = i < at || (last && finished);
        const current = i === at && !finished && !cancelled;
        return (
          <li key={key} className="flex min-w-0 flex-1 items-center gap-1.5 last:flex-none" aria-current={current ? "step" : undefined}>
            <span className="sr-only">{done ? t("qt.stepDone", { label }) : current ? t("qt.stepCurrent", { label }) : label}</span>
            <span
              aria-hidden
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption ${
                cancelled ? "border border-line bg-surface text-ink-3" : done ? "bg-primary-strong text-white" : current ? "border-2 border-primary bg-surface text-primary-strong" : "border border-line bg-surface text-ink-3"
              }`}
            >
              {done && !cancelled ? <Check size={14} weight="bold" /> : i + 1}
            </span>
            <span aria-hidden className={`hidden text-label xl:inline ${current || done ? "text-ink" : "text-ink-3"}`}>{label}</span>
            {!last ? <span aria-hidden className={`h-px min-w-2 flex-1 ${i < at && !cancelled ? "bg-primary" : "bg-line"}`} /> : null}
          </li>
        );
      })}
    </ol>
  );
}
