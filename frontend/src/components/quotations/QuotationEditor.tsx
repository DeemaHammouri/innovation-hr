"use client";

import { Plus, Trash } from "@phosphor-icons/react";
import { useState } from "react";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Quotation, type QuotationLine, type QuotationVersion, type ServiceItem } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { lineMath, totalsOf, useMoney } from "./quoteUi";

const CURRENCIES = ["JOD", "USD", "EUR", "SAR", "AED"];
type Line = Omit<QuotationLine, "service" | "visits" | "frequency"> & { service: string; key: number; frequency: string; visits: string };
const FREQUENCIES = ["once", "monthly", "quarterly", "semiannual", "annual"];
type LineErrors = Record<string, string>;

let counter = 0;
const blank = (): Line => ({ key: ++counter, service: "", description: "", quantity: "1", unit_price: "", discount_percent: "0", tax_percent: "0", frequency: "once", visits: "" });
const fromServer = (l: QuotationLine): Line => ({ key: ++counter, service: l.service ? String(l.service) : "", description: l.description, quantity: l.quantity, unit_price: l.unit_price, discount_percent: l.discount_percent, tax_percent: l.tax_percent, frequency: l.frequency ?? "once", visits: l.visits == null ? "" : String(l.visits) });
const strip = (v: string) => v.replace(/\.00$/, "");

/** HR's working screen: the draft version's details and line items. Totals shown here are a preview; the server's numbers are the ones that count. */
export function QuotationEditor({ quotation, version, onChanged }: { quotation: Quotation; version: QuotationVersion; onChanged: (q: Quotation) => void }) {
  const { t, msg, lang } = useI18n();
  const toast = useToast();
  const money = useMoney();
  const { data: services } = useFetch<ServiceItem[] | { results: ServiceItem[] }>("/lookups/services/");
  const catalog = (Array.isArray(services) ? services : (services?.results ?? [])).filter((s) => s.is_active);
  const [currency, setCurrency] = useState(version.currency);
  const [validUntil, setValidUntil] = useState(version.valid_until ?? "");
  const [notes, setNotes] = useState(version.notes);
  const [paymentTerms, setPaymentTerms] = useState(version.payment_terms ?? "");
  const [lines, setLines] = useState<Line[]>(() => (version.lines.length ? version.lines.map(fromServer) : [blank()]));
  const [saving, setSaving] = useState<"" | "draft" | "submit">("");
  const [top, setTop] = useState<Record<string, string>>({});
  const [lineErrors, setLineErrors] = useState<LineErrors[]>([]);
  const [formError, setFormError] = useState("");

  const totals = totalsOf(lines);
  const update = (key: number, patch: Partial<Line>) => setLines((all) => all.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  function pickService(l: Line, id: string) {
    const svc = catalog.find((s) => String(s.id) === id);
    const name = svc ? (lang === "ar" ? svc.name_ar : svc.name_en) : "";
    const previous = catalog.find((s) => String(s.id) === l.service);
    const wasAuto = !l.description || (previous && [previous.name_en, previous.name_ar].includes(l.description));
    update(l.key, {
      service: id,
      ...(svc && wasAuto ? { description: name } : {}),
      ...(svc?.default_unit_price && (!l.unit_price || Number(l.unit_price) === 0) ? { unit_price: strip(svc.default_unit_price) } : {}),
    });
    if (svc && CURRENCIES.includes(svc.currency) && lines.every((x) => !x.unit_price || x.key === l.key)) setCurrency(svc.currency);
  }

  const body = () => ({
    currency,
    valid_until: validUntil || null,
    notes,
    payment_terms: paymentTerms,
    lines: lines.map((l) => ({ frequency: l.frequency, visits: l.visits === "" ? null : l.visits, service: l.service ? Number(l.service) : null, description: l.description, quantity: l.quantity, unit_price: l.unit_price === "" ? "0" : l.unit_price, discount_percent: l.discount_percent || "0", tax_percent: l.tax_percent || "0" })),
  });

  function showErrors(err: unknown) {
    if (err instanceof ApiError && err.status === 400) {
      const data = err.data as Record<string, unknown>;
      const next: Record<string, string> = {};
      for (const k of ["currency", "valid_until", "notes", "payment_terms"]) if (Array.isArray(data[k])) next[k] = String((data[k] as unknown[])[0]);
      if (Array.isArray(data.lines)) {
        const arr = data.lines as unknown[];
        if (arr.length && typeof arr[0] === "string") next.lines = String(arr[0]);
        else setLineErrors(arr.map((e) => (e && typeof e === "object" ? (e as LineErrors) : {})));
      }
      setTop(next);
      if (!Object.keys(next).length && !Array.isArray(data.lines)) setFormError(typeof data.detail === "string" ? data.detail : "lead.fix");
      const first = next.currency ? "currency" : next.valid_until ? "valid_until" : null;
      if (first) document.getElementById(`field-${first}`)?.focus();
    } else {
      setFormError(err instanceof ApiError && err.status === 403 ? err.message : "qt.saveFailed");
    }
  }

  async function run(kind: "draft" | "submit") {
    setSaving(kind);
    setTop({});
    setLineErrors([]);
    setFormError("");
    try {
      let q = await api<Quotation>(`/quotations/${quotation.id}/draft/`, { method: "PUT", body: body() });
      if (kind === "submit") q = await api<Quotation>(`/quotations/${quotation.id}/submit/`, { method: "POST" });
      toast.success(t(kind === "draft" ? "qt.draftSaved" : "qt.submitted"));
      onChanged(q);
    } catch (err) {
      showErrors(err);
    }
    setSaving("");
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); void run("submit"); }} noValidate className="mb-6 space-y-4 md:space-y-6">
      {quotation.review_comment ? (
        <div role="note" className="rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
          <p className="text-body font-semibold">{t("qt.changesAsked")}</p>
          <p className="mt-1 whitespace-pre-line text-label font-normal">{quotation.review_comment}</p>
        </div>
      ) : null}
      {formError ? <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">{msg(formError)}</p> : null}

      <Card as="section" className="p-5 md:p-6">
        <h2 className="text-section text-ink">{t("qt.editor.details", { number: version.number })}</h2>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <Input name="currency" label={t("qt.currency")} ltr maxLength={3} list="qt-currencies" autoComplete="off" value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} error={top.currency} hint={t("qt.currencyHint")} required />
            <datalist id="qt-currencies">{CURRENCIES.map((c) => <option key={c} value={c} />)}</datalist>
          </div>
          <Input name="valid_until" label={t("qt.validUntil")} type="date" required value={validUntil} onChange={(e) => setValidUntil(e.target.value)} error={top.valid_until} hint={t("qt.validUntilHint")} />
        </div>
      </Card>

      <section aria-labelledby="qt-lines" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="qt-lines" className="text-section text-ink">{t("qt.lines")}</h2>
        </div>
        {top.lines ? <p role="alert" className="text-label font-medium text-danger-ink">{msg(top.lines)}</p> : null}
        {lines.map((l, i) => {
          const errs = lineErrors[i] ?? {};
          const m = lineMath(l);
          return (
            <Card key={l.key} as="section" className="p-4 md:p-5" aria-label={t("qt.lineN", { n: i + 1 })}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-body font-semibold text-ink">{t("qt.lineN", { n: i + 1 })}</h3>
                <IconButton label={t("qt.removeLine", { n: i + 1 })} onClick={() => setLines((all) => (all.length > 1 ? all.filter((x) => x.key !== l.key) : [blank()]))}>
                  <Trash size={20} aria-hidden />
                </IconButton>
              </div>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
                  <Select name={`service-${l.key}`} label={t("qt.service")} value={l.service} onChange={(e) => pickService(l, e.target.value)} error={errs.service} placeholder={t("qt.customItem")} options={catalog.map((s) => ({ value: String(s.id), label: lang === "ar" ? s.name_ar : s.name_en }))} />
                  <Input name={`description-${l.key}`} label={t("qt.description")} required value={l.description} onChange={(e) => update(l.key, { description: e.target.value })} error={errs.description} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Select name={`frequency-${l.key}`} label={t("qt.frequency")} value={l.frequency} onChange={(e) => update(l.key, { frequency: e.target.value })} error={errs.frequency} options={FREQUENCIES.map((f) => ({ value: f, label: t(`qt.freq.${f}`) }))} />
                  <Input name={`visits-${l.key}`} label={t("qt.visits")} inputMode="numeric" ltr value={l.visits} onChange={(e) => update(l.key, { visits: e.target.value })} error={errs.visits} />
                </div>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                  <Input name={`quantity-${l.key}`} label={t("qt.quantity")} inputMode="decimal" ltr value={l.quantity} onChange={(e) => update(l.key, { quantity: e.target.value })} error={errs.quantity} />
                  <Input name={`unit_price-${l.key}`} label={t("qt.unitPrice")} inputMode="decimal" ltr value={l.unit_price} onChange={(e) => update(l.key, { unit_price: e.target.value })} error={errs.unit_price} />
                  <Input name={`discount_percent-${l.key}`} label={t("qt.discountPct")} inputMode="decimal" ltr value={l.discount_percent} onChange={(e) => update(l.key, { discount_percent: e.target.value })} error={errs.discount_percent} />
                  <Input name={`tax_percent-${l.key}`} label={t("qt.taxPct")} inputMode="decimal" ltr value={l.tax_percent} onChange={(e) => update(l.key, { tax_percent: e.target.value })} error={errs.tax_percent} />
                  <div className="col-span-2 md:col-span-1">
                    <p className="mb-1.5 text-label text-ink">{t("qt.lineTotal")}</p>
                    <p className="tnum flex h-11 items-center text-body font-semibold text-ink" dir="ltr">{money(m.total, currency)}</p>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
        <Button variant="secondary" icon={<Plus size={18} aria-hidden />} onClick={() => lines.length < 100 && setLines((all) => [...all, blank()])}>
          {t("qt.addLine")}
        </Button>
      </section>

      <Card as="section" className="p-5 md:p-6">
        <dl className="tnum space-y-2 text-body">
          <Row label={t("qt.subtotal")} value={money(totals.subtotal, currency)} />
          <Row label={t("qt.discount")} value={`− ${money(totals.discount, currency)}`} />
          <Row label={t("qt.tax")} value={money(totals.tax, currency)} />
          <div className="flex items-center justify-between border-t border-line pt-3 text-section font-semibold text-ink">
            <dt>{t("qt.total")}</dt>
            <dd dir="ltr">{money(totals.total, currency)}</dd>
          </div>
        </dl>
        <p className="mt-3 text-caption text-ink-2">{t("qt.totalsNote")}</p>
      </Card>

      <Card as="section" className="p-5 md:p-6">
        <Textarea name="payment_terms" label={t("qt.paymentTerms")} hint={t("qt.paymentTermsHint")} rows={3} value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} error={top.payment_terms} />
        <div className="mt-5" />
        <Textarea name="notes" label={t("qt.notes")} hint={t("qt.notesHint")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} error={top.notes} />
      </Card>

      <div className="sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 -mx-4 flex gap-3 border-t border-line bg-surface px-4 py-3 md:bottom-4 md:mx-0 md:justify-end md:rounded-card md:border md:shadow-float">
        <Button variant="secondary" loading={saving === "draft"} onClick={() => void run("draft")} className="flex-1 md:flex-none">{t("qt.saveDraft")}</Button>
        <Button type="submit" loading={saving === "submit"} className="flex-1 md:flex-none">{t("qt.submitReview")}</Button>
      </div>
    </form>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-ink-2">
      <dt>{label}</dt>
      <dd dir="ltr" className="text-ink">{value}</dd>
    </div>
  );
}
