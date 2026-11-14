"use client";

import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type LeaveRequest, type LeaveStatus, type LeaveType } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const TONE: Record<LeaveStatus, "neutral" | "warning" | "success" | "danger"> = { pending: "warning", approved: "success", rejected: "danger", cancelled: "neutral" };

export function LeavePill({ status }: { status: LeaveStatus }) {
  const { t } = useI18n();
  return <StatusPill tone={TONE[status]}>{t(`leave.status.${status}`)}</StatusPill>;
}

export function useTypeName() {
  const { lang } = useI18n();
  return (x: { name_en: string; name_ar: string }) => (lang === "ar" ? x.name_ar : x.name_en);
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function RequestSheet({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const name = useTypeName();
  const { data: types } = useFetch<LeaveType[]>("/hr/leave-types/");
  const [type, setType] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["leave_type", "start_date", "end_date", "reason"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!type) found.leave_type = "leave.err.type";
    if (!start) found.start_date = "leave.err.start";
    if (!end) found.end_date = "leave.err.end";
    else if (start && end < start) found.end_date = "leave.err.order";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const saved = await action.run(() => api("/hr/leave/", { method: "POST", body: { leave_type: Number(type), start_date: start, end_date: end, reason: reason.trim() } }));
    if (saved) {
      toast.success(t("leave.requested"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("leave.request.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="leave-form" loading={action.saving}>{t("leave.request.send")}</Button>
        </>
      }
    >
      <form id="leave-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Select name="leave_type" label={t("leave.type")} required value={type} onChange={(e) => { setType(e.target.value); setLocal({}); }} placeholder={t("leave.type.choose")} error={errors.leave_type} options={(types ?? []).map((x) => ({ value: String(x.id), label: name(x) }))} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input name="start_date" label={t("leave.start")} type="date" required value={start} onChange={(e) => { setStart(e.target.value); if (!end) setEnd(e.target.value); setLocal({}); }} error={errors.start_date} />
          <Input name="end_date" label={t("leave.end")} type="date" required min={start || undefined} value={end} onChange={(e) => { setEnd(e.target.value); setLocal({}); }} error={errors.end_date} />
        </div>
        <p className="text-label font-normal text-ink-2">{t("leave.weekendNote")}</p>
        <Textarea name="reason" label={t("leave.reason")} rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} error={errors.reason} />
      </form>
    </Sheet>
  );
}

export function RejectSheet({ req, onClose, onDone }: { req: LeaveRequest; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<LeaveRequest>
      path={`/hr/leave/${req.id}/reject/`}
      onClose={onClose}
      onDone={onDone}
      field="note"
      title={t("leave.reject.title")}
      intro={`${req.user_name} · ${req.start_date} → ${req.end_date}`}
      question={t("leave.reject.reason")}
      confirm={t("leave.reject.confirm")}
      done={t("leave.reject.done")}
      danger
      emptyKey="leave.err.note"
    />
  );
}

/** Add or edit a leave type (HR head). Switching one off keeps it on old requests. */
export function TypeSheet({ type, onClose, onDone }: { type?: LeaveType; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [en, setEn] = useState(type?.name_en ?? "");
  const [ar, setAr] = useState(type?.name_ar ?? "");
  const [days, setDays] = useState(type?.annual_days ? String(type.annual_days) : "");
  const [paid, setPaid] = useState(type?.paid ?? true);
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["name_en", "name_ar", "annual_days"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!en.trim()) found.name_en = "leave.err.typeName";
    if (!ar.trim()) found.name_ar = "leave.err.typeName";
    if (days.trim() && !(Number(days) >= 1 && Number(days) <= 366 && Number.isInteger(Number(days)))) found.annual_days = "leave.err.allowance";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) return document.getElementById(`field-${first}`)?.focus();
    const body = { name_en: en.trim(), name_ar: ar.trim(), annual_days: days.trim() ? Number(days) : "", paid };
    const saved = await action.run(() => (type ? api(`/hr/leave-types/${type.id}/`, { method: "PATCH", body }) : api("/hr/leave-types/", { method: "POST", body })));
    if (saved) {
      toast.success(t("leave.types.saved"));
      onDone();
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t(type ? "leave.types.edit" : "leave.types.add")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="type-form" loading={action.saving}>{t("common.save")}</Button>
        </>
      }
    >
      <form id="type-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <Input name="name_en" label={t("op.item.nameEn")} required value={en} onChange={(e) => { setEn(e.target.value); setLocal({}); }} error={errors.name_en} />
        <Input name="name_ar" label={t("op.item.nameAr")} required dir="rtl" lang="ar" value={ar} onChange={(e) => { setAr(e.target.value); setLocal({}); }} error={errors.name_ar} />
        <Input name="annual_days" label={t("leave.types.allowance")} hint={t("leave.types.allowanceHint")} inputMode="numeric" ltr value={days} onChange={(e) => { setDays(e.target.value); setLocal({}); }} error={errors.annual_days} />
        <label htmlFor="type-paid" className="flex min-h-11 cursor-pointer items-center gap-3 text-label text-ink">
          <input id="type-paid" type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} className="size-4 accent-[var(--color-primary)]" />
          {t("leave.types.paid")}
        </label>
      </form>
    </Sheet>
  );
}

export { iso as isoDate };
