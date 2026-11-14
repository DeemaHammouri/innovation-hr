"use client";

import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type Lead, type Quotation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Done = (q: Quotation) => void;

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** From a qualified lead: ask HR for a quotation, with an optional note about what the client wants. */
export function RequestQuotationSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Quotation>("/quotations/", { method: "POST", body: { lead: lead.id, note: note.trim() } }));
    if (saved) {
      toast.success(t("qt.requested"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("qt.request.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="request-quotation-form" loading={action.saving}>{t("qt.request.save")}</Button>
        </>
      }
    >
      <form id="request-quotation-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("qt.request.text", { name: lead.company_name })}</p>
        <Textarea name="note" label={t("qt.request.note")} hint={t("qt.request.noteHint")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

export function SkipQuotationSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: (lead: Lead) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Lead>(`/leads/${lead.id}/skip-quotation/`, { method: "POST", body: { note: note.trim() } }));
    if (saved) {
      toast.success(t("qt.skipped"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("qt.skip.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="skip-quotation-form" loading={action.saving}>{t("qt.skip.save")}</Button>
        </>
      }
    >
      <form id="skip-quotation-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("qt.skip.text", { name: lead.company_name })}</p>
        <Textarea name="note" label={t("qt.skip.note")} rows={2} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

export function ChangesSheet({ quotation, onClose, onDone }: { quotation: Quotation; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Quotation>
      path={`/quotations/${quotation.id}/request-changes/`}
      onClose={onClose}
      onDone={onDone}
      field="comment"
      title={t("qt.changes.title")}
      intro={t("qt.changes.text")}
      question={t("qt.changes.comment")}
      confirm={t("qt.changes.save")}
      done={t("qt.changesSent")}
      emptyKey="qt.err.comment"
    />
  );
}

export function CancelSheet({ quotation, onClose, onDone }: { quotation: Quotation; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Quotation>
      path={`/quotations/${quotation.id}/cancel/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("qt.cancel.title")}
      intro={t("qt.cancel.text", { ref: quotation.ref })}
      question={t("qt.cancel.reason")}
      confirm={t("qt.cancel.save")}
      done={t("qt.cancelled")}
      danger
      emptyKey="qt.err.cancel"
    />
  );
}

type Outcome = "" | "confirmed" | "waiting" | "rejected";
type Reason = { id: number; name_en: string; name_ar: string; is_active: boolean };

/** What the client decided. A date is asked for when it is waiting, a reason when it is a no. */
export function OutcomeSheet({ quotation, onClose, onDone }: { quotation: Quotation; onClose: () => void; onDone: Done }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [outcome, setOutcome] = useState<Outcome>("");
  const [followUp, setFollowUp] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["outcome", "next_follow_up", "rejection_reason", "rejection_note"]);
  const { data: reasons } = useFetch<Reason[] | { results: Reason[] }>("/lookups/rejection-reasons/");
  const list = (Array.isArray(reasons) ? reasons : (reasons?.results ?? [])).filter((r) => r.is_active);
  const errors = { ...action.errors, ...local };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!outcome) found.outcome = "qt.err.outcome";
    if (outcome === "waiting" && !followUp) found.next_follow_up = "Choose a follow-up date.";
    if (outcome === "rejected" && !reason) found.rejection_reason = "qt.err.reason";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const body: Record<string, unknown> = { outcome };
    if (outcome === "waiting") body.next_follow_up = followUp;
    if (outcome === "rejected") {
      body.rejection_reason = Number(reason);
      body.rejection_note = note;
    }
    const saved = await action.run(() => api<Quotation>(`/quotations/${quotation.id}/outcome/`, { method: "POST", body }));
    if (saved) {
      toast.success(t("qt.outcomeSaved"));
      onDone(saved);
    }
  }

  const options: { value: Outcome; label: string; text: string }[] = [
    { value: "confirmed", label: t("qt.outcome.confirmed"), text: t("qt.outcome.confirmedText") },
    { value: "waiting", label: t("qt.outcome.waiting"), text: t("qt.outcome.waitingText") },
    { value: "rejected", label: t("qt.outcome.rejected"), text: t("qt.outcome.rejectedText") },
  ];
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("qt.outcome.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="qt-outcome-form" loading={action.saving}>{t("qt.outcome.save")}</Button>
        </>
      }
    >
      <form id="qt-outcome-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        <fieldset>
          <legend className="mb-1.5 block text-label text-ink">
            {t("qt.outcome.question")}
            <span className="font-medium text-ink-2"> {t("common.required")}</span>
          </legend>
          <div className="space-y-2" role="radiogroup" aria-label={t("qt.outcome.question")}>
            {options.map((o, i) => (
              <label key={o.value} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-control border px-3.5 py-2.5 ${outcome === o.value ? "border-primary bg-primary-tint" : "border-line bg-surface hover:bg-canvas"}`}>
                <input id={i === 0 ? "field-outcome" : undefined} type="radio" name="qt-outcome" value={o.value} checked={outcome === o.value} onChange={() => { setOutcome(o.value); setLocal({}); }} className="size-4 accent-[var(--color-primary)]" />
                <span className="min-w-0">
                  <span className="block text-body text-ink">{o.label}</span>
                  <span className="block text-label font-normal text-ink-2">{o.text}</span>
                </span>
              </label>
            ))}
          </div>
          {errors.outcome ? <ErrorLine id="outcome" message={errors.outcome} /> : null}
        </fieldset>
        {outcome === "waiting" ? (
          <Input name="next_follow_up" label={t("lead.nextFollowUp")} type="date" required min={todayIso()} hint={t("lead.nextFollowUpHint")} value={followUp} onChange={(e) => { setFollowUp(e.target.value); setLocal({}); }} error={errors.next_follow_up} />
        ) : null}
        {outcome === "rejected" ? (
          <>
            <Select name="rejection_reason" label={t("lead.reason")} required placeholder={t("lead.reasonChoose")} value={reason} onChange={(e) => { setReason(e.target.value); setLocal({}); }} error={errors.rejection_reason} options={list.map((r) => ({ value: String(r.id), label: lang === "ar" ? r.name_ar : r.name_en }))} />
            <Textarea name="rejection_note" label={t("lead.reasonNote")} rows={2} value={note} onChange={(e) => setNote(e.target.value)} error={errors.rejection_note} />
          </>
        ) : null}
      </form>
    </Sheet>
  );
}

function ErrorLine({ id, message }: { id: string; message: string }) {
  const { msg } = useI18n();
  return <p id={`error-${id}`} role="alert" className="mt-1.5 text-label font-medium text-danger-ink">{msg(message)}</p>;
}
