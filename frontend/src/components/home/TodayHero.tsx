"use client";

import { ArrowRight, CheckCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { Ltr } from "@/components/ui/Ltr";
import { Skeleton } from "@/components/ui/States";
import type { WorkItem } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useMyWork } from "@/lib/mywork";

export const HERO_ITEMS = 3;

/** Overdue first, then the soonest due date, then the rest in the order the server gave them. */
export function byUrgency(items: WorkItem[]) {
  return items
    .map((item, i) => ({ item, i }))
    .sort((a, b) => Number(b.item.overdue) - Number(a.item.overdue) || (a.item.due ?? "9999-12-31").localeCompare(b.item.due ?? "9999-12-31") || a.i - b.i)
    .map((x) => x.item);
}

/** The one to three things that need this person now, each with a direct button. Built from My Work, so it can never disagree with the server. */
export function TodayHero() {
  const { t, formatDate, formatNumber } = useI18n();
  const { data } = useMyWork();
  const items = data ? byUrgency(data.items) : [];
  const top = items.slice(0, HERO_ITEMS);
  const more = data ? Math.max(0, data.total - top.length) : 0;
  const overdue = items.filter((i) => i.overdue).length;

  return (
    <section aria-labelledby="today-title" className="mb-4 overflow-hidden rounded-card bg-navy p-5 text-on-navy md:p-6 lg:mb-6">
      <div className="flex items-center justify-between gap-3">
        <h2 id="today-title" className="text-section text-white">{t("home.today")}</h2>
        {data && data.total > 0 ? (
          <span className={`rounded-full px-3 py-1 text-label font-medium ${overdue ? "bg-danger-bg text-danger-ink" : "bg-white/15 text-white"}`}>
            {overdue ? t("home.overdueCount", { count: formatNumber(overdue) }) : t("mywork.count", { count: formatNumber(data.total) })}
          </span>
        ) : null}
      </div>
      {!data ? (
        <div className="mt-4 space-y-2" aria-busy="true">
          <Skeleton className="h-14 !bg-white/15" />
          <Skeleton className="h-14 !bg-white/15" />
        </div>
      ) : top.length === 0 ? (
        <div className="mt-4 flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/15 text-white">
            <CheckCircle size={22} weight="fill" aria-hidden />
          </span>
          <div>
            <p className="text-body text-white">{t("mywork.emptyTitle")}</p>
            <p className="text-label font-normal text-on-navy">{t("mywork.emptyText")}</p>
          </div>
        </div>
      ) : (
        <ul className="stagger mt-4 space-y-2">
          {top.map((item) => (
            <li key={`${item.kind}-${item.ref}-${item.link}`} className="flex items-center gap-3 rounded-control bg-white/10 p-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body text-white">{item.title}</span>
                <span className="block truncate text-label font-normal text-on-navy">
                  <Ltr>{item.ref}</Ltr> · {t(`mywork.kind.${item.kind}`)}
                  {item.due ? ` · ${item.overdue ? t("mywork.overdue") : t("mywork.due")} ${formatDate(item.due)}` : ""}
                </span>
              </span>
              <Link href={item.link} className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-control bg-white px-4 text-label font-semibold text-navy transition-transform active:scale-[0.98] md:h-10">
                {t("home.open")}
                <ArrowRight size={16} aria-hidden className="rtl:-scale-x-100" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {more > 0 ? (
        <a href="#attention" className="mt-3 inline-block text-label font-medium text-white underline underline-offset-2">
          {t("home.moreWaiting", { count: formatNumber(more) })}
        </a>
      ) : null}
    </section>
  );
}
