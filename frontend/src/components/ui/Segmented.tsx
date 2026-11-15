"use client";

import { useRef } from "react";
import { useI18n } from "@/lib/i18n";

export type Segment<V extends string> = {
  value: V;
  label: React.ReactNode;
  ariaLabel?: string;
  lang?: string;
  id?: string;
  controls?: string;
};

/**
 * A pill with a sliding blue thumb. As a radiogroup it picks a value (language); as a tablist it switches views.
 * Arrow keys move between segments (mirrored in RTL), Home and End jump to the ends.
 */
export function Segmented<V extends string>({
  segments,
  value,
  onChange,
  label,
  mode = "radiogroup",
  className = "",
}: {
  segments: Segment<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
  mode?: "radiogroup" | "tablist";
  className?: string;
}) {
  const { dir } = useI18n();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const index = Math.max(0, segments.findIndex((s) => s.value === value));

  function onKeyDown(e: React.KeyboardEvent) {
    const rtl = dir === "rtl";
    let next = index;
    if (e.key === "ArrowRight") next = index + (rtl ? -1 : 1);
    else if (e.key === "ArrowLeft") next = index + (rtl ? 1 : -1);
    else if (e.key === "ArrowDown") next = index + 1;
    else if (e.key === "ArrowUp") next = index - 1;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = segments.length - 1;
    else return;
    e.preventDefault();
    next = (next + segments.length) % segments.length;
    onChange(segments[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role={mode}
      aria-label={label}
      onKeyDown={onKeyDown}
      className={`relative grid rounded-full border border-line bg-canvas p-0.5 ${className}`}
      style={{ gridTemplateColumns: `repeat(${segments.length}, minmax(0, 1fr))` }}
    >
      {/* The thumb moves with transform only. --dir-sign mirrors it in RTL. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0.5 start-0.5 rounded-full bg-primary-strong transition-transform duration-[var(--dur-base)] ease-[var(--ease-spring)]"
        style={{
          width: `calc((100% - 4px) / ${segments.length})`,
          transform: `translateX(calc(${index * 100}% * var(--dir-sign)))`,
        }}
      />
      {segments.map((s, i) => {
        const active = i === index;
        return (
          <button
            key={s.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            id={s.id}
            type="button"
            role={mode === "tablist" ? "tab" : "radio"}
            aria-checked={mode === "radiogroup" ? active : undefined}
            aria-selected={mode === "tablist" ? active : undefined}
            aria-controls={s.controls}
            aria-label={s.ariaLabel}
            lang={s.lang}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(s.value)}
            className={`relative z-10 flex h-9 min-w-11 items-center justify-center rounded-full px-4 text-label transition-colors duration-[var(--dur-base)] ${
              active ? "text-white" : "text-ink-2 hover:text-ink"
            }`}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
