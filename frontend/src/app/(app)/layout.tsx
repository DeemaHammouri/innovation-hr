"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { PageTitle } from "@/components/ui/PageTitle";
import { Skeleton } from "@/components/ui/States";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

/** Everything inside (app) needs a signed-in person who has already set their own password. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, sessionExpired } = useAuth();
  const router = useRouter();
  const t = useT();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(sessionExpired ? "/session-expired" : "/login");
    else if (user.must_change_password) router.replace("/set-password");
  }, [loading, user, sessionExpired, router]);

  if (loading || !user || user.must_change_password) {
    return (
      <div className="flex min-h-dvh" aria-busy="true" aria-label={t("common.loading")}>
        <PageTitle />
        <div className="hidden w-[var(--rail-w)] shrink-0 bg-navy md:block lg:w-[var(--sidebar-w)]" />
        <div className="flex-1 p-4 md:p-8">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="mt-6 h-48 w-full max-w-3xl rounded-card" />
        </div>
      </div>
    );
  }
  return (
    <AppShell>
      <Suspense fallback={null}>{children}</Suspense>
    </AppShell>
  );
}
