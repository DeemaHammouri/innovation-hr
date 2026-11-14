"use client";

import { useState } from "react";
import { FormError, ReasonSheet, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type Contract, type Lead } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Done = (c: Contract) => void;

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function RequestContractSheet({ lead, onClose, onDone }: { lead: Lead; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Contract>("/contracts/", { method: "POST", body: { lead: lead.id, note: note.trim() } }));
    if (saved) {
      toast.success(t("ct.requested"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.request.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="request-contract-form" loading={action.saving}>{t("ct.request.save")}</Button>
        </>
      }
    >
      <form id="request-contract-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("ct.request.text", { name: lead.company_name })}</p>
        <Textarea name="note" label={t("ct.request.note")} hint={t("ct.request.noteHint")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

/** HR sends the draft (uploaded in the Documents section) to Commercial, with an optional note. */
export function SendSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const [note, setNote] = useState("");
  const action = useAction(["note"]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/send/`, { method: "POST", body: { note: note.trim() } }));
    if (saved) {
      toast.success(t("ct.sent"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.send.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="send-contract-form" loading={action.saving}>{t("ct.send.save")}</Button>
        </>
      }
    >
      <form id="send-contract-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("ct.send.text")}</p>
        <Textarea name="note" label={t("ct.send.note")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={action.errors.note} />
      </form>
    </Sheet>
  );
}

/** Commercial logs the offline meeting: when it happened and what was discussed. */
export function MeetingSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t, msg } = useI18n();
  const toast = useToast();
  const [date, setDate] = useState(todayIso());
  const [notes, setNotes] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["meeting_date", "meeting_notes"]);
  const errors = { ...action.errors, ...local };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!date) found.meeting_date = "Choose the date the meeting took place.";
    if (!notes.trim()) found.meeting_notes = "Write what was discussed in the meeting.";
    setLocal(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`field-${first}`)?.focus();
      return;
    }
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/meeting/`, { method: "POST", body: { meeting_date: date, meeting_notes: notes.trim() } }));
    if (saved) {
      toast.success(t("ct.meetingLogged"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.meeting.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" form="meeting-form" loading={action.saving}>{t("ct.meeting.save")}</Button>
        </>
      }
    >
      <form id="meeting-form" onSubmit={submit} noValidate className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("ct.meeting.text")}</p>
        <Input name="meeting_date" label={t("ct.meeting.date")} type="date" required max={todayIso()} value={date} onChange={(e) => { setDate(e.target.value); setLocal({}); }} error={errors.meeting_date ? msg(errors.meeting_date) : undefined} />
        <Textarea name="meeting_notes" label={t("ct.meeting.notes")} required rows={4} value={notes} onChange={(e) => { setNotes(e.target.value); setLocal({}); }} error={errors.meeting_notes} />
      </form>
    </Sheet>
  );
}

/** Commercial sends the meeting file to the CEO. The server refuses if a document is missing and says which. */
export function SubmitSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction([]);
  async function go() {
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/submit/`, { method: "POST" }));
    if (saved) {
      toast.success(t("ct.submitted"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      onClose={onClose}
      title={t("ct.submit.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={action.saving} onClick={go}>{t("ct.submit.save")}</Button>
        </>
      }
    >
      <FormError message={action.formError} />
      <p className="text-body text-ink-2">{t("ct.submit.text")}</p>
    </Sheet>
  );
}

/** The CEO's signature: one confirmation, and the name and time are stored. */
export function ApproveSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction([]);
  async function go() {
    const saved = await action.run(() => api<Contract>(`/contracts/${contract.id}/approve/`, { method: "POST" }));
    if (saved) {
      toast.success(t("ct.approved"));
      onDone(saved);
    }
  }
  return (
    <Sheet
      open
      alert
      onClose={onClose}
      title={t("ct.approve.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={action.saving} onClick={go}>{t("ct.approve.save")}</Button>
        </>
      }
    >
      <FormError message={action.formError} />
      <p className="text-body text-ink-2">{t("ct.approve.text", { name: contract.lead_company })}</p>
    </Sheet>
  );
}

export function ReturnSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Contract>
      path={`/contracts/${contract.id}/return/`}
      onClose={onClose}
      onDone={onDone}
      field="comment"
      title={t("ct.return.title")}
      intro={t("ct.return.text")}
      question={t("ct.return.comment")}
      confirm={t("ct.return.save")}
      done={t("ct.returned")}
      emptyKey="qt.err.comment"
    />
  );
}

export function CancelContractSheet({ contract, onClose, onDone }: { contract: Contract; onClose: () => void; onDone: Done }) {
  const { t } = useI18n();
  return (
    <ReasonSheet<Contract>
      path={`/contracts/${contract.id}/cancel/`}
      onClose={onClose}
      onDone={onDone}
      field="reason"
      title={t("ct.cancel.title")}
      intro={t("ct.cancel.text", { ref: contract.ref })}
      question={t("ct.cancel.reason")}
      confirm={t("ct.cancel.save")}
      done={t("ct.cancelled")}
      danger
      emptyKey="ct.err.cancel"
    />
  );
}
