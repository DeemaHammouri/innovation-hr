"use client";

import { CaretRight, CheckCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/States";
import { useI18n } from "@/lib/i18n";
import { useMyWork } from "@/lib/mywork";
import { byUrgency, HERO_ITEMS } from "./TodayHero";

const SHOWN = 6;

/** What needs this person's action today. Every module feeds it through the backend; the list is the same shape for every role. */
export function MyWorkSection() {
  const { t, formatDate, formatNumber } = useI18n();
  const { data } = useMyWork();
  const rest = data ? byUrgency(data.items).slice(HERO_ITEMS) : [];
  if (data && rest.length === 0) return null;

  return (
    <Card as="section" id="attention" aria-labelledby="my-work" className="mb-4 overflow-hidden lg:mb-6">
      <div className="flex items-center justify-between gap-3 p-5 pb-3">
        <h2 id="my-work" className="text-section text-ink">
          {t("home.attention")}
        </h2>
        {data && data.total > 0 ? <StatusPill tone={data.items.some((i) => i.overdue) ? "danger" : "primary"}>{t("mywork.count", { count: formatNumber(data.total) })}</StatusPill> : null}
      </div>
      {!data ? (
        <div className="space-y-2 px-5 pb-5" aria-busy="true">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : rest.length === 0 ? (
        <div className="flex items-center gap-3 px-5 pb-5">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-success-bg text-success-ink">
            <CheckCircle size={22} weight="fill" aria-hidden />
          </span>
          <div>
            <p className="text-body text-ink">{t("mywork.emptyTitle")}</p>
            <p className="text-label font-normal text-ink-2">{t("mywork.emptyText")}</p>
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-line border-t border-line">
          {rest.slice(0, SHOWN).map((item) => (
            <li key={`${item.kind}-${item.ref}-${item.link}`}>
              <Link href={item.link} className="flex min-h-14 items-center gap-3 px-5 py-2.5 hover:bg-canvas">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body text-ink">{item.title}</span>
                  <span className="block truncate text-label font-normal text-ink-2">
                    <span dir="ltr">{item.ref}</span> · {t(`mywork.kind.${item.kind}`)}
                  </span>
                </span>
                {item.due ? (
                  <StatusPill tone={item.overdue ? "danger" : "neutral"}>
                    {item.overdue ? t("mywork.overdue") : t("mywork.due")} {formatDate(item.due)}
                  </StatusPill>
                ) : null}
                <CaretRight size={16} aria-hidden className="shrink-0 text-ink-3 rtl:-scale-x-100" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
