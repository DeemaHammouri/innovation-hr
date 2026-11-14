"use client";

import { MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import { useShell } from "@/lib/shell";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { LogoMark } from "./Logo";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";

export function TopBar() {
  const t = useT();
  const { title, condensed, setPaletteOpen } = useShell();
  const [mac, setMac] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setMac(/Mac|iPhone|iPad/.test(navigator.platform)), 0);
    return () => clearTimeout(id);
  }, []);

  return (
    <header className="sticky top-0 z-30 h-[var(--topbar-h)] border-b border-line bg-canvas/85 backdrop-blur-md">
      <div className="mx-auto flex h-full max-w-page items-center gap-3 px-4 md:px-8">
        {/* The large page title moves up into here once it scrolls out of sight. */}
        <div className="flex min-w-0 items-center gap-3 md:max-w-[9rem] lg:w-56 lg:max-w-none lg:shrink-0">
          <span className="md:hidden">
            <LogoMark size={32} />
          </span>
          <p
            aria-hidden={!condensed}
            className={`min-w-0 truncate text-section text-ink transition-opacity duration-[var(--dur-base)] ${condensed ? "opacity-100" : "opacity-0"}`}
          >
            {title}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-haspopup="dialog"
          className="mx-auto hidden h-10 min-w-0 max-w-md flex-1 items-center gap-3 rounded-control border border-line bg-surface px-3.5 text-start text-body text-ink-2 transition-transform duration-[var(--dur-fast)] hover:border-primary-line active:scale-[0.99] md:flex"
        >
          <MagnifyingGlass size={20} aria-hidden />
          <span className="min-w-0 flex-1 truncate">{t("search.placeholder")}</span>
          <kbd dir="ltr" className="shrink-0 rounded-md border border-line bg-canvas px-1.5 py-0.5 font-sans text-caption text-ink-2">
            {mac ? "⌘K" : "Ctrl K"}
          </kbd>
        </button>

        <div className="ms-auto flex shrink-0 items-center gap-3 md:ms-0">
          <NotificationBell />
          <LanguageSwitcher />
          <div className="hidden md:block">
            <ProfileMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
