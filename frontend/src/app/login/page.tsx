"use client";

import { ArrowRight, Check } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/shell/LanguageSwitcher";
import { LogoMark } from "@/components/shell/Logo";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { PageTitle } from "@/components/ui/PageTitle";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useForm } from "@/lib/useForm";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const { t, msg } = useI18n();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const form = useForm({ email: "", password: "" }, (v) => ({
    ...(!v.email.trim() ? { email: "v.enterIdentifier" } : {}),
    ...(!v.password ? { password: "v.enterPassword" } : {}),
  }));

  useEffect(() => {
    if (!loading && user) router.replace(user.must_change_password ? "/set-password" : "/");
  }, [loading, user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.check()) return;
    setSubmitting(true);
    try {
      const signedIn = await login(form.values.email.trim(), form.values.password);
      router.replace(signedIn.must_change_password ? "/set-password" : "/");
    } catch (err) {
      setFormError(err instanceof ApiError && err.status === 401 ? "login.mismatch" : err instanceof ApiError && err.status === 429 ? "p8.api.0" : "login.failed");
      setSubmitting(false);
    }
  }

  const points = ["login.point1", "login.point2", "login.point3"];

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <PageTitle>{t("login.pageTitle")}</PageTitle>

      {/* Navy panel. Start side on desktop, a compact header on phones. */}
      <section className="grid-texture relative flex flex-col bg-navy px-6 py-6 text-on-navy lg:px-14 lg:py-12">
        <div className="flex items-center gap-3">
          <LogoMark size={40} />
          <span className="text-section text-on-navy">{t("brand.name")}</span>
        </div>
        <div className="mt-8 lg:my-auto lg:py-16">
          <h2 className="max-w-md text-title font-bold text-white lg:text-[length:var(--text-large-title)]">{t("login.headline")}</h2>
          <ul className="mt-8 hidden space-y-4 lg:block">
            {points.map((p) => (
              <li key={p} className="flex items-start gap-3 text-body text-on-navy">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-navy-2 text-primary">
                  <Check size={14} weight="bold" aria-hidden />
                </span>
                {t(p)}
              </li>
            ))}
          </ul>
        </div>
        <p className="hidden text-caption text-on-navy-muted lg:block">{t("brand.company")}</p>
      </section>

      <section className="relative flex flex-col bg-surface px-6 py-8 lg:px-14">
        <div className="flex justify-end">
          <LanguageSwitcher />
        </div>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <h1 className="text-large-title text-ink">{t("login.title")}</h1>
          <p className="mt-1 text-body text-ink-2">{t("login.subtitle")}</p>

          <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
            {formError ? (
              <p role="alert" className="rounded-control border border-danger/25 bg-danger-bg p-3.5 text-label font-medium text-danger-ink">
                {msg(formError)}
              </p>
            ) : null}
            <Input label={t("login.identifier")} type="text" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="username" required {...form.field("email")} />
            <Input label={t("login.password")} type="password" autoComplete="current-password" required {...form.field("password")} />
            <Button type="submit" className="w-full" loading={submitting}>
              {t("common.signIn")}
              <ArrowRight size={20} className="rtl:-scale-x-100" aria-hidden />
            </Button>
          </form>
          <p className="mt-6 text-label font-normal text-ink-2">{t("login.note")}</p>
        </div>
      </section>
    </main>
  );
}
