"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useI18n } from "@/lib/i18n";
import { Button } from "./Button";

export const PAGE_SIZE = 10;

/** "Showing 1-10 of 24" with Previous and Next. The server returns whole lists, so paging happens here. */
export function Pagination({ page, total, onPage, pageSize = PAGE_SIZE }: { page: number; total: number; onPage: (page: number) => void; pageSize?: number }) {
  const { t, formatNumber } = useI18n();
  if (total <= pageSize) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  const last = Math.ceil(total / pageSize);
  return (
    <nav aria-label={t("common.pagination")} className="flex items-center justify-between gap-3 border-t border-line px-4 py-3">
      <p className="tnum text-label font-medium text-ink-2">
        {t("common.showing", { from: formatNumber(from), to: formatNumber(to), total: formatNumber(total) })}
      </p>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)} icon={<CaretLeft size={16} className="rtl:-scale-x-100" aria-hidden />}>
          {t("common.previous")}
        </Button>
        <Button variant="secondary" disabled={page >= last} onClick={() => onPage(page + 1)}>
          {t("common.next")}
          <CaretRight size={16} className="rtl:-scale-x-100" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
