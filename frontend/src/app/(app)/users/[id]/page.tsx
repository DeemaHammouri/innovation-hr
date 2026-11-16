"use client";

import { LockKey, Pencil, UserCheck, UserMinus } from "@phosphor-icons/react";
import { can } from "@/lib/can";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { NoAccess } from "@/components/NoAccess";
import { useUserActions } from "@/components/users/UserActions";
import { Avatar } from "@/components/ui/Avatar";
import { Button, buttonClass } from "@/components/ui/Button";
import { InsetList, InsetRow, StatusPill } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Skeleton, useDelayed } from "@/components/ui/States";
import type { User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { pushRecent } from "@/lib/recent";
import { useFetch } from "@/lib/useFetch";

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user: me } = useAuth();
  const { t, dept, role } = useI18n();
  const allowed = can(me, "user.manage");
  const { data, error, loading, reload } = useFetch<User>(allowed ? `/users/${id}/` : null);
  const showSkeleton = useDelayed(loading);
  const actions = useUserActions(reload);

  useEffect(() => {
    if (me && data) {
      pushRecent(me.id, { kind: "user", id: data.id, title: data.full_name, subtitle: `${dept(data.department_name)} · ${role(data.role)}`, href: `/users/${data.id}` });
    }
    // The label is rewritten in the active language each visit, so only the person matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.id, data?.id]);

  if (!me) return null;
  if (!allowed) return <NoAccess />;

  const back = { href: "/users", label: t("users.title") };
  if (error) return (<><PageHeader title={t("users.title")} back={back} /><ErrorState message={error} onRetry={reload} /></>);
  if (!data) {
    return (
      <>
        <PageHeader title={t("users.title")} back={back} />
        {showSkeleton ? (
          <div className="max-w-2xl space-y-4" aria-busy="true">
            <Skeleton className="h-36 rounded-card" />
            <Skeleton className="h-36 rounded-card" />
          </div>
        ) : null}
      </>
    );
  }

  const isMe = data.id === me.id;
  return (
    <>
      <PageHeader
        back={back}
        title={data.full_name}
        leading={<Avatar name={data.full_name} size="lg" />}
        meta={
          <span className="flex flex-wrap gap-1.5">
            <StatusPill tone={data.is_active ? "success" : "neutral"}>{data.is_active ? t("common.active") : t("common.inactive")}</StatusPill>
            {isMe ? <StatusPill tone="primary" dot={false}>{t("users.you")}</StatusPill> : null}
          </span>
        }
        action={
          <>
            <Link href={`/users/${data.id}/edit`} className={buttonClass("secondary")}>
              <Pencil size={20} aria-hidden />
              {t("users.edit")}
            </Link>
            <Button variant="secondary" icon={<LockKey size={20} aria-hidden />} onClick={() => actions.askReset(data)}>
              {t("users.resetPassword")}
            </Button>
            {data.is_active ? (
              !isMe ? (
                <Button variant="secondary" className="text-danger-ink" icon={<UserMinus size={20} aria-hidden />} onClick={() => actions.askDeactivate(data)}>
                  {t("users.deactivate")}
                </Button>
              ) : null
            ) : (
              <Button variant="secondary" icon={<UserCheck size={20} aria-hidden />} onClick={() => void actions.activate(data)}>
                {t("users.activate")}
              </Button>
            )}
          </>
        }
      />
      <div className="max-w-2xl space-y-5 md:space-y-6">
        <InsetList title={t("users.sectionAccount")}>
          <InsetRow label={t("common.email")} ltr>{data.email}</InsetRow>
          <InsetRow label={t("common.status")}>{data.is_active ? t("common.active") : t("common.inactive")}</InsetRow>
          <InsetRow label={t("users.language")}>{data.preferred_language === "ar" ? "العربية" : "English"}</InsetRow>
        </InsetList>
        <InsetList title={t("users.sectionOrg")}>
          <InsetRow label={t("common.department")}>{dept(data.department_name)}</InsetRow>
          <InsetRow label={t("common.role")}>{role(data.role)}</InsetRow>
        </InsetList>
        <InsetList title={t("users.sectionActivity")}>
          <InsetRow label={t("users.passwordStatus")}>
            {data.must_change_password ? (
              <StatusPill tone="warning">{t("users.mustChange")}</StatusPill>
            ) : (
              <StatusPill tone="success">{t("users.passwordSet")}</StatusPill>
            )}
          </InsetRow>
        </InsetList>
      </div>
      {actions.dialogs}
    </>
  );
}
