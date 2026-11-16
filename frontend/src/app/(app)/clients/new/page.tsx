"use client";

import { ClientForm } from "@/components/clients/ClientForm";
import { can } from "@/lib/can";
import { NoAccess } from "@/components/NoAccess";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

export default function NewClientPage() {
  const { user } = useAuth();
  const t = useT();
  if (!user) return null;
  if (!can(user, "client.manage")) return <NoAccess />;
  return (
    <>
      <PageHeader title={t("clients.add")} back={{ href: "/clients", label: t("clients.title") }} />
      <ClientForm editing={null} />
    </>
  );
}
