"use client";

import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { Button } from "@/components/ui/Button";
import { Select, Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { api, type OpAssignee, type Project } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

/** The Operation head chooses the one primary employee (a reason is required to replace them) and any support people. */
export function StaffSheet({ project, onClose, onDone }: { project: Project; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { data: people } = useFetch<OpAssignee[]>("/operations/assignees/");
  const primary = project.staff.find((s) => s.role === "primary" && !s.ended_at);
  const support = project.staff.filter((s) => s.role === "support" && !s.ended_at);
  const [who, setWho] = useState("");
  const [reason, setReason] = useState("");
  const [sup, setSup] = useState("");
  const a = useAction(["user", "reason"]);
  const b = useAction(["user"]);
  const call = (path: string, body: object) => api<Project>(`/projects/${project.id}/${path}/`, { method: "POST", body });
  async function savePrimary() {
    if (!who) return void a.setErrors({ user: "prj.err.person" });
    if (primary && !reason.trim()) return void a.setErrors({ reason: "prj.err.reason" });
    if (await a.run(() => call("primary", { user: Number(who), reason }))) {
      a.setSaving(false); // the sheet stays open for the next change
      setWho("");
      setReason("");
      toast.success(t("prj.staffSaved"));
      onDone();
    }
  }
  async function addSupport() {
    if (!sup) return void b.setErrors({ user: "prj.err.person" });
    if (await b.run(() => call("support", { user: Number(sup) }))) {
      b.setSaving(false);
      setSup("");
      toast.success(t("prj.staffSaved"));
      onDone();
    }
  }
  async function remove(user: number) {
    if (await b.run(() => call("remove", { user }))) {
      b.setSaving(false);
      toast.success(t("prj.staffSaved"));
      onDone();
    }
  }
  const options = (people ?? []).filter((p) => !project.staff.some((s) => s.user === p.id && !s.ended_at));
  const pick = (id: string, set: (v: string) => void, error?: string) => (
    <Select name="user" label={t("prj.person")} value={id} onChange={(e) => set(e.target.value)} error={error} placeholder={t("prj.pickPerson")} options={options.map((p) => ({ value: String(p.id), label: p.full_name }))} />
  );
  return (
    <Sheet open onClose={onClose} title={t("prj.staff")} footer={<Button onClick={onClose}>{t("common.done")}</Button>}>
      <div className="space-y-6">
        <section className="space-y-3">
          <h3 className="text-body font-semibold text-ink">{t("prj.primary")}</h3>
          <p className="text-label font-normal text-ink-2">{primary ? primary.name : t("prj.noPrimary")}</p>
          <FormError message={a.formError} />
          {pick(who, setWho, a.errors.user)}
          {primary ? <Textarea name="reason" label={t("prj.reason")} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} error={a.errors.reason} /> : null}
          <Button loading={a.saving} onClick={savePrimary}>{primary ? t("prj.replacePrimary") : t("prj.assignPrimary")}</Button>
        </section>
        <section className="space-y-3">
          <h3 className="text-body font-semibold text-ink">{t("prj.support")}</h3>
          <FormError message={b.formError} />
          <ul className="divide-y divide-line">
            {support.map((s) => (
              <li key={s.user} className="flex items-center justify-between gap-2 py-2">
                <span className="text-body text-ink">{s.name}</span>
                <Button variant="secondary" onClick={() => remove(s.user)}>{t("prj.removeSupport")}</Button>
              </li>
            ))}
          </ul>
          {pick(sup, setSup, b.errors.user)}
          <Button variant="secondary" loading={b.saving} onClick={addSupport}>{t("prj.addSupport")}</Button>
        </section>
      </div>
    </Sheet>
  );
}
