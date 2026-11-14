"use client";

import { PencilSimple, Plus, SlidersHorizontal } from "@phosphor-icons/react";
import { useState } from "react";
import { NoAccess } from "@/components/NoAccess";
import { Button, IconButton } from "@/components/ui/Button";
import { Card, StatusPill } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { Sheet } from "@/components/ui/Sheet";
import { EmptyState, ErrorState, RowsSkeleton, useDelayed } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, type ChecklistLookup, type Lookup, type ServiceLookup, type SlaSettings, type WorkHours, api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";

type Section = "reasons" | "services" | "checklist" | "hours" | "sla";
const SECTIONS: Section[] = ["reasons", "services", "checklist", "hours", "sla"];
const LIST_PATH = { reasons: "rejection-reasons", services: "services", checklist: "checklist-template" } as const;

type Row = Lookup & Partial<ServiceLookup> & Partial<ChecklistLookup>;

/** A bilingual lookup list. Values are switched off, never deleted, so old records keep their wording. */
function LookupList({ section }: { section: "reasons" | "services" | "checklist" }) {
  const { t, lang, msg, formatNumber } = useI18n();
  const toast = useToast();
  const path = `/lookups/${LIST_PATH[section]}/`;
  const { data, error, loading, reload } = useFetch<Row[]>(path);
  const show = useDelayed(loading);
  const [editing, setEditing] = useState<Row | "new" | null>(null);
  const [form, setForm] = useState({ name_en: "", name_ar: "", price: "", required: true });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  function open(row: Row | "new") {
    setEditing(row);
    setErrors({});
    setForm(
      row === "new"
        ? { name_en: "", name_ar: "", price: "", required: true }
        : { name_en: row.name_en, name_ar: row.name_ar, price: row.default_unit_price ?? "", required: row.required ?? true },
    );
  }

  async function save() {
    const next: Record<string, string> = {};
    if (!form.name_en.trim()) next.name_en = "Enter the English name.";
    if (!form.name_ar.trim()) next.name_ar = "Enter the Arabic name.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const body: Record<string, unknown> = { name_en: form.name_en, name_ar: form.name_ar };
    if (section === "services") body.default_unit_price = form.price === "" ? null : form.price;
    if (section === "checklist") body.required = form.required;
    setBusy(true);
    try {
      if (editing === "new") await api(path, { method: "POST", body });
      else if (editing) await api(`${path}${editing.id}/`, { method: "PATCH", body });
      setEditing(null);
      reload();
      toast.success(t("lookups.saved"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) setErrors(e.fieldErrors());
      else toast.error(msg(errorMessage(e)));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(row: Row) {
    try {
      await api(`${path}${row.id}/`, { method: "PATCH", body: { is_active: !row.is_active } });
      reload();
      toast.success(row.is_active ? t("lookups.switchedOff") : t("lookups.switchedOn"));
    } catch (e) {
      toast.error(msg(errorMessage(e)));
    }
  }

  if (error) return <ErrorState message={error} onRetry={reload} />;
  const name = (r: Row) => (lang === "ar" ? r.name_ar : r.name_en);
  const other = (r: Row) => (lang === "ar" ? r.name_en : r.name_ar);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="max-w-md text-label font-normal text-ink-2">{t(`lookups.${section}.help`)}</p>
        <Button icon={<Plus size={20} aria-hidden />} onClick={() => open("new")}>
          {t("lookups.add")}
        </Button>
      </div>
      {!data ? (
        show ? <RowsSkeleton rows={4} /> : null
      ) : data.length === 0 ? (
        <Card>
          <EmptyState compact icon={<SlidersHorizontal size={24} aria-hidden />} title={t("lookups.emptyTitle")} description={t("lookups.emptyText")} />
        </Card>
      ) : (
        <Card as="section" className="overflow-hidden">
          <ul className="divide-y divide-line">
            {data.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className={`truncate text-body ${r.is_active ? "text-ink" : "text-ink-3"}`}>{name(r)}</p>
                  <p className="truncate text-label font-normal text-ink-2">
                    {other(r)}
                    {section === "services" && r.default_unit_price ? ` · ${formatNumber(Number(r.default_unit_price))} ${r.currency}` : ""}
                    {section === "checklist" ? ` · ${r.required ? t("lookups.required") : t("lookups.optional")}` : ""}
                  </p>
                </div>
                {r.is_active ? null : <StatusPill tone="neutral">{t("lookups.off")}</StatusPill>}
                <Button variant="ghost" onClick={() => toggle(r)}>
                  {r.is_active ? t("lookups.switchOff") : t("lookups.switchOn")}
                </Button>
                <IconButton label={t("common.edit")} onClick={() => open(r)}>
                  <PencilSimple size={20} aria-hidden />
                </IconButton>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Sheet
        open={editing !== null}
        title={editing === "new" ? t("lookups.addTitle") : t("lookups.editTitle")}
        onClose={() => setEditing(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={save} loading={busy}>
              {t("lookups.save")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input name="name_en" label={t("lookups.nameEn")} lang="en" value={form.name_en} error={errors.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} />
          <Input name="name_ar" label={t("lookups.nameAr")} lang="ar" value={form.name_ar} error={errors.name_ar} onChange={(e) => setForm({ ...form, name_ar: e.target.value })} />
          {section === "services" ? (
            <Input
              name="price"
              label={t("lookups.price")}
              hint={t("lookups.priceHint")}
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              ltr
              value={form.price}
              error={errors.default_unit_price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
            />
          ) : null}
          {section === "checklist" ? (
            <label className="flex min-h-11 items-center gap-3 text-body text-ink">
              <input type="checkbox" className="size-5 accent-[var(--color-primary-strong)]" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} />
              {t("lookups.requiredFlag")}
            </label>
          ) : null}
        </div>
      </Sheet>
    </div>
  );
}

/** Work hours and the lead SLA are single settings, not lists. */
function SettingsForm({ section }: { section: "hours" | "sla" }) {
  const { t, msg } = useI18n();
  const toast = useToast();
  const path = section === "hours" ? "/lookups/work-hours/" : "/lookups/sla/";
  const { data, error, loading, reload } = useFetch<WorkHours & SlaSettings>(path);
  const show = useDelayed(loading);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return show ? <RowsSkeleton rows={3} /> : null;

  const fields =
    section === "hours"
      ? ([
          { key: "work_start", type: "time" },
          { key: "work_end", type: "time" },
          { key: "grace_minutes", type: "number" },
        ] as const)
      : ([
          { key: "first_contact_hours", type: "number" },
          { key: "follow_up_days", type: "number" },
        ] as const);
  const value = (k: string) => draft[k] ?? String((data as unknown as Record<string, string | number>)[k]).slice(0, k.startsWith("work_") ? 5 : undefined);

  async function save() {
    if (Object.keys(draft).length === 0) {
      toast.success(t("lookups.saved")); // nothing changed, so there is nothing to send
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      await api(path, { method: "PATCH", body: draft });
      setDraft({});
      reload();
      toast.success(t("lookups.saved"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) setErrors(e.fieldErrors());
      else toast.error(msg(errorMessage(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-lg space-y-4 p-5">
      <p className="text-label font-normal text-ink-2">{t(`lookups.${section}.help`)}</p>
      {fields.map((f) => (
        <Input
          key={f.key}
          name={f.key}
          label={t(`lookups.field.${f.key}`)}
          type={f.type}
          ltr
          min={f.type === "number" ? "0" : undefined}
          value={value(f.key)}
          error={errors[f.key]}
          onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
        />
      ))}
      <div className="flex justify-end">
        <Button onClick={save} loading={busy}>
          {t("lookups.save")}
        </Button>
      </div>
    </Card>
  );
}

export default function LookupsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [section, setSection] = useState<Section>("reasons");
  if (!user) return null;
  if (user.role_key !== "ceo") return <NoAccess />;

  const options = SECTIONS.map((s) => ({ value: s, label: t(`lookups.section.${s}`) }));
  return (
    <>
      <PageHeader title={t("lookups.title")} description={t("lookups.description")} />
      <div className="mb-5 md:hidden">
        <Select name="section" label={t("lookups.sectionLabel")} value={section} options={options} onChange={(e) => setSection(e.target.value as Section)} />
      </div>
      <div className="mb-5 hidden md:block">
        <Segmented segments={options} value={section} onChange={setSection} label={t("lookups.sectionLabel")} mode="tablist" className="w-fit" />
      </div>
      <div className="max-w-2xl">
        {section === "hours" || section === "sla" ? <SettingsForm key={section} section={section} /> : <LookupList key={section} section={section} />}
      </div>
    </>
  );
}
