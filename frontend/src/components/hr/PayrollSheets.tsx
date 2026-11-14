"use client";

import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type PayrollEntry, type PayrollRun, type PayrollStatus, type SalaryRow } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const TONE: Record<PayrollStatus, "warning" | "primary" | "success"> = { draft: "warning", ceo_approved: "primary", paid: "success" };
const validMoney = (v: string) => /^\d+(\.\d{1,2})?$/.test(v.trim());

export function RunPill({ status }: { status: PayrollStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={TONE[status]}>{t(`payroll.status.${status}`)}</StatusPill>;
}

const currentMonth = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export function NewRunSheet({ onClose, onDone }: { onClose: () => void; onDone: (run: PayrollRun) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [month, setMonth] = useState(currentMonth());
  const [local, setLocal] = useState("");
  const action = useAction(["month"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!month) {
      setLocal("payroll.err.month");
      return document.getElementById("field-month")?.focus();
    }
    const run = await action.run(() => api<PayrollRun>("/hr/payroll/runs/", { method: "POST", body: { month } }));
    if (run) {
      toast.success(t("payroll.run.created"));
      onDone(run);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("payroll.run.new")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="run-form" loading={action.saving}>{t("payroll.run.create")}</Button>
        </>
      }
    >
      <form id="run-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-label font-normal text-ink-2">{t("payroll.run.help")}</p>
        <Input name="month" label={t("payroll.month")} type="month" required max={currentMonth()} value={month} onChange={(e) => { setMonth(e.target.value); setLocal(""); }} error={month ? action.errors.month : local} />
      </form>
    </Sheet>
  );
}

export function SalarySheet({ row, onClose, onDone }: { row: SalaryRow; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [amount, setAmount] = useState(row.base_salary ?? "");
  const [currency, setCurrency] = useState(row.currency ?? "JOD");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["base_salary", "currency"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!validMoney(amount)) found.base_salary = "payroll.err.salary";
    if (!/^[A-Za-z]{3}$/.test(currency.trim())) found.currency = "pay.err.currency";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const saved = await action.run(() => api(`/hr/salaries/${row.user}/`, { method: "PUT", body: { base_salary: amount.trim(), currency: currency.trim().toUpperCase() } }));
    if (saved) {
      toast.success(t("payroll.salary.saved"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("payroll.salary.title", { name: row.user_name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="salary-form" loading={action.saving}>{t("common.save")}</Button>
        </>
      }
    >
      <form id="salary-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="base_salary" label={t("payroll.base")} required inputMode="decimal" ltr value={amount} onChange={(e) => { setAmount(e.target.value); setLocal({}); }} error={errors.base_salary} />
        <Input name="currency" label={t("pay.currency")} required ltr maxLength={3} value={currency} onChange={(e) => { setCurrency(e.target.value.toUpperCase()); setLocal({}); }} error={errors.currency} />
      </form>
    </Sheet>
  );
}

export function EntrySheet({ entry, currency, onClose, onDone }: { entry: PayrollEntry; currency: string; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [allow, setAllow] = useState(entry.allowances);
  const [deduct, setDeduct] = useState(entry.deductions);
  const [note, setNote] = useState(entry.note);
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["allowances", "deductions", "note"]);
  const errors = { ...action.errors, ...local };
  const net = Number(entry.base_salary) + (validMoney(allow) ? Number(allow) : 0) - (validMoney(deduct) ? Number(deduct) : 0);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!validMoney(allow)) found.allowances = "payroll.err.amount";
    if (!validMoney(deduct)) found.deductions = "payroll.err.amount";
    else if (net < 0) found.deductions = "payroll.err.net";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const saved = await action.run(() => api(`/hr/payroll/entries/${entry.id}/`, { method: "PATCH", body: { allowances: allow.trim(), deductions: deduct.trim(), note: note.trim() } }));
    if (saved) {
      toast.success(t("payroll.entry.saved"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={entry.user_name}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="entry-form" loading={action.saving}>{t("common.save")}</Button>
        </>
      }
    >
      <form id="entry-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-label font-normal text-ink-2">{t("payroll.entry.base", { amount: `${entry.base_salary} ${currency}` })}</p>
        <Input name="allowances" label={t("payroll.allowances")} inputMode="decimal" ltr value={allow} onChange={(e) => { setAllow(e.target.value); setLocal({}); }} error={errors.allowances} />
        <Input name="deductions" label={t("payroll.deductions")} inputMode="decimal" ltr value={deduct} onChange={(e) => { setDeduct(e.target.value); setLocal({}); }} error={errors.deductions} />
        <Input name="note" label={t("pay.note")} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} error={errors.note} />
        <p aria-live="polite" className="tnum text-body font-semibold text-ink" dir="ltr">{t("payroll.net")}: {net.toFixed(2)} {currency}</p>
      </form>
    </Sheet>
  );
}

export function ReopenSheet({ run, onClose, onDone }: { run: PayrollRun; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<PayrollRun>
      path={`/hr/payroll/runs/${run.id}/reopen/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("payroll.reopen.title")}
      intro={t("payroll.reopen.intro", { month: run.month })}
      question={t("payroll.reopen.reason")}
      confirm={t("payroll.reopen.confirm")}
      done={t("payroll.reopen.done")}
      emptyKey="payroll.err.reopen"
    />
  );
}
