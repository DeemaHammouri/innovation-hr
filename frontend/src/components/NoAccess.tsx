"use client";

import { LockSimple } from "@phosphor-icons/react";
import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";
import { useT } from "@/lib/i18n";

/** Shown inside the app when a role opens a page it doesn't have. */
export function NoAccess() {
  const t = useT();
  return (
    <Card>
      <EmptyState
        icon={<LockSimple size={24} aria-hidden />}
        title={t("noaccess.title")}
        description={t("noaccess.text")}
        action={
          <Link href="/" className={buttonClass("primary")}>
            {t("noaccess.home")}
          </Link>
        }
      />
    </Card>
  );
}
