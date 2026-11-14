"use client";

import { CaretDown, Eye, EyeSlash, MagnifyingGlass, X } from "@phosphor-icons/react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";

type Shared = {
  name: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
};

const control =
  "block h-11 w-full rounded-control border bg-surface px-3.5 text-body text-ink placeholder:text-ink-2/70 transition-shadow duration-[var(--dur-fast)] focus-visible:outline-offset-0 focus:border-primary disabled:bg-canvas disabled:text-ink-2";

function Shell({ name, label, error, hint, required, children }: Shared & { children: React.ReactNode }) {
  const { t, msg } = useI18n();
  return (
    <div>
      <label htmlFor={`field-${name}`} className="mb-1.5 block text-label text-ink">
        {label}
        {required ? <span className="font-medium text-ink-2"> {t("common.required")}</span> : null}
      </label>
      {children}
      {/* One slot: the error replaces the hint. */}
      {error ? (
        <p id={`error-${name}`} role="alert" className="mt-1.5 text-label font-medium text-danger-ink">
          {msg(error)}
        </p>
      ) : hint ? (
        <p id={`hint-${name}`} className="mt-1.5 text-label font-normal text-ink-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

const describedBy = (name: string, error?: string, hint?: string) => (error ? `error-${name}` : hint ? `hint-${name}` : undefined);
const border = (error?: string) => (error ? "border-danger" : "border-line");

// Email, phone, password and URL are typed left to right in both languages.
const LTR_TYPES = ["email", "tel", "password", "url"];

type InputProps = Shared & Omit<React.InputHTMLAttributes<HTMLInputElement>, "name"> & { ltr?: boolean };

export function Input({ name, label, error, hint, required, type = "text", ltr, className = "", ...rest }: InputProps) {
  const { t } = useI18n();
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";
  const forceLtr = ltr || LTR_TYPES.includes(type);
  const input = (
    <input
      {...rest}
      id={`field-${name}`}
      name={name}
      type={isPassword && shown ? "text" : type}
      required={required}
      dir={forceLtr ? "ltr" : undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy(name, error, hint)}
      // dir="ltr" fields line up with their labels: left in English, right in Arabic. The input itself is LTR,
      // so the room kept for the show/hide button needs physical sides.
      className={`${control} ${forceLtr ? "text-left rtl:text-right" : ""} ${border(error)} ${isPassword ? "pr-12 rtl:pl-12 rtl:pr-3.5" : ""} ${className}`}
    />
  );
  return (
    <Shell name={name} label={label} error={error} hint={hint} required={required}>
      {isPassword ? (
        <div className="relative">
          {input}
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? t("common.hidePassword") : t("common.showPassword")}
            aria-pressed={shown}
            className="absolute inset-y-0 end-0 flex w-11 items-center justify-center rounded-e-control text-ink-2 hover:text-ink"
          >
            {shown ? <EyeSlash size={20} aria-hidden /> : <Eye size={20} aria-hidden />}
          </button>
        </div>
      ) : (
        input
      )}
    </Shell>
  );
}

type SelectProps = Shared &
  Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "name"> & { options: { value: string; label: string }[]; placeholder?: string };

export function Select({ name, label, error, hint, required, options, placeholder, className = "", ...rest }: SelectProps) {
  return (
    <Shell name={name} label={label} error={error} hint={hint} required={required}>
      <div className="relative">
        <select
          {...rest}
          id={`field-${name}`}
          name={name}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(name, error, hint)}
          className={`${control} appearance-none pe-10 ${border(error)} ${className}`}
        >
          {placeholder ? <option value="">{placeholder}</option> : null}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <CaretDown size={16} aria-hidden className="pointer-events-none absolute end-3.5 top-1/2 -translate-y-1/2 text-ink-2" />
      </div>
    </Shell>
  );
}

type TextareaProps = Shared & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "name">;

export function Textarea({ name, label, error, hint, required, className = "", ...rest }: TextareaProps) {
  return (
    <Shell name={name} label={label} error={error} hint={hint} required={required}>
      <textarea
        rows={3}
        {...rest}
        id={`field-${name}`}
        name={name}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(name, error, hint)}
        className={`${control} h-auto py-2.5 ${border(error)} ${className}`}
      />
    </Shell>
  );
}

/** The inline search field on list pages: icon, clear button, label for screen readers only. */
export function SearchField({
  label,
  value,
  onChange,
  placeholder,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <div className={`relative ${className}`}>
      <label htmlFor="list-search" className="sr-only">
        {label}
      </label>
      <MagnifyingGlass size={20} aria-hidden className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-ink-2" />
      <input
        id="list-search"
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className={`${control} border-line ps-11 pe-11`}
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={t("common.clearSearch")}
          className="absolute end-1 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-full text-ink-2 hover:bg-canvas hover:text-ink"
        >
          <X size={16} aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
