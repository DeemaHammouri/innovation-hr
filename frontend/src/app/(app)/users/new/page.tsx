"use client";

import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { UserForm } from "@/components/users/UserForm";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

export default function NewUserPage() {
  const { user } = useAuth();
  const t = useT();
  if (!user) return null;
  if (!user.permissions.manage_users) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("users.add")} back={{ href: "/users", label: t("users.title") }} />
      <UserForm editing={null} me={user} />
    </>
  );
}
