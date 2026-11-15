"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Client } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { isEmail, useForm } from "@/lib/useForm";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card as="section" className="p-5 md:p-6">
      <h2 className="text-section text-ink">{title}</h2>
      <div className="mt-5 space-y-5">{children}</div>
    </Card>
  );
}

export function ClientForm({ editing }: { editing: Client | null }) {
  const { t, msg } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const form = useForm(
    {
      company_name: editing?.company_name ?? "",
      contact_person: editing?.contact_person ?? "",
      phone: editing?.phone ?? "",
      email: editing?.email ?? "",
      address: editing?.address ?? "",
      notes: editing?.notes ?? "",
    } as Record<string, string>,
    (v) => ({
      ...(!v.company_name.trim() ? { company_name: "v.company" } : {}),
      ...(v.email.trim() && !isEmail(v.email.trim()) ? { email: "v.emailOptional" } : {}),
    }),
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.check()) return;
    setSaving(true);
    try {
      const saved = await api<Client>(editing ? `/clients/${editing.id}/` : "/clients/", { method: editing ? "PATCH" : "POST", body: editing ? { ...form.values, expected_updated_at: editing.updated_at } : form.values });
      toast.success(t("clients.saved"));
      router.push(`/clients/${saved.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const fields = err.fieldErrors();
        const known = Object.keys(form.values);
        form.setErrors(Object.fromEntries(known.filter((k) => fields[k]).map((k) => [k, fields[k]])));
        const first = known.find((k) => fields[k]);
        if (first) form.focusField(first);
        else setFormError("users.checkDetails");
      } else {
        setFormError(err instanceof ApiError && err.status === 409 ? err.message : "clients.saveFailed");
      }
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-4 md:space-y-6">
      {formError ? (
        <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">
          {msg(formError)}
        </p>
      ) : null}

      <Section title={t("clients.sectionCompany")}>
        <Input label={t("clients.companyName")} autoComplete="organization" required {...form.field("company_name")} />
        <Textarea label={t("clients.address")} {...form.field("address")} />
      </Section>

      <Section title={t("clients.sectionContact")}>
        <Input label={t("clients.contactPerson")} autoComplete="off" {...form.field("contact_person")} />
        <div className="grid gap-5 sm:grid-cols-2">
          <Input label={t("common.phone")} type="tel" autoComplete="off" {...form.field("phone")} />
          <Input label={t("common.email")} type="email" autoComplete="off" {...form.field("email")} />
        </div>
      </Section>

      <Section title={t("clients.notes")}>
        <Textarea label={t("clients.notes")} rows={5} {...form.field("notes")} />
      </Section>

      <div className="sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 -mx-4 flex gap-3 border-t border-line bg-surface px-4 py-3 md:bottom-4 md:mx-0 md:justify-end md:rounded-card md:border md:shadow-float">
        <Link href={editing ? `/clients/${editing.id}` : "/clients"} className={buttonClass("secondary", "flex-1 md:flex-none")}>
          {t("common.cancel")}
        </Link>
        <Button type="submit" loading={saving} className="flex-1 md:flex-none">
          {editing ? t("clients.save") : t("clients.create")}
        </Button>
      </div>
    </form>
  );
}
