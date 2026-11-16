"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { buttonClass, Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type Department, type User } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { isEmail, useForm } from "@/lib/useForm";
import { CredentialsSheet, type Credentials } from "./UserActions";

const rolesFor = (department?: string) => (department === "Administration" ? ["head"] : ["member", "head"]);

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card as="section" className="p-5 md:p-6">
      <h2 className="text-section text-ink">{title}</h2>
      {description ? <p className="mt-1 text-body text-ink-2">{description}</p> : null}
      <div className="mt-5 space-y-5">{children}</div>
    </Card>
  );
}

export function UserForm({ editing, me }: { editing: User | null; me: User }) {
  const { t, msg, dept, role, lang } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [deptFailed, setDeptFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [credentials, setCredentials] = useState<(Credentials & { id: number }) | null>(null);
  const isSelf = editing?.id === me.id;

  const form = useForm(
    {
      full_name: editing?.full_name ?? "",
      email: editing?.email ?? "",
      department: editing?.department ? String(editing.department) : "",
      role: editing?.role ?? "member",
      preferred_language: editing?.preferred_language ?? lang,
    } as Record<string, string>,
    (v) => ({
      ...(!v.full_name.trim() ? { full_name: "v.fullName" } : {}),
      ...(!v.email.trim() ? { email: "v.theirEmail" } : !isEmail(v.email.trim()) ? { email: "v.emailFormat" } : {}),
      ...(!v.department ? { department: "v.chooseDept" } : {}),
      ...(!v.role ? { role: "v.chooseRole" } : {}),
    }),
  );

  useEffect(() => {
    api<Department[]>("/departments/").then(setDepartments).catch(() => setDeptFailed(true));
  }, []);

  const selectedDept = departments.find((d) => String(d.id) === form.values.department)?.name;
  const allowedRoles = rolesFor(selectedDept);

  function chooseDepartment(e: { target: { value: string } }) {
    const id = e.target.value;
    form.setValue("department", id);
    const name = departments.find((d) => String(d.id) === id)?.name;
    if (!rolesFor(name).includes(form.values.role)) form.setValue("role", rolesFor(name)[0]);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.check()) return;
    setSaving(true);
    const v = form.values;
    const body: Record<string, unknown> = {
      full_name: v.full_name.trim(),
      email: v.email.trim(),
      department: Number(v.department),
      role: v.role,
      preferred_language: v.preferred_language,
    };
    try {
      const saved = await api<User & { temporary_password?: string }>(editing ? `/users/${editing.id}/` : "/users/", { method: editing ? "PATCH" : "POST", body });
      if (editing) {
        toast.success(t("users.saved"));
        router.push(`/users/${editing.id}`);
      } else {
        setCredentials({ id: saved.id, name: saved.full_name, email: saved.email, password: saved.temporary_password ?? "", reason: "users.credAdded" });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const fields = err.fieldErrors();
        const known = Object.keys(v);
        form.setErrors(Object.fromEntries(known.filter((k) => fields[k]).map((k) => [k, fields[k]])));
        const first = known.find((k) => fields[k]);
        if (first) form.focusField(first);
        else setFormError(fields.detail ?? fields.non_field_errors ?? "users.checkDetails");
      } else {
        setFormError("users.saveFailed");
      }
    } finally {
      setSaving(false);
    }
  }

  const backHref = editing ? `/users/${editing.id}` : "/users";
  const roleHint =
    isSelf ? t("users.selfRole") : selectedDept === "Administration" ? t("users.adminHint") : selectedDept === "Marketing" ? t("users.marketingHint") : undefined;

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-2xl space-y-4 md:space-y-6">
      {formError || deptFailed ? (
        <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">
          {msg(formError || "users.deptLoadFailed")}
        </p>
      ) : null}

      <Section title={t("users.sectionPersonal")}>
        <Input label={t("users.fullName")} autoComplete="off" required {...form.field("full_name")} />
        <Input label={t("common.email")} type="email" autoComplete="off" required {...form.field("email")} />
      </Section>

      <Section title={t("users.sectionAccount")} description={undefined}>
        {!editing ? <p className="text-label text-ink-2">{t("users.tempHintServer")}</p> : null}
        <Select
          label={t("users.language")}
          required
          options={[
            { value: "en", label: "English" },
            { value: "ar", label: "العربية" },
          ]}
          hint={t("users.languageHint")}
          {...form.field("preferred_language")}
        />
      </Section>

      <Section title={t("users.sectionOrg")}>
        <Select
          label={t("common.department")}
          required
          placeholder={t("users.chooseDept")}
          options={departments.map((d) => ({ value: String(d.id), label: dept(d.name) }))}
          disabled={isSelf}
          hint={isSelf ? t("users.selfDept") : undefined}
          {...form.field("department")}
          onChange={chooseDepartment}
        />
        <Select
          label={t("common.role")}
          required
          options={allowedRoles.map((r) => ({ value: r, label: role(r) }))}
          disabled={isSelf}
          hint={roleHint}
          {...form.field("role")}
        />
      </Section>

      {/* Stays in reach while the form scrolls. On phones it sits just above the tab bar. */}
      <div className="sticky bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 -mx-4 flex gap-3 border-t border-line bg-surface px-4 py-3 md:bottom-4 md:mx-0 md:justify-end md:rounded-card md:border md:shadow-float">
        <Link href={backHref} className={buttonClass("secondary", "flex-1 md:flex-none")}>
          {t("common.cancel")}
        </Link>
        <Button type="submit" loading={saving} className="flex-1 md:flex-none">
          {editing ? t("users.save") : t("users.create")}
        </Button>
      </div>

      <CredentialsSheet
        credentials={credentials}
        onClose={() => {
          const id = credentials?.id;
          setCredentials(null);
          router.push(id ? `/users/${id}` : "/users");
        }}
      />
    </form>
  );
}
