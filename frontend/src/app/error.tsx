"use client";

import { StatusPage } from "@/components/StatusPage";
import { useT } from "@/lib/i18n";

/** Any unexpected failure while drawing a page: a plain message and a way to retry, never a stack trace. */
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useT();
  return <StatusPage kind="error" href="/" action={t("status.error.retry")} onAction={reset} />;
}
