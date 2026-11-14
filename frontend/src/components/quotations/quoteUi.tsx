"use client";

import { Check } from "@phosphor-icons/react";
import { StatusPill } from "@/components/ui/Card";
import type { Quotation, QuotationStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export const QUOTE_STATUSES: QuotationStatus[] = ["requested", "in_preparation", "in_review", "changes_requested", "signed", "sent", "waiting", "confirmed", "rejected", "cancelled"];

const TONE: Record<QuotationStatus, "neutral" | "primary" | "warning" | "success" | "danger"> = {
  requested: "neutral",
  in_preparation: "primary",
  in_review: "primary",
  changes_requested: "warning",
  signed: "success",
  sent: "primary",
  waiting: "warning",
  confirmed: "success",
  rejected: "danger",
  cancelled: "neutral",
};

export function QuoteStatusPill({ status }: { status: QuotationStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={TONE[status]}>{t(`qt.status.${status}`)}</StatusPill>;
}

/** Money in the active language's number style, with the currency code of the quotation. */
export function useMoney() {
  const { lang } = useI18n();
  const locale = lang === "ar" ? "ar-u-nu-latn" : "en-US";
  return (amount: string | number, currency = "JOD") => {
    const n = Number(amount);
    try {
      return new Intl.NumberFormat(locale, { style: "currency", currency, currencyDisplay: "code", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number.isFinite(n) ? n : 0).replace(/ /g, " ");
    } catch {
      return `${n.toFixed(2)} ${currency}`;
    }
  };
}

const STEPS = ["request", "prepare", "review", "send", "decision"] as const;

function stepIndex(status: QuotationStatus) {
  switch (status) {
    case "requested": return 0;
    case "in_preparation":
    case "changes_requested": return 1;
    case "in_review": return 2;
    case "signed": return 3;
    default: return 4;
  }
}

/** Request → Prepare → Review and sign → Send → Decision. */
export function QuoteStepper({ quotation }: { quotation: Pick<Quotation, "status"> }) {
  const { t } = useI18n();
  const at = stepIndex(quotation.status);
  const finished = ["confirmed", "rejected", "cancelled"].includes(quotation.status);
  const bad = quotation.status === "rejected" || quotation.status === "cancelled";
  return (
    <ol aria-label={t("qt.stepper")} className="flex items-center gap-1.5 sm:gap-2">
      {STEPS.map((key, i) => {
        const last = i === STEPS.length - 1;
        const label = last && finished ? t(`qt.status.${quotation.status}`) : t(`qt.step.${key}`);
        const done = i < at || (last && finished);
        const current = i === at && !finished;
        const danger = last && bad;
        return (
          <li key={key} className="flex min-w-0 flex-1 items-center gap-1.5 last:flex-none" aria-current={current ? "step" : undefined}>
            <span className="sr-only">{done ? t("qt.stepDone", { label }) : current ? t("qt.stepCurrent", { label }) : label}</span>
            <span
              aria-hidden
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption ${
                danger ? "bg-danger text-white" : done ? "bg-primary text-white" : current ? "border-2 border-primary bg-surface text-primary-strong" : "border border-line bg-surface text-ink-3"
              }`}
            >
              {done && !danger ? <Check size={14} weight="bold" /> : i + 1}
            </span>
            <span aria-hidden className={`hidden text-label sm:inline ${current || done ? "text-ink" : "text-ink-3"}`}>{label}</span>
            {!last ? <span aria-hidden className={`h-px min-w-2 flex-1 ${i < at ? "bg-primary" : "bg-line"}`} /> : null}
          </li>
        );
      })}
    </ol>
  );
}

/** Same arithmetic as the server (which is the one that counts): line total, then the version totals. */
export function lineMath(l: { quantity: string; unit_price: string; discount_percent: string; tax_percent: string }) {
  const qty = Number(l.quantity) || 0;
  const price = Number(l.unit_price) || 0;
  const disc = Number(l.discount_percent) || 0;
  const tax = Number(l.tax_percent) || 0;
  const gross = qty * price;
  const discount = (gross * disc) / 100;
  const net = gross - discount;
  const taxAmount = (net * tax) / 100;
  return { gross, discount, tax: taxAmount, total: net + taxAmount };
}

export function totalsOf(lines: Parameters<typeof lineMath>[0][]) {
  return lines.reduce(
    (acc, l) => {
      const m = lineMath(l);
      return { subtotal: acc.subtotal + m.gross, discount: acc.discount + m.discount, tax: acc.tax + m.tax, total: acc.total + m.total };
    },
    { subtotal: 0, discount: 0, tax: 0, total: 0 },
  );
}
