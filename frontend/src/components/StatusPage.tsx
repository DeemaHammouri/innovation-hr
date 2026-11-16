"use client";

import { Compass, LockSimple, Timer, WarningCircle, WifiSlash } from "@phosphor-icons/react";
import Link from "next/link";
import { LanguageSwitcher } from "@/components/shell/LanguageSwitcher";
import { LogoMark } from "@/components/shell/Logo";
import { buttonClass } from "@/components/ui/Button";
import { PageTitle } from "@/components/ui/PageTitle";
import { useT } from "@/lib/i18n";

const ICONS = { notFound: Compass, noAccess: LockSimple, expired: Timer, error: WarningCircle, offline: WifiSlash };

/** A whole-page message with one clear way back. Used for 404 and an expired session. */
export function StatusPage({ kind, href, action, onAction }: { kind: keyof typeof ICONS; href: string; action: string; onAction?: () => void }) {
  const t = useT();
  const Icon = ICONS[kind];
  return (
    <main className="flex min-h-dvh flex-col bg-canvas px-4 py-5">
      <PageTitle>{t(`status.${kind}.title`)}</PageTitle>
      <div className="flex items-center justify-between">
        <LogoMark size={36} />
        <LanguageSwitcher />
      </div>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center py-10 text-center">
        <div className="mb-5 flex size-14 items-center justify-center rounded-full bg-primary-tint text-primary-strong">
          <Icon size={28} aria-hidden />
        </div>
        <h1 className="text-title text-ink">{t(`status.${kind}.title`)}</h1>
        <p className="mt-2 text-body text-ink-2">{t(`status.${kind}.text`)}</p>
        {onAction ? (
          <button type="button" onClick={onAction} className={buttonClass("primary", "mt-6")}>{action}</button>
        ) : (
          <Link href={href} className={buttonClass("primary", "mt-6")}>
            {action}
          </Link>
        )}
      </div>
    </main>
  );
}
