"use client";

import { X } from "@phosphor-icons/react";
import { useId, useRef } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/lib/i18n";
import { IconButton } from "./Button";
import { useDialog } from "./useDialog";
import { usePresence } from "./usePresence";

/**
 * One overlay for everything that opens on top of a page: a centred modal on desktop, a bottom sheet with a grabber on
 * phones. Focus stays inside, Escape closes, focus goes back to what opened it.
 */
export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
  alert,
  size = "md",
  hideClose,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  alert?: boolean;
  size?: "md" | "lg";
  hideClose?: boolean;
}) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const { mounted, closing } = usePresence(open);
  useDialog(open, onClose, ref);
  if (!mounted || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-6">
      <div
        data-closing={closing || undefined}
        className="sheet-backdrop absolute inset-0 bg-navy/45"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={ref}
        role={alert ? "alertdialog" : "dialog"}
        aria-modal="true"
        aria-labelledby={titleId}
        data-closing={closing || undefined}
        className={`sheet-panel relative flex max-h-[92dvh] w-full flex-col rounded-t-sheet bg-surface shadow-float md:max-h-[85dvh] md:rounded-sheet ${
          size === "lg" ? "md:max-w-2xl" : "md:max-w-md"
        }`}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
          className="mx-auto mt-2 flex h-5 w-16 shrink-0 items-center justify-center md:hidden"
        >
          <span aria-hidden className="h-1 w-10 rounded-full bg-line" />
        </button>
        <div className="flex items-start justify-between gap-3 px-5 pt-3 md:pt-5">
          <h2 id={titleId} className="min-w-0 pt-1.5 text-section text-ink">
            {title}
          </h2>
          {hideClose ? null : (
            <IconButton label={t("common.close")} onClick={onClose} className="-me-2 -mt-1 hidden md:inline-flex">
              <X size={20} aria-hidden />
            </IconButton>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer ? (
          <div className="flex flex-col-reverse gap-3 border-t border-line px-5 pt-4 pb-[calc(1rem+env(safe-area-inset-bottom))] md:flex-row md:justify-end md:pb-4">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
