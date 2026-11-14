"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Assignee, type Lead } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Errors = Record<string, string>;
type Done = (lead: Lead) => void;

/** Runs one request, keeps the sheet open on a problem, and puts server messages beside the right field. */
export function useAction(fields: string[]) {
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  async function run<T>(request: () => Promise<T>): Promise<T | null> {
    setSaving(true);
    setErrors({});
    setFormError("");
    try {
      const out = await request();
      return out;
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const all = err.fieldErrors();
        const mine = Object.fromEntries(fields.filter((f) => all[f]).map((f) => [f, all[f]]));
        setErrors(mine);
        const first = fields.find((f) => mine[f]);
        if (first) document.getElementById(`field-${first}`)?.focus();
        else setFormError(all.detail || "lead.fix");
      } else {
        setFormError(err instanceof ApiError && err.message ? err.message : "lead.saveFailed");
      }
      setSaving(false);
      return null;
    }
  }
  return { saving, setSaving, errors, setErrors, formError, run };
}

export function FormError({ message }: { message: string }) {
  const { msg } = useI18n();
  if (!message) return null;
  return (
    <p role="alert" className="mb-4 rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">
      {msg(message)}
    </p>
  );
}

type Outcome = "" | "waiting" | "rejected" | "accepted";
const TYPES = ["call", "whatsapp", "email", "meeting", "other"] as const;
const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

type Reason = { id: number; name_en: string; name_ar: string; is_active: boolean };

/** Log a contact (with or without an outcome), or record only the outcome. Input is asked for before anything moves. */
export function ContactSheet({
  lead,
  mode,
  initialOutcome = "",
  onClose,
  onDone,
}: {
  lead: Lead;
  mode: "contact" | "outcome";
  initialOutcome?: Outcome;
  onClose: () => void;
  onDone: Done;
}) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const mustChoose = mode === "outcome" || lead.status === "waiting";
  const [type, setType] = useState("call");
  const [when, setWhen] = useState("");
  const [notes, setNotes] = useState("");
  const [outcome, setOutcome] = useState<Outcome>(initialOutcome);
  const [followUp, setFollowUp] = useState("");
  const [reason, setReason] = useState("");
  const [reasonNote, setReasonNote] = useState("");
  const [local, setLocal] = useState<Errors>({});
  const action = useAction(["type", "occurred_at", "notes", "outcome", "next_follow_up", "rejection_reason", "rejection_note"]);
  const { data: reasons } = useFetch<Reason[] | { results: Reason[] }>("/lookups/rejection-reasons/");
  const reasonList = (Array.isArray(reasons) ? reasons : (reasons?.results ?? [])).filter((r) => r.is_active);
  const errors = { ...action.errors, ...local };

  const options: { value: Outcome; label: string; text: string }[] = [
    ...(mustChoose ? [] : [{ value: "" as Outcome, label: t("lead.outcome.none"), text: t("lead.contact.outcomeNone") }]),
    { value: "waiting", label: t("lead.outcome.waiting"), text: t("lead.outcome.waitingText") },
    { value: "accepted", label: t("lead.outcome.accepted"), text: t("lead.outcome.acceptedText") },
    { value: "rejected", label: t("lead.outcome.rejected"), text: t("lead.outcome.rejectedText") },
  ];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Errors = {};
    if (mustChoose && !outcome) found.outcome = "lead.err.8";
    if (outcome === "waiting" && !followUp) found.next_follow_up = "lead.err.9";
    if (outcome === "rejected" && !reason) found.rejection_reason = "lead.err.12";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const body: Record<string, unknown> = { outcome, notes };
    if (mode === "contact") body.type = type;
    if (when) body.occurred_at = new Date(when).toISOString();
    if (outcome === "waiting") body.next_follow_up = followUp;
    if (outcome === "rejected") {
      body.rejection_reason = Number(reason);
      body.rejection_note = reasonNote;
    }
    const saved = await action.run(() => api<Lead>(`/leads/${lead.id}/${mode === "contact" ? "interactions" : "outcome"}/`, { method: "POST", body }));
    if (saved) {
      toast.success(t(mode === "contact" ? "lead.contactSaved" : "lead.outcomeSaved"));
      onDone(saved);
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={t(mode === "contact" ? "lead.contact.title" : "lead.contact.outcomeTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="contact-form" loading={action.saving}>{t(mode === "contact" ? "lead.logContact" : "lead.logOutcome")}</Button>
        </>
      }
    >
      <form id="contact-form" onSubmit={submit} noValidate className="space-y-5">
        <FormError message={action.formError} />
        {mode === "contact" ? (
          <div className="grid gap-5 sm:grid-cols-2">
            <Select name="type" label={t("lead.contact.type")} value={type} onChange={(e) => setType(e.target.value)} error={errors.type} options={TYPES.map((v) => ({ value: v, label: t(`lead.type.${v}`) }))} />
            <Input name="occurred_at" label={t("lead.contact.when")} type="datetime-local" max={`${todayIso()}T23:59`} value={when} onChange={(e) => setWhen(e.target.value)} error={errors.occurred_at} />
          </div>
        ) : null}
        <Textarea name="notes" label={t("lead.contact.notes")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} error={errors.notes} />
        <fieldset>
          <legend className="mb-1.5 block text-label text-ink">
            {t("lead.contact.outcome")}
            {mustChoose ? <span className="font-medium text-ink-2"> {t("common.required")}</span> : null}
          </legend>
          <div className="space-y-2" role="radiogroup" aria-label={t("lead.contact.outcome")}>
            {options.map((o) => (
              <label key={o.value || "none"} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-control border px-3.5 py-2.5 ${outcome === o.value ? "border-primary bg-primary-tint" : "border-line bg-surface hover:bg-canvas"}`}>
                <input id={o.value === (options[0].value) ? "field-outcome" : undefined} type="radio" name="outcome" value={o.value} checked={outcome === o.value} onChange={() => { setOutcome(o.value); setLocal({}); }} className="size-4 accent-[var(--color-primary)]" />
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
            <Select name="rejection_reason" label={t("lead.reason")} required placeholder={t("lead.reasonChoose")} value={reason} onChange={(e) => { setReason(e.target.value); setLocal({}); }} error={errors.rejection_reason} options={reasonList.map((r) => ({ value: String(r.id), label: lang === "ar" ? r.name_ar : r.name_en }))} />
            <Textarea name="rejection_note" label={t("lead.reasonNote")} rows={2} value={reasonNote} onChange={(e) => setReasonNote(e.target.value)} error={errors.rejection_note} />
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

export function AssignSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t, formatNumber } = useI18n();
  const toast = useToast();
  const { data: people } = useFetch<Assignee[]>("/leads/assignees/");
  const [who, setWho] = useState(lead.assigned_to ? String(lead.assigned_to) : "");
  const [local, setLocal] = useState("");
  const action = useAction(["assigned_to"]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!who) {
      setLocal("lead.err.16");
      document.getElementById("field-assigned_to")?.focus();
      return;
    }
    const saved = await action.run(() => api<Lead>(`/leads/${lead.id}/assign/`, { method: "POST", body: { assigned_to: Number(who) } }));
    if (saved) {
      toast.success(t("lead.assigned", { name: saved.assigned_to_name ?? "" }));
      onDone(saved);
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={t(lead.assigned_to ? "lead.assign.reassign" : "lead.assign.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="assign-form" loading={action.saving}>{t("lead.assign.save")}</Button>
        </>
      }
    >
      <form id="assign-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        {people && people.length === 0 ? (
          <p className="text-body text-ink-2">{t("lead.assign.none")}</p>
        ) : (
          <Select
            name="assigned_to"
            label={t("lead.assign.choose")}
            required
            placeholder={t("lead.assign.choose")}
            value={who}
            onChange={(e) => { setWho(e.target.value); setLocal(""); }}
            error={local || action.errors.assigned_to}
            options={(people ?? []).map((p) => ({ value: String(p.id), label: `${p.full_name} · ${t("lead.assign.openLeads", { count: formatNumber(p.open_leads) })}` }))}
          />
        )}
      </form>
    </Sheet>
  );
}

/** A sheet that asks for one written reason, then posts it to `path`. Reopen, archive, request changes and cancel are all this. */
export function ReasonSheet<T>({
  path,
  onClose,
  onDone,
  field,
  title,
  question,
  confirm,
  done,
  intro,
  danger,
  emptyKey,
}: {
  path: string;
  onClose: () => void;
  onDone: (result: T) => void;
  field: string;
  title: string;
  question: string;
  confirm: string;
  done: string;
  intro?: string;
  danger?: boolean;
  emptyKey: string;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [text, setText] = useState("");
  const [local, setLocal] = useState("");
  const action = useAction([field]);
  const formId = `reason-form-${field}`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) {
      setLocal(emptyKey);
      document.getElementById(`field-${field}`)?.focus();
      return;
    }
    const saved = await action.run(() => api<T>(path, { method: "POST", body: { [field]: text.trim() } }));
    if (saved) {
      toast.success(done);
      onDone(saved);
    }
  }

  return (
    <Sheet
      open
      alert={danger}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button variant={danger ? "danger" : "primary"} type="submit" form={formId} loading={action.saving}>{confirm}</Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        {intro ? <p className="text-body text-ink-2">{intro}</p> : null}
        <Textarea name={field} label={question} required rows={3} value={text} onChange={(e) => { setText(e.target.value); setLocal(""); }} error={local || action.errors[field]} />
      </form>
    </Sheet>
  );
}

export function ReopenSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return <ReasonSheet<Lead> path={`/leads/${lead.id}/reopen/`} onClose={onClose} onDone={onDone} field="note" title={t("lead.reopen.title")} question={t("lead.reopen.note")} confirm={t("lead.reopen.save")} done={t("lead.reopened")} emptyKey="lead.err.15" />;
}

export function ArchiveSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Lead> path={`/leads/${lead.id}/archive/`} onClose={onClose} onDone={onDone} field="reason" title={t("lead.archive.title")} intro={t("lead.archive.text", { name: lead.company_name })} question={t("lead.archive.reason")} confirm={t("lead.archive.save")} done={t("lead.archived")} danger emptyKey="lead.err.17" />
  );
}
