"use client";

import { StatusPage } from "@/components/StatusPage";
import { useT } from "@/lib/i18n";

export default function SessionExpiredPage() {
  const t = useT();
  return <StatusPage kind="expired" href="/login" action={t("common.signIn")} />;
}
