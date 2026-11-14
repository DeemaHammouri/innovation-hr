"use client";

import { StatusPage } from "@/components/StatusPage";
import { useT } from "@/lib/i18n";

export default function NotFound() {
  const t = useT();
  return <StatusPage kind="notFound" href="/" action={t("noaccess.home")} />;
}
