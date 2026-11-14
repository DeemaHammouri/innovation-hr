"use client";

import { ArrowLeft } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { useShell } from "@/lib/shell";
import { PageTitle } from "./PageTitle";

/**
 * The iOS-style large title. When it scrolls under the top bar, the same words appear in the bar.
 * `back` adds a link to the parent list above the title.
 */
export function PageHeader({
  title,
  description,
  action,
  back,
  meta,
  leading,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  back?: { href: string; label: string };
  meta?: React.ReactNode;
  leading?: React.ReactNode;
}) {
  const { setTitle, setCondensed } = useShell();
  const ref = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    setTitle(title);
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setCondensed(!entry.isIntersecting), {
      rootMargin: "-72px 0px 0px 0px",
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      setCondensed(false);
    };
  }, [title, setTitle, setCondensed]);

  return (
    <header className="mb-6 md:mb-8">
      <PageTitle>{title}</PageTitle>
      {back ? (
        <Link
          href={back.href}
          className="-ms-2 mb-2 inline-flex h-11 items-center gap-1.5 rounded-control px-2 text-label text-primary-strong hover:bg-primary-tint md:h-9"
        >
          <ArrowLeft size={16} className="rtl:-scale-x-100" aria-hidden />
          {back.label}
        </Link>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 items-center gap-4">
          {leading}
          <div className="min-w-0">
          <h1 ref={ref} className="text-large-title text-ink">
            {title}
          </h1>
          {description ? <p className="mt-1 text-body text-ink-2">{description}</p> : null}
          {meta ? <div className="mt-2">{meta}</div> : null}
          </div>
        </div>
        {action ? <div className="flex flex-wrap items-center gap-2">{action}</div> : null}
      </div>
    </header>
  );
}
