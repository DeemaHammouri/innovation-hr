"use client";

import { ClientForm } from "@/components/clients/ClientForm";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

export default function NewClientPage() {
  const { user } = useAuth();
  const t = useT();
  if (!user) return null;
  if (!user.permissions.manage_clients) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("clients.add")} back={{ href: "/clients", label: t("clients.title") }} />
      <ClientForm editing={null} />
    </>
  );
}
