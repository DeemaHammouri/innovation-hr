"use client";

import { Stamp } from "@phosphor-icons/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export type StampStatus = { has_stamp: boolean; can_manage: boolean };
const CHANGED = "company-stamp-changed";

/** Tell every open notice that the stamp was just uploaded, so banners and sheets update without a reload. */
export function announceStampChanged() {
  window.dispatchEvent(new Event(CHANGED));
}

/** Whether the company stamp is on file (signing needs it) and whether this person can upload it. null until known. */
export function useStampStatus(): StampStatus | null {
  const { user } = useAuth();
  const path = usePathname();
  const [status, setStatus] = useState<StampStatus | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const on = () => setTick((n) => n + 1);
    window.addEventListener(CHANGED, on);
    return () => window.removeEventListener(CHANGED, on);
  }, []);
  const signedIn = !!user;
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    api<StampStatus>("/company/setup/")
      .then((s) => !cancelled && setStatus(s))
      .catch(() => !cancelled && setStatus(null));
    return () => {
      cancelled = true;
    };
  }, [signedIn, path, tick]);
  return status;
}

/** Shown where someone is about to sign: says plainly what is missing and who fixes it, with a link only for the person who can. */
export function StampNotice({ status }: { status: StampStatus | null }) {
  const { t } = useI18n();
  if (!status || status.has_stamp) return null;
  return (
    <div role="alert" className="mb-4 flex gap-3 rounded-control border border-warning/30 bg-warning-bg p-4 text-warning-ink">
      <Stamp size={22} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-2">
        <p className="text-body font-semibold">{t("stamp.missing.title")}</p>
        <p className="text-label font-normal">{t(status.can_manage ? "stamp.missing.ceo" : "stamp.missing.other")}</p>
        {status.can_manage ? <Link href="/admin/company" className="inline-block text-label font-semibold underline underline-offset-2">{t("stamp.missing.link")}</Link> : null}
      </div>
    </div>
  );
}

/** A setup banner at the top of every page, for the person who can upload the stamp. Nobody else sees it. */
export function StampBanner() {
  const { t } = useI18n();
  const status = useStampStatus();
  const path = usePathname();
  if (!status || status.has_stamp || !status.can_manage) return null;
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center gap-3 rounded-control border border-warning/30 bg-warning-bg px-4 py-3 text-warning-ink">
      <Stamp size={20} className="shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 text-label font-semibold">{t("stamp.banner")}</p>
      {path.startsWith("/admin/company") ? null : <Link href="/admin/company" className="text-label font-semibold underline underline-offset-2">{t("stamp.missing.link")}</Link>}
    </div>
  );
}
