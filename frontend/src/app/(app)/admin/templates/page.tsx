"use client";

import { Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { FormError, useAction } from "@/components/leads/LeadSheets";
import { NoAccess } from "@/components/NoAccess";
import { Button } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, type ContractTemplate } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { can } from "@/lib/can";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

const COUNTRIES = ["*", "JO", "SA", "AE", "KW", "QA", "BH", "OM", "EG", "LB", "IQ", "PS", "OTHER"];

/** The wording of a contract for each country. A contract is prefilled from the template of its client's country, or the default (*). */
export default function TemplatesPage() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const allowed = !!user && can(user, "contract.template");
  const { data, error, reload } = useFetch<ContractTemplate[] | { results: ContractTemplate[] }>(allowed ? "/contract-templates/" : null);
  const [editing, setEditing] = useState<ContractTemplate | "new" | null>(null);
  if (!user) return null;
  if (!allowed) return <NoAccess />;
  const list = Array.isArray(data) ? data : data?.results ?? [];
  return (
    <>
      <PageHeader title={t("tpl.title")} description={t("tpl.description")} action={<Button icon={<Plus size={18} aria-hidden />} onClick={() => setEditing("new")}>{t("tpl.add")}</Button>} />
      {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <Skeleton className="h-40 max-w-2xl rounded-card" /> : (
        <Card className="max-w-2xl overflow-hidden">
          <ul className="divide-y divide-line">
            {list.map((x) => (
              <li key={x.id}>
                <button type="button" onClick={() => setEditing(x)} className="flex w-full items-center gap-3 px-4 py-3.5 text-start hover:bg-canvas/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body font-semibold text-ink">{lang === "ar" ? x.name_ar : x.name_en}</p>
                    <p className="text-label font-normal text-ink-2">{x.country === "*" ? t("tpl.default") : x.country}</p>
                  </div>
                  <StatusPill tone={x.is_active ? "success" : "neutral"}>{t(x.is_active ? "common.active" : "common.inactive")}</StatusPill>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {editing ? <EditSheet item={editing === "new" ? null : editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); reload(); }} /> : null}
    </>
  );
}

function EditSheet({ item, onClose, onDone }: { item: ContractTemplate | null; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const action = useAction(["country", "name_en", "name_ar", "body_en", "body_ar"]);
  const [f, setF] = useState({ country: item?.country ?? "JO", name_en: item?.name_en ?? "", name_ar: item?.name_ar ?? "", body_en: item?.body_en ?? "", body_ar: item?.body_ar ?? "", is_active: item?.is_active ?? true });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  async function save() {
    const saved = await action.run(() => (item ? api(`/contract-templates/${item.id}/`, { method: "PATCH", body: f }) : api("/contract-templates/", { method: "POST", body: f })));
    if (saved) {
      toast.success(t("tpl.saved"));
      onDone();
    }
  }
  return (
    <Sheet open onClose={onClose} title={item ? t("tpl.edit") : t("tpl.add")} footer={<><Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button><Button loading={action.saving} onClick={save}>{t("common.save")}</Button></>}>
      <div className="space-y-4">
        <FormError message={action.formError} />
        <p className="text-label font-normal text-ink-2">{t("tpl.placeholders")}</p>
        <Select name="country" label={t("tpl.country")} required value={f.country} onChange={set("country")} options={COUNTRIES.map((c) => ({ value: c, label: c === "*" ? t("tpl.default") : c }))} error={action.errors.country} />
        <Input name="name_en" label={t("tpl.nameEn")} required value={f.name_en} onChange={set("name_en")} error={action.errors.name_en} />
        <Input name="name_ar" label={t("tpl.nameAr")} required dir="rtl" value={f.name_ar} onChange={set("name_ar")} error={action.errors.name_ar} />
        <Textarea name="body_en" label={t("ct.draft.bodyEn")} rows={8} dir="ltr" value={f.body_en} onChange={set("body_en")} error={action.errors.body_en} />
        <Textarea name="body_ar" label={t("ct.draft.bodyAr")} rows={8} dir="rtl" value={f.body_ar} onChange={set("body_ar")} error={action.errors.body_ar} />
      </div>
    </Sheet>
  );
}
