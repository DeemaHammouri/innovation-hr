"use client";

import { WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Lead } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { isEmail, useForm } from "@/lib/useForm";

const DRAFT = "innovation.draft.lead";
const FIELDS = ["company_name", "contact_name", "phone", "email", "source", "notes"] as const;

function readDraft(): Record<string, string> | null {
  try {
    const raw = localStorage.getItem(DRAFT);
    return raw ? (JSON.parse(raw) as Record<string, string>) : null;
  } catch {
    return null;
  }
}
const writeDraft = (values: Record<string, string> | null) => {
  try {
    if (values) localStorage.setItem(DRAFT, JSON.stringify(values));
    else localStorage.removeItem(DRAFT);
  } catch {
    /* storage can be blocked; the form still works without a draft */
  }
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card as="section" className="p-5 md:p-6">
      <h2 className="text-section text-ink">{title}</h2>
      <div className="mt-5 space-y-5">{children}</div>
    </Card>
  );
}

export function LeadForm({ editing }: { editing: Lead | null }) {
  const { t, msg } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [duplicates, setDuplicates] = useState<string[]>([]);
  const [{ initial, restored }] = useState(() => {
    if (editing) return { initial: Object.fromEntries(FIELDS.map((f) => [f, editing[f] ?? ""])), restored: false };
    const draft = readDraft();
    const values = Object.fromEntries(FIELDS.map((f) => [f, draft?.[f] ?? ""]));
    return { initial: values, restored: FIELDS.some((f) => values[f]) };
  });
  const form = useForm(initial, (v) => ({
    ...(!v.company_name.trim() ? { company_name: "v.company" } : {}),
    ...(v.email.trim() && !isEmail(v.email.trim()) ? { email: "v.emailOptional" } : {}),
    ...(!v.phone.trim() && !v.email.trim() ? { phone: "Add a phone number or an email so someone can reach this lead." } : {}),
  }));

  // A new lead keeps what was typed, so leaving the page by accident costs nothing.
  const first = useRef(true);
  useEffect(() => {
    if (editing) return;
    if (first.current) {
      first.current = false;
      return;
    }
    writeDraft(FIELDS.some((f) => form.values[f]) ? form.values : null);
  }, [form.values, editing]);

  async function save(allowDuplicate: boolean) {
    setFormError("");
    setDuplicates([]);
    if (!form.check()) return;
    setSaving(true);
    try {
      const body = { ...form.values, ...(allowDuplicate ? { allow_duplicate: true } : {}) };
      const saved = await api<Lead>(editing ? `/leads/${editing.id}/` : "/leads/", { method: editing ? "PATCH" : "POST", body });
      if (!editing) writeDraft(null);
      toast.success(t(editing ? "lead.saved" : "lead.created"));
      router.push(`/leads/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const data = err.data as Record<string, unknown>;
        if (Array.isArray(data.duplicate)) {
          setDuplicates((data.duplicate as unknown[]).map(String));
        } else {
          const fields = err.fieldErrors();
          const known = [...FIELDS] as string[];
          form.setErrors(Object.fromEntries(known.filter((k) => fields[k]).map((k) => [k, fields[k]])));
          const firstBad = known.find((k) => fields[k]);
          if (firstBad) form.focusField(firstBad);
          else setFormError(fields.detail || "lead.fix");
        }
      } else {
        setFormError(err instanceof ApiError && err.status === 403 ? err.message : "lead.saveFailed");
      }
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(false); }} noValidate className="max-w-2xl space-y-4 md:space-y-6">
      {formError ? (
        <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">{msg(formError)}</p>
      ) : null}
      {restored ? <p role="status" className="rounded-control border border-primary-line bg-primary-tint p-3.5 text-label font-medium text-primary-hover">{t("lead.draftRestored")}</p> : null}
      {duplicates.length > 0 ? (
        <div role="alert" className="flex gap-3 rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
          <WarningCircle size={22} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
          <div className="min-w-0">
            <p className="text-body font-semibold">{t("lead.duplicateTitle")}</p>
            <p className="mt-1 text-label font-normal">{t("lead.duplicateText", { refs: duplicates.join(", ") })}</p>
            <Button variant="secondary" className="mt-3" loading={saving} onClick={() => void save(true)}>{t("lead.addAnyway")}</Button>
          </div>
        </div>
      ) : null}

      <Section title={t("lead.sectionCompany")}>
        <Input label={t("lead.companyName")} autoComplete="organization" required {...form.field("company_name")} />
        <Input label={t("lead.source")} hint={t("lead.sourceHint")} autoComplete="off" {...form.field("source")} />
      </Section>

      <Section title={t("lead.sectionContact")}>
        <Input label={t("lead.contactName")} autoComplete="off" {...form.field("contact_name")} />
        <div className="grid gap-5 sm:grid-cols-2">
          <Input label={t("common.phone")} type="tel" autoComplete="off" {...form.field("phone")} />
          <Input label={t("common.email")} type="email" autoComplete="off" {...form.field("email")} />
        </div>
      </Section>

      <Section title={t("lead.sectionNotes")}>
        <Textarea label={t("lead.notes")} rows={4} {...form.field("notes")} />
      </Section>

      <div className="sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 -mx-4 flex gap-3 border-t border-line bg-surface px-4 py-3 md:bottom-4 md:mx-0 md:justify-end md:rounded-card md:border md:shadow-float">
        <Link href={editing ? `/leads/${editing.id}` : "/leads"} className={buttonClass("secondary", "flex-1 md:flex-none")}>{t("common.cancel")}</Link>
        <Button type="submit" loading={saving} className="flex-1 md:flex-none">{t(editing ? "lead.save" : "lead.create")}</Button>
      </div>
    </form>
  );
}
