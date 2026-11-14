"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";

// Figures count up once per visit, on the first load only.
let played = false;

export function CountUp({ value }: { value: number }) {
  const { formatNumber } = useI18n();
  const [shown, setShown] = useState(value);
  const done = useRef(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (played || reduce || done.current || value === 0) {
      const t = setTimeout(() => setShown(value), 0);
      return () => clearTimeout(t);
    }
    done.current = true;
    played = true;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 400);
      setShown(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <span className="tnum">{formatNumber(shown)}</span>;
}
