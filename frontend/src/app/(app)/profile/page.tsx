"use client";

import { SignOut } from "@phosphor-icons/react";
import { LanguageSwitcher } from "@/components/shell/LanguageSwitcher";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { type DashboardSummary } from "@/lib/api";
import { useAuth, useSignOut } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { useUrlParams } from "@/lib/useUrlParams";

type Tab = "overview" | "settings";

export default function ProfilePage() {
  const { user } = useAuth();
  const { t, dept, role, formatDateTime } = useI18n();
  const signOut = useSignOut();
  const [params, setParams] = useUrlParams(["tab"] as const);
  const tab: Tab = params.tab === "settings" ? "settings" : "overview";
  const { data } = useFetch<DashboardSummary>("/dashboard/summary/");
  if (!user) return null;
  const last = data?.my_sign_ins[0];

  return (
    <>
      <PageHeader title={t("profile.title")} />

      <Card className="mb-5 flex flex-wrap items-center gap-4 p-5 md:mb-6 md:p-6">
        <Avatar name={user.full_name} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-title text-ink">{user.full_name}</h2>
          <p className="mt-0.5 text-body text-ink-2">
            {dept(user.department_name)} · {role(user.role)}
          </p>
          <div className="mt-2">
            <StatusPill tone={user.is_active ? "success" : "neutral"}>{user.is_active ? t("common.active") : t("common.inactive")}</StatusPill>
          </div>
        </div>
      </Card>

      <Segmented<Tab>
        mode="tablist"
        label={t("profile.title")}
        value={tab}
        onChange={(v) => setParams({ tab: v === "settings" ? "settings" : "" })}
        className="mb-5 w-full max-w-xs md:mb-6"
        segments={[
          { value: "overview", label: t("profile.overview"), id: "tab-overview", controls: "panel-overview" },
          { value: "settings", label: t("common.settings"), id: "tab-settings", controls: "panel-settings" },
        ]}
      />

      {tab === "overview" ? (
        <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" className="max-w-2xl animate-fade-in space-y-5 md:space-y-6">
          <InsetList title={t("profile.personal")}>
            <InsetRow label={t("profile.fullName")}>{user.full_name}</InsetRow>
            <InsetRow label={t("common.email")} ltr>{user.email}</InsetRow>
          </InsetList>
          <InsetList title={t("users.sectionOrg")}>
            <InsetRow label={t("common.department")}>{dept(user.department_name)}</InsetRow>
            <InsetRow label={t("common.role")}>{role(user.role)}</InsetRow>
          </InsetList>
          <InsetList title={t("users.sectionActivity")}>
            <InsetRow label={t("profile.lastSignIn")}>{last ? formatDateTime(last.timestamp) : t("common.none")}</InsetRow>
          </InsetList>
        </div>
      ) : (
        <div id="panel-settings" role="tabpanel" aria-labelledby="tab-settings" className="max-w-2xl animate-fade-in space-y-5 md:space-y-6">
          <Card as="section" className="p-5 md:p-6" aria-labelledby="set-language">
            <h2 id="set-language" className="text-section text-ink">{t("settings.languageTitle")}</h2>
            <p className="mt-1 text-body text-ink-2">{t("settings.languageText")}</p>
            <div className="mt-4">
              <LanguageSwitcher className="w-full max-w-xs" />
            </div>
          </Card>

          <Card as="section" className="p-5 md:p-6" aria-labelledby="set-password">
            <h2 id="set-password" className="text-section text-ink">{t("settings.passwordTitle")}</h2>
            <p className="mt-1 text-body text-ink-2">{t("settings.passwordText")}</p>
          </Card>

          <Card as="section" className="p-5 md:p-6" aria-labelledby="set-signout">
            <h2 id="set-signout" className="text-section text-ink">{t("settings.signOutTitle")}</h2>
            <p className="mt-1 text-body text-ink-2">{t("settings.signOutText")}</p>
            <Button variant="secondary" className="mt-4 text-danger-ink" icon={<SignOut size={20} className="rtl:-scale-x-100" aria-hidden />} onClick={signOut}>
              {t("common.signOut")}
            </Button>
          </Card>
        </div>
      )}
    </>
  );
}
