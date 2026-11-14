"use client";

import { DotsThree, MagnifyingGlass, UserCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Sheet } from "@/components/ui/Sheet";
import { useT } from "@/lib/i18n";
import { isActive, useNavItems } from "@/lib/nav";
import { useMyWork } from "@/lib/mywork";
import { useShell } from "@/lib/shell";
import { Badge, NavIcon } from "./navIcons";

const tab =
  "relative flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-caption transition-transform duration-[var(--dur-fast)] active:scale-95";

const MAX_TABS = 3; // Search and More/Profile take the other two slots.

/** Phones: an iOS-style bottom tab bar instead of a hamburger. Anything past the first three destinations moves into a More sheet. */
export function TabBar() {
  const t = useT();
  const pathname = usePathname();
  const items = useNavItems();
  const { badges } = useMyWork();
  const { paletteOpen, setPaletteOpen } = useShell();
  const [moreOpen, setMoreOpen] = useState(false);
  const overflow = items.length > MAX_TABS;
  const shown = overflow ? items.slice(0, MAX_TABS) : items;
  const rest = overflow ? items.slice(MAX_TABS) : [];
  const onProfile = pathname.startsWith("/profile");
  const restActive = rest.some((i) => isActive(i.href, pathname)) || (overflow && onProfile);
  const moreCount = rest.reduce((n, i) => n + (badges[i.key] ?? 0), 0);

  return (
    <>
      <nav
        aria-label={t("common.mainNav")}
        className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="flex">
          {shown.map((item) => {
            const active = isActive(item.href, pathname) && !paletteOpen;
            return (
              <li key={item.key} className="flex flex-1">
                <Link href={item.href} aria-current={active ? "page" : undefined} className={`${tab} ${active ? "text-primary-strong" : "text-ink-2"}`}>
                  <NavIcon item={item.key} active={active} size={24} />
                  {t(`nav.${item.key}`)}
                  <Badge count={badges[item.key] ?? 0} className="absolute top-1.5 start-1/2 ms-2" />
                </Link>
              </li>
            );
          })}
          <li className="flex flex-1">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              aria-haspopup="dialog"
              className={`${tab} ${paletteOpen ? "text-primary-strong" : "text-ink-2"}`}
            >
              <MagnifyingGlass size={24} weight={paletteOpen ? "fill" : "regular"} aria-hidden />
              {t("nav.search")}
            </button>
          </li>
          <li className="flex flex-1">
            {overflow ? (
              <button
                type="button"
                onClick={() => setMoreOpen(true)}
                aria-haspopup="dialog"
                className={`${tab} ${restActive && !paletteOpen ? "text-primary-strong" : "text-ink-2"}`}
              >
                <DotsThree size={24} weight={restActive && !paletteOpen ? "fill" : "regular"} aria-hidden />
                {t("nav.more")}
                <Badge count={moreCount} className="absolute top-1.5 start-1/2 ms-2" />
              </button>
            ) : (
              <Link
                href="/profile"
                aria-current={onProfile ? "page" : undefined}
                className={`${tab} ${onProfile && !paletteOpen ? "text-primary-strong" : "text-ink-2"}`}
              >
                <UserCircle size={24} weight={onProfile && !paletteOpen ? "fill" : "regular"} aria-hidden />
                {t("nav.profile")}
              </Link>
            )}
          </li>
        </ul>
      </nav>

      <Sheet open={moreOpen} title={t("nav.more")} onClose={() => setMoreOpen(false)}>
        <ul className="-mx-2 space-y-1">
          {[...rest.map((i) => ({ key: i.key as string, href: i.href, icon: <NavIcon item={i.key} active={isActive(i.href, pathname)} size={24} /> })), { key: "profile", href: "/profile", icon: <UserCircle size={24} aria-hidden /> }].map((row) => (
            <li key={row.key}>
              <Link
                href={row.href}
                onClick={() => setMoreOpen(false)}
                className="flex min-h-12 items-center gap-3 rounded-control px-3 text-body text-ink hover:bg-canvas"
              >
                <span className="text-primary-strong">{row.icon}</span>
                <span className="flex-1">{t(`nav.${row.key}`)}</span>
                <Badge count={badges[row.key] ?? 0} />
              </Link>
            </li>
          ))}
        </ul>
      </Sheet>
    </>
  );
}
