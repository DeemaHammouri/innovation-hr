"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "@/lib/i18n";

/**
 * A floating panel anchored to a trigger. It lives in a portal so tables and scroll boxes never clip it.
 * Escape and outside clicks close it, and focus returns to the trigger.
 */
export function Popover({
  trigger,
  children,
  label,
  menu,
  width = 224,
}: {
  trigger: (props: {
    ref: React.RefObject<HTMLButtonElement | null>;
    onClick: () => void;
    "aria-haspopup": "menu" | "dialog";
    "aria-expanded": boolean;
    "aria-controls": string | undefined;
    open: boolean;
  }) => React.ReactNode;
  children: (close: () => void) => React.ReactNode;
  label: string;
  menu?: boolean;
  width?: number;
}) {
  const { dir } = useI18n();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const anchor = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();

  // Closing from inside (Escape, picking an item) hands focus back to the trigger. Clicking elsewhere doesn't.
  const [focusBack, setFocusBack] = useState(0);
  const close = useCallback(() => {
    setOpen(false);
    setFocusBack((n) => n + 1);
  }, []);
  useEffect(() => {
    if (focusBack > 0) anchor.current?.focus();
  }, [focusBack]);

  useLayoutEffect(() => {
    if (!open || !anchor.current) return;
    const r = anchor.current.getBoundingClientRect();
    const h = panel.current?.offsetHeight ?? 0;
    const below = r.bottom + 8;
    const top = below + h > window.innerHeight - 8 ? Math.max(8, r.top - 8 - h) : below;
    // Line the panel's end edge up with the trigger's end edge, and keep it on screen.
    const raw = dir === "rtl" ? r.left : r.right - width;
    setPos({ top, left: Math.min(Math.max(8, raw), window.innerWidth - width - 8) });
  }, [open, dir, width]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!panel.current?.contains(target) && !anchor.current?.contains(target)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
      }
      if (e.key === "Tab" && !menu) {
        // A disclosure, not a trap: tabbing past the last control closes it.
        const items = panel.current?.querySelectorAll<HTMLElement>("button, a[href], [tabindex='0']");
        if (items && items.length && document.activeElement === items[items.length - 1] && !e.shiftKey) setOpen(false);
      }
    };
    const onScroll = () => setOpen(false);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    const first = panel.current?.querySelector<HTMLElement>("[role=menuitem], button, a[href]");
    first?.focus();
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey, true);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, close, menu]);

  function onPanelKey(e: React.KeyboardEvent) {
    if (!menu) return;
    const items = Array.from(panel.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") items[(i + 1) % items.length]?.focus();
    else if (e.key === "ArrowUp") items[(i - 1 + items.length) % items.length]?.focus();
    else if (e.key === "Home") items[0]?.focus();
    else if (e.key === "End") items[items.length - 1]?.focus();
    else return;
    e.preventDefault();
  }

  return (
    <>
      {trigger({
        ref: anchor,
        onClick: () => setOpen((o) => !o),
        "aria-haspopup": menu ? "menu" : "dialog",
        "aria-expanded": open,
        "aria-controls": open ? id : undefined,
        open,
      })}
      {open
        ? createPortal(
            <div
              ref={panel}
              id={id}
              role={menu ? "menu" : "dialog"}
              aria-label={label}
              onKeyDown={onPanelKey}
              style={{ top: pos?.top ?? 0, left: pos?.left ?? 0, width, visibility: pos ? "visible" : "hidden" }}
              className="fixed z-50 animate-pop rounded-card border border-line bg-surface p-1.5 shadow-float"
            >
              {children(close)}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

export function MenuItem({
  icon,
  children,
  onSelect,
  danger,
  plain,
}: {
  icon?: React.ReactNode;
  children: React.ReactNode;
  onSelect?: () => void;
  danger?: boolean;
  /** Inside a disclosure panel (not a menu): drop the menuitem role. */
  plain?: boolean;
}) {
  const cls = `flex h-11 w-full items-center gap-3 rounded-control px-3 text-start text-body md:h-10 ${
    danger ? "text-danger-ink hover:bg-danger-bg" : "text-ink hover:bg-canvas"
  } focus-visible:bg-canvas`;
  const content = (
    <>
      {icon ? <span className="shrink-0 text-current opacity-80">{icon}</span> : null}
      <span className="min-w-0 flex-1 truncate">{children}</span>
    </>
  );
  return (
    <button type="button" role={plain ? undefined : "menuitem"} onClick={onSelect} className={cls}>
      {content}
    </button>
  );
}

/** Kebab-style action menu: pass the trigger button and menu items. */
export function Menu({
  trigger,
  label,
  children,
}: {
  trigger: (props: Parameters<Parameters<typeof Popover>[0]["trigger"]>[0]) => React.ReactNode;
  label: string;
  children: (close: () => void) => React.ReactNode;
}) {
  return (
    <Popover menu trigger={trigger} label={label}>
      {children}
    </Popover>
  );
}
