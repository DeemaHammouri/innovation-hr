"use client";

import { useEffect } from "react";
import { StampBanner } from "@/components/company/StampNotice";
import { MyWorkProvider } from "@/lib/mywork";
import { ShellProvider, useShell } from "@/lib/shell";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { TabBar } from "./TabBar";
import { TopBar } from "./TopBar";

function Frame({ children }: { children: React.ReactNode }) {
  const { setPaletteOpen } = useShell();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setPaletteOpen]);

  return (
    <div className="flex min-h-dvh">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-page flex-1 px-4 pt-6 pb-[calc(6rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8 md:pb-12">
          <StampBanner />
          {children}
        </main>
      </div>
      <TabBar />
      <CommandPalette />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <MyWorkProvider>
        <Frame>{children}</Frame>
      </MyWorkProvider>
    </ShellProvider>
  );
}
