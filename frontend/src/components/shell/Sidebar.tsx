"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Tooltip } from "@/components/ui/Tooltip";
import { useT } from "@/lib/i18n";
import { isActive, useNavItems } from "@/lib/nav";
import { useMyWork } from "@/lib/mywork";
import { LogoMark } from "./Logo";
import { Badge, NavIcon } from "./navIcons";

/**
 * Navy sidebar at the inline start: left in English, right in Arabic. It collapses to an icon rail from 768 to 1023px.
 * view-transition-name lets it glide across when the language changes.
 */
export function Sidebar() {
  const t = useT();
  const pathname = usePathname();
  const items = useNavItems();
  const { badges } = useMyWork();
  return (
    <aside
      style={{ viewTransitionName: "app-sidebar" }}
      className="sticky top-0 hidden h-dvh w-[var(--rail-w)] shrink-0 flex-col bg-navy text-on-navy md:flex lg:w-[var(--sidebar-w)]"
    >
      <div className="flex h-16 items-center justify-center gap-3 px-5 lg:justify-start lg:px-6">
        <LogoMark />
        <span className="hidden text-section font-semibold text-on-navy lg:inline">{t("brand.name")}</span>
      </div>

      <nav aria-label={t("common.mainNav")} className="mt-4 flex-1">
        <p className="mb-2 hidden px-6 text-caption text-on-navy-muted lg:block">{t("nav.workspace")}</p>
        <ul className="space-y-1">
          {items.map((item) => {
            const active = isActive(item.href, pathname);
            const label = t(`nav.${item.key}`);
            return (
              <li key={item.key} className="relative px-3">
                <Tooltip label={label} side="end" className="w-full" tipClassName="lg:hidden">
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    aria-label={(badges[item.key] ?? 0) > 0 ? `${label}, ${badges[item.key]}` : label}
                    className={`flex h-11 w-full items-center justify-center gap-3 rounded-control text-body font-medium transition-transform duration-[var(--dur-fast)] active:scale-[0.98] lg:justify-start lg:px-3 ${
                      active ? "bg-navy-2 text-white" : "text-on-navy-muted hover:bg-navy-2 hover:text-on-navy"
                    }`}
                  >
                    <NavIcon item={item.key} active={active} />
                    <span className="hidden lg:inline">{label}</span>
                    <span className="hidden lg:ms-auto lg:inline-flex">
                      <Badge count={badges[item.key] ?? 0} />
                    </span>
                    {(badges[item.key] ?? 0) > 0 ? (
                      <span aria-hidden className="absolute end-4 top-2 size-2 rounded-full bg-primary ring-2 ring-navy lg:hidden" />
                    ) : null}
                  </Link>
                </Tooltip>
                {active ? <span aria-hidden className="absolute inset-y-2 end-0 w-[3px] rounded-full bg-primary" /> : null}
              </li>
            );
          })}
        </ul>
      </nav>

      <p className="hidden px-6 pb-5 text-caption text-on-navy-muted lg:block">{t("brand.company")}</p>
    </aside>
  );
}
