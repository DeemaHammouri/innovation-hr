"use client";

import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Segmented";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type ClientDecision, type Lookup } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** After a completed meeting Commercial records what the client decided. Confirm starts the contract; Waiting books the follow-up; Rejection asks why. */
export function DecisionSheet({ clientId, onClose, onDone }: { clientId: number; onClose: () => void; onDone: () => void }) {
  const { t, lang, msg } = useI18n();
  const toast = useToast();
  const [choice, setChoice] = useState<ClientDecision>("confirm");
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const action = useAction(["decision", "next_follow_up", "reason", "note"]);
  const reasons = useFetch<Lookup[] | { results: Lookup[] }>(choice === "rejection" ? "/lookups/rejection-reasons/" : null);
  const list = Array.isArray(reasons.data) ? reasons.data : reasons.data?.results ?? [];
  const errors = { ...action.errors, ...local };
  async function save() {
    const found: Record<string, string> = {};
    if (choice === "waiting" && !date) found.next_follow_up = "client.err.date";
    if (choice === "rejection" && !reason) found.reason = "client.err.reason";
    setLocal(found);
    if (Object.keys(found).length) return;
    const body: Record<string, unknown> = { decision: choice, note: note.trim() };
    if (choice === "waiting") body.next_follow_up = date;
    if (choice === "rejection") body.reason = Number(reason);
    const saved = await action.run(() => api(`/clients/${clientId}/decide/`, { method: "POST", body }));
    if (saved) {
      toast.success(t("client.decision.done"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={t("client.decision.title")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("client.decision.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-body text-ink-2">{t("client.decision.text")}</p>
        <Segmented
          label={t("client.decision.choose")}
          value={choice}
          onChange={(v) => { setChoice(v); setLocal({}); }}
          segments={[{ value: "confirm", label: t("client.decision.confirm") }, { value: "waiting", label: t("client.decision.waiting") }, { value: "rejection", label: t("client.decision.rejection") }]}
        />
        <p className="text-label font-normal text-ink-2">{t(`client.decision.${choice}Hint`)}</p>
        {choice === "waiting" ? <Input name="next_follow_up" label={t("client.decision.date")} type="date" required value={date} onChange={(e) => { setDate(e.target.value); setLocal({}); }} error={errors.next_follow_up ? msg(errors.next_follow_up) : undefined} /> : null}
        {choice === "rejection" ? (
          <Select name="reason" label={t("client.decision.reason")} required value={reason} onChange={(e) => { setReason(e.target.value); setLocal({}); }} placeholder={t("client.decision.chooseReason")} options={list.map((r) => ({ value: String(r.id), label: lang === "ar" ? r.name_ar : r.name_en }))} error={errors.reason ? msg(errors.reason) : undefined} />
        ) : null}
        <Textarea name="note" label={t("client.decision.note")} rows={3} value={note} onChange={(e) => setNote(e.target.value)} error={errors.note} />
      </div>
    </Sheet>
  );
}
