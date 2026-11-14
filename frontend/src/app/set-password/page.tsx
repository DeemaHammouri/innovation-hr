"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/shell/LanguageSwitcher";
import { LogoMark } from "@/components/shell/Logo";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { PageTitle } from "@/components/ui/PageTitle";
import { PasswordChecklist } from "@/components/ui/PasswordChecklist";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError, type User } from "@/lib/api";
import { forgetTemporaryPassword, getTemporaryPassword, useAuth, useSignOut } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useForm } from "@/lib/useForm";

export default function SetPasswordPage() {
  const { user, loading, setUser } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const signOut = useSignOut();
  const { t, msg } = useI18n();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const form = useForm({ new_password: "", confirm_password: "" }, (v) => ({
    ...(v.new_password.length < 8 ? { new_password: "v.min8" } : {}),
    ...(!v.confirm_password ? { confirm_password: "v.typeAgain" } : v.confirm_password !== v.new_password ? { confirm_password: "v.mismatch" } : {}),
  }));

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (!user.must_change_password) router.replace("/");
  }, [loading, user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.check()) return;
    setSubmitting(true);
    try {
      const updated = await api<User>("/auth/change-password/", { method: "POST", body: form.values });
      forgetTemporaryPassword();
      setUser(updated);
      toast.success(t("setpw.done"));
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const fields = err.fieldErrors();
        form.setErrors({ new_password: fields.new_password, confirm_password: fields.confirm_password });
      } else {
        setFormError("setpw.failed");
      }
      setSubmitting(false);
    }
  }

  const temporary = getTemporaryPassword();
  const { new_password, confirm_password } = form.values;

  return (
    <main className="flex min-h-dvh flex-col bg-canvas px-4 py-5">
      <PageTitle>{t("setpw.title")}</PageTitle>
      <div className="flex justify-end">
        <LanguageSwitcher />
      </div>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-8">
        <div className="mb-6 flex justify-center">
          <LogoMark size={44} />
        </div>
        <div className="rounded-sheet border border-line bg-surface p-6 md:p-8">
          <h1 className="text-title text-ink">{t("setpw.title")}</h1>
          <p className="mt-1 text-body text-ink-2">{t("setpw.subtitle")}</p>
          <form onSubmit={onSubmit} noValidate className="mt-6 space-y-5">
            {formError ? (
              <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">
                {msg(formError)}
              </p>
            ) : null}
            <Input label={t("setpw.new")} type="password" autoComplete="new-password" required {...form.field("new_password")} />
            <Input label={t("setpw.confirm")} type="password" autoComplete="new-password" required {...form.field("confirm_password")} />
            <PasswordChecklist
              password={new_password}
              confirm={confirm_password}
              sameAsTemporary={temporary ? new_password === temporary : undefined}
            />
            <Button type="submit" className="w-full" loading={submitting}>
              {t("setpw.save")}
            </Button>
            <Button variant="ghost" className="w-full" onClick={signOut}>
              {t("common.signOut")}
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
