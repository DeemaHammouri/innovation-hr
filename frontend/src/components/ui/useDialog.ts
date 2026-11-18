"use client";

import { useEffect } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Only what can really take focus: an element hidden at this screen size (the phone grab handle on desktop) would swallow .focus(). */
const visible = (el: HTMLElement) => typeof el.checkVisibility !== "function" || el.checkVisibility({ visibilityProperty: true });
const focusables = (node: HTMLElement | null | undefined) => Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(visible);

/** Escape closes, Tab stays inside, focus returns to whatever opened the dialog, page behind doesn't scroll. */
export function useDialog(open: boolean, onClose: () => void, ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement as HTMLElement | null;
    // Lock the page behind the dialog on <html>: locking <body> would switch position: sticky off for the top bar and sidebar.
    const root = document.documentElement;
    const previousOverflow = root.style.overflow;
    root.style.overflow = "hidden";

    const node = ref.current;
    const autofocus = node?.querySelector<HTMLElement>("[data-autofocus]");
    (autofocus && visible(autofocus) ? autofocus : focusables(node)[0])?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
      if (e.key !== "Tab" || !node) return;
      const items = focusables(node);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      root.style.overflow = previousOverflow;
      trigger?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
}
