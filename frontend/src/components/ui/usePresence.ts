import { useEffect, useState } from "react";

/** Keeps something mounted while its exit animation plays. */
export function usePresence(open: boolean, ms = 240) {
  const [mounted, setMounted] = useState(open);
  useEffect(() => {
    const t = setTimeout(() => setMounted(open), open ? 0 : ms);
    return () => clearTimeout(t);
  }, [open, ms]);
  return { mounted: open || mounted, closing: !open && mounted };
}
