"use client";

import { Plus, Trash } from "@phosphor-icons/react";
import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { FilesPanel } from "@/components/records/RecordPanels";
import { Button, IconButton } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Instalment, type Statement } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export const METHODS = ["bank_transfer", "cash", "cheque", "card", "other"] as const;
export const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const validMoney = (v: string) => /^\d+(\.\d{1,2})?$/.test(v.trim()) && Number(v) > 0;

type Row = { due_date: string; amount: string; note: string };
type RowErrors = { due_date?: string; amount?: string };

/** Build an instalment schedule: a currency and one or more (date, amount) rows. */
export function ScheduleSheet({ clientId, currency, onClose, onDone }: { clientId: number; currency: string; onClose: () => void; onDone: (s: Statement) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [total, setTotal] = useState("");
  const [totalErr, setTotalErr] = useState("");
  const [cur, setCur] = useState(currency);
  const [rows, setRows] = useState<Row[]>([{ due_date: addDays(todayIso(), 30), amount: "", note: "" }]);
  const [errs, setErrs] = useState<RowErrors[]>([]);
  const [curErr, setCurErr] = useState("");
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (i: number, patch: Partial<Row>) => {
    setRows((r) => r.map((x, n) => (n === i ? { ...x, ...patch } : x)));
    setErrs([]);
  };
  function equalSplit() {
    if (!validMoney(total)) {
      setTotalErr("pay.err.amount");
      return document.getElementById("field-total")?.focus();
    }
    setTotalErr("");
    const cents = Math.round(Number(total) * 100);
    const each = Math.floor(cents / rows.length);
    setRows((r) => r.map((x, n) => ({ ...x, amount: ((n === r.length - 1 ? cents - each * (r.length - 1) : each) / 100).toFixed(2) })));
    setErrs([]);
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found = rows.map<RowErrors>((r) => ({
      due_date: r.due_date ? undefined : "pay.err.date",
      amount: validMoney(r.amount) ? undefined : "pay.err.amount",
    }));
    const bad = found.findIndex((f) => f.due_date || f.amount);
    const curBad = !/^[A-Za-z]{3}$/.test(cur.trim());
    setErrs(found);
    setCurErr(curBad ? "pay.err.currency" : "");
    if (curBad) return document.getElementById("field-currency")?.focus();
    if (bad >= 0) return document.getElementById(`field-${found[bad].due_date ? "due" : "amt"}-${bad}`)?.focus();
    setSaving(true);
    setFormError("");
    try {
      const out = await api<Statement>(`/payments/clients/${clientId}/schedule/`, { method: "POST", body: { currency: cur.trim().toUpperCase(), instalments: rows.map((r) => ({ ...r, amount: r.amount.trim() })) } });
      toast.success(t("pay.sched.saved"));
      onDone(out);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const nested = err.data.instalments;
        if (Array.isArray(nested)) setErrs(nested as RowErrors[]);
        if (typeof err.data.currency === "string" || Array.isArray(err.data.currency)) setCurErr(String(Array.isArray(err.data.currency) ? err.data.currency[0] : err.data.currency));
        else if (!Array.isArray(nested)) setFormError(String(err.fieldErrors().instalments || err.fieldErrors().detail || "lead.fix"));
        else setFormError("lead.fix");
      } else setFormError("lead.saveFailed");
      setSaving(false);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("pay.sched.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="schedule-form" loading={saving}>{t("pay.sched.save")}</Button>
        </>
      }
    >
      <form id="schedule-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={formError} />
        <p className="text-label font-normal text-ink-2">{t("pay.sched.help")}</p>
        <Input name="currency" label={t("pay.currency")} required ltr maxLength={3} value={cur} onChange={(e) => { setCur(e.target.value.toUpperCase()); setCurErr(""); }} error={curErr} />
        <ul className="space-y-3">
          {rows.map((r, i) => (
            <li key={i} className="rounded-card border border-line p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-label font-semibold text-ink">{t("pay.sched.row", { n: i + 1 })}</p>
                {rows.length > 1 ? (
                  <IconButton label={t("pay.sched.removeRow", { n: i + 1 })} variant="ghost" onClick={() => setRows((x) => x.filter((_, n) => n !== i))}>
                    <Trash size={18} aria-hidden />
                  </IconButton>
                ) : null}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input name={`due-${i}`} label={t("pay.dueDate")} type="date" required value={r.due_date} onChange={(e) => set(i, { due_date: e.target.value })} error={errs[i]?.due_date} />
                <Input name={`amt-${i}`} label={t("pay.amount")} required inputMode="decimal" ltr value={r.amount} onChange={(e) => set(i, { amount: e.target.value })} error={errs[i]?.amount} />
              </div>
              <div className="mt-3">
                <Input name={`note-${i}`} label={t("pay.note")} maxLength={200} value={r.note} onChange={(e) => set(i, { note: e.target.value })} />
              </div>
            </li>
          ))}
        </ul>
        <Button variant="secondary" icon={<Plus size={18} aria-hidden />} onClick={() => setRows((x) => [...x, { due_date: addDays(x[x.length - 1]?.due_date || todayIso(), 30), amount: "", note: "" }])} disabled={rows.length >= 36}>
          {t("pay.sched.addRow")}
        </Button>
        <div className="rounded-card border border-line bg-canvas/50 p-3">
          <Input name="total" label={t("pay.sched.total")} hint={t("pay.sched.totalHint")} inputMode="decimal" ltr value={total} onChange={(e) => { setTotal(e.target.value); setTotalErr(""); }} error={totalErr} />
          <div className="mt-3">
            <Button variant="secondary" onClick={equalSplit}>{t("pay.sched.split")}</Button>
          </div>
        </div>
      </form>
    </Sheet>
  );
}

/** Record a payment against one instalment. Afterwards the receipt can be attached straight away. */
export function PaySheet({ inst, onClose, onDone }: { inst: Instalment; onClose: () => void; onDone: (s: Statement) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [amount, setAmount] = useState(inst.balance);
  const [received, setReceived] = useState(todayIso());
  const [method, setMethod] = useState<string>("bank_transfer");
  const [reference, setReference] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["amount", "received_on", "method", "reference"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!validMoney(amount)) found.amount = "pay.err.amount";
    else if (Number(amount) > Number(inst.balance)) found.amount = "pay.err.over";
    if (!received) found.received_on = "pay.err.received";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const out = await action.run(() => api<Statement>(`/payments/instalments/${inst.id}/payments/`, { method: "POST", body: { amount: amount.trim(), received_on: received, method, reference: reference.trim() } }));
    if (out) {
      toast.success(t("pay.recorded"));
      onDone(out);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("pay.record.title", { n: inst.number })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="pay-form" loading={action.saving}>{t("pay.record.save")}</Button>
        </>
      }
    >
      <form id="pay-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-label font-normal text-ink-2">{t("pay.record.balance", { amount: `${inst.balance} ${inst.currency}` })}</p>
        <Input name="amount" label={`${t("pay.amount")} (${inst.currency})`} required inputMode="decimal" ltr value={amount} onChange={(e) => { setAmount(e.target.value); setLocal({}); }} error={errors.amount} />
        <Input name="received_on" label={t("pay.receivedOn")} type="date" required max={todayIso()} value={received} onChange={(e) => { setReceived(e.target.value); setLocal({}); }} error={errors.received_on} />
        <Select name="method" label={t("pay.method")} required value={method} onChange={(e) => setMethod(e.target.value)} error={errors.method} options={METHODS.map((m) => ({ value: m, label: t(`pay.method.${m}`) }))} />
        <Input name="reference" label={t("pay.reference")} hint={t("pay.referenceHint")} maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} error={errors.reference} />
      </form>
    </Sheet>
  );
}

export function EditInstalmentSheet({ inst, onClose, onDone }: { inst: Instalment; onClose: () => void; onDone: (s: Statement) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [due, setDue] = useState(inst.due_date);
  const [amount, setAmount] = useState(inst.amount);
  const [note, setNote] = useState(inst.note);
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["due_date", "amount", "note"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!due) found.due_date = "pay.err.date";
    if (!validMoney(amount)) found.amount = "pay.err.amount";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const out = await action.run(() => api<Statement>(`/payments/instalments/${inst.id}/`, { method: "PATCH", body: { due_date: due, amount: amount.trim(), note: note.trim() } }));
    if (out) {
      toast.success(t("pay.edit.saved"));
      onDone(out);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("pay.edit.title", { n: inst.number })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="edit-inst-form" loading={action.saving}>{t("common.save")}</Button>
        </>
      }
    >
      <form id="edit-inst-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="due_date" label={t("pay.dueDate")} type="date" required value={due} onChange={(e) => { setDue(e.target.value); setLocal({}); }} error={errors.due_date} />
        <Input name="amount" label={`${t("pay.amount")} (${inst.currency})`} required inputMode="decimal" ltr value={amount} onChange={(e) => { setAmount(e.target.value); setLocal({}); }} error={errors.amount} />
        <Input name="note" label={t("pay.note")} maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} error={errors.note} />
      </form>
    </Sheet>
  );
}

export function CancelInstalmentSheet({ inst, onClose, onDone }: { inst: Instalment; onClose: () => void; onDone: (s: Statement) => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Statement>
      path={`/payments/instalments/${inst.id}/cancel/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("pay.cancel.title", { n: inst.number })}
      intro={t("pay.cancel.intro")}
      question={t("pay.cancel.reason")}
      confirm={t("pay.cancel.confirm")}
      done={t("pay.cancel.done")}
      danger
      emptyKey="pay.err.cancelReason"
    />
  );
}

export function ReverseSheet({ paymentId, number, onClose, onDone }: { paymentId: number; number: number; onClose: () => void; onDone: (s: Statement) => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Statement>
      path={`/payments/records/${paymentId}/reverse/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("pay.reverse.title")}
      intro={t("pay.reverse.intro", { n: number })}
      question={t("pay.reverse.reason")}
      confirm={t("pay.reverse.confirm")}
      done={t("pay.reverse.done")}
      danger
      emptyKey="pay.err.reverseReason"
    />
  );
}

export function ReceiptSheet({ paymentId, canAttach, onClose }: { paymentId: number; canAttach: boolean; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Sheet open onClose={onClose} title={t("pay.receipt.title")} footer={<Button onClick={onClose}>{t("common.done")}</Button>}>
      <p className="mb-4 text-label font-normal text-ink-2">{t("pay.receipt.help")}</p>
      <FilesPanel target={`payment:${paymentId}`} canAttach={canAttach} category="receipt" />
    </Sheet>
  );
}
