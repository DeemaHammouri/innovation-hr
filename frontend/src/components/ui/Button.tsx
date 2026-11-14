"use client";

import { CircleNotch } from "@phosphor-icons/react";
import { Tooltip } from "./Tooltip";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary: "bg-primary-strong text-white hover:bg-primary-hover active:bg-primary-press",
  secondary: "border border-line bg-surface text-ink hover:bg-canvas active:bg-neutral-bg",
  danger: "bg-danger text-white hover:bg-danger-ink active:bg-danger-ink",
  ghost: "text-primary-strong hover:bg-primary-tint active:bg-primary-line",
};

const base =
  "inline-flex shrink-0 select-none items-center justify-center gap-2 rounded-control text-label font-semibold transition-transform duration-[var(--dur-fast)] ease-[var(--ease-out)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  icon?: React.ReactNode;
};

/** Never disabled for invalid data. It only locks while a request is running. */
export function Button({ variant = "primary", loading, icon, children, className = "", disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${base} h-11 px-4 md:h-10 ${variants[variant]} ${className}`}
    >
      {loading ? <CircleNotch size={20} className="animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

type IconProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> & {
  label: string;
  variant?: Variant;
  tooltipSide?: "bottom" | "end";
  tipClassName?: string;
  pressed?: boolean;
};

/** 40px square (44px on touch). The label is both the tooltip and the accessible name. */
export function IconButton({ label, variant = "ghost", tooltipSide = "bottom", tipClassName, pressed, className = "", children, ...rest }: IconProps) {
  const tone = variant === "ghost" ? "text-ink-2 hover:bg-canvas hover:text-ink active:bg-neutral-bg" : variants[variant];
  return (
    <Tooltip label={label} side={tooltipSide} tipClassName={tipClassName}>
      <button type="button" {...rest} aria-label={label} aria-pressed={pressed} className={`${base} size-11 md:size-10 ${tone} ${className}`}>
        {children}
      </button>
    </Tooltip>
  );
}

/** A link that looks like a button. */
export function buttonClass(variant: Variant = "secondary", className = "") {
  return `${base} h-11 px-4 md:h-10 ${variants[variant]} ${className}`;
}
