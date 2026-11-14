"use client";

import { createContext, useContext, useMemo, useState } from "react";

type ShellState = {
  title: string;
  /** True once the large page title has scrolled under the top bar. */
  condensed: boolean;
  setTitle: (t: string) => void;
  setCondensed: (c: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (o: boolean) => void;
};

const ShellContext = createContext<ShellState | null>(null);

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [title, setTitle] = useState("");
  const [condensed, setCondensed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const value = useMemo(
    () => ({ title, condensed, setTitle, setCondensed, paletteOpen, setPaletteOpen }),
    [title, condensed, paletteOpen],
  );
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell() {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used inside ShellProvider");
  return ctx;
}
