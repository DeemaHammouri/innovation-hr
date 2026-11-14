"use client";

/** CSS-only tooltip: shows on hover and keyboard focus, never on touch (no hover there). */
export function Tooltip({
  label,
  side = "bottom",
  children,
  className = "",
  tipClassName = "",
}: {
  label: string;
  side?: "bottom" | "end" | "bottom-end";
  children: React.ReactNode;
  className?: string;
  tipClassName?: string;
}) {
  const place = side === "bottom-end" ? "top-full mt-2 end-0" : side === "bottom" ? "top-full mt-2 start-1/2 -translate-x-1/2 rtl:translate-x-1/2" : "start-full ms-3 top-1/2 -translate-y-1/2";
  return (
    <span className={`group/tip relative inline-flex ${className}`}>
      {children}
      <span
        role="tooltip"
        aria-hidden
        className={`pointer-events-none absolute z-50 hidden whitespace-nowrap rounded-control bg-navy px-2.5 py-1.5 text-caption text-on-navy opacity-0 transition-opacity duration-[var(--dur-fast)] [@media(hover:hover)]:block group-hover/tip:opacity-100 group-focus-within/tip:opacity-100 ${place} ${tipClassName}`}
      >
        {label}
      </span>
    </span>
  );
}
