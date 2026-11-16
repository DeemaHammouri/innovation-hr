"use client";

import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { NoAccess } from "@/components/NoAccess";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { type CompanyProfile, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

export default function CompanyPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const allowed = !!user && can(user, "company.manage");
  const { data, error, reload } = useFetch<CompanyProfile>(allowed ? "/company/" : null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("company.title")} description={t("company.description")} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <Skeleton className="h-64 max-w-2xl rounded-card" /> : <CompanyForm key={data.updated_at} data={data} onSaved={reload} />}
    </>
  );
}

function CompanyForm({ data, onSaved }: { data: CompanyProfile; onSaved: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["name_en", "name_ar", "quotation_prefix", "contract_prefix", "stamp"]);
  const [v, setV] = useState({ name_en: data.name_en, name_ar: data.name_ar, quotation_prefix: data.quotation_prefix, contract_prefix: data.contract_prefix });
  const [stamp, setStamp] = useState<File | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    const form = new FormData();
    Object.entries(v).forEach(([k, val]) => form.append(k, val));
    if (stamp) form.append("stamp", stamp);
    const saved = await action.run(() => upload<CompanyProfile>("/company/", form, "PATCH"));
    if (saved) {
      toast.success(t("company.saved"));
      onSaved();
    }
  }
  return (
    <form onSubmit={save} noValidate className="max-w-2xl space-y-5">
      <FormError message={action.formError} />
      <Card as="section" className="space-y-5 p-5 md:p-6">
        <div className="grid gap-5 sm:grid-cols-2">
          <Input name="name_en" label={t("company.nameEn")} value={v.name_en} onChange={(e) => setV({ ...v, name_en: e.target.value })} error={action.errors.name_en} required />
          <Input name="name_ar" label={t("company.nameAr")} value={v.name_ar} onChange={(e) => setV({ ...v, name_ar: e.target.value })} error={action.errors.name_ar} required />
          <Input name="quotation_prefix" label={t("company.quotationPrefix")} ltr hint={t("company.prefixHint")} value={v.quotation_prefix} onChange={(e) => setV({ ...v, quotation_prefix: e.target.value.toUpperCase() })} error={action.errors.quotation_prefix} required />
          <Input name="contract_prefix" label={t("company.contractPrefix")} ltr value={v.contract_prefix} onChange={(e) => setV({ ...v, contract_prefix: e.target.value.toUpperCase() })} error={action.errors.contract_prefix} required />
        </div>
        <div>
          <label htmlFor="field-stamp" className="mb-1.5 block text-label text-ink">{t("company.stamp")}</label>
          <input id="field-stamp" name="stamp" type="file" accept="image/png" onChange={(e) => setStamp(e.target.files?.[0] ?? null)} className="block w-full text-body text-ink file:me-3 file:rounded-control file:border file:border-line file:bg-surface file:px-3 file:py-2" />
          <p className={`mt-2 text-label ${data.has_stamp ? "text-ink-2" : "font-medium text-warning-ink"}`}>{t(data.has_stamp ? "company.stampHas" : "company.stampNone")}</p>
          {action.errors.stamp ? <p role="alert" className="mt-1 text-label font-medium text-danger-ink">{action.errors.stamp}</p> : null}
        </div>
      </Card>
      <div className="flex justify-end"><Button type="submit" loading={action.saving}>{t("company.save")}</Button></div>
    </form>
  );
}
