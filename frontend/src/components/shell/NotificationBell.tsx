"use client";

import { Bell, BellSlash, Checks } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { IconButton } from "@/components/ui/Button";
import { Popover } from "@/components/ui/Popover";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { type AppNotification, type Page, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useMyWork } from "@/lib/mywork";
import { useFetch } from "@/lib/useFetch";

const LATEST = 8;

function List({ close }: { close: () => void }) {
  const { t, relativeTime } = useI18n();
  const router = useRouter();
  const { reload: reloadWork } = useMyWork();
  const { data, error, loading, reload } = useFetch<Page<AppNotification>>(`/notifications/?page_size=${LATEST}`);

  async function open(n: AppNotification) {
    close();
    if (!n.read) await api(`/notifications/${n.id}/read/`, { method: "POST" }).catch(() => {});
    reloadWork();
    if (n.link) router.push(n.link);
  }

  async function markAll() {
    await api("/notifications/read-all/", { method: "POST" }).catch(() => {});
    reload();
    reloadWork();
  }

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) {
    return (
      <div className="space-y-2 p-3" aria-busy="true">
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
      </div>
    );
  }
  const unread = data.results.some((n) => !n.read);
  return (
    <div>
      <div className="flex items-center justify-between gap-3 px-4 pt-3 pb-1">
        <h2 className="text-section text-ink">{t("notifications.title")}</h2>
        <button
          type="button"
          onClick={markAll}
          disabled={!unread}
          className="inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-label text-primary-strong hover:bg-primary-tint disabled:text-ink-3 disabled:hover:bg-transparent"
        >
          <Checks size={18} aria-hidden />
          {t("notifications.markAll")}
        </button>
      </div>
      {data.results.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-10 text-center">
          <BellSlash size={28} className="mb-2 text-ink-3" aria-hidden />
          <p className="text-body text-ink">{t("notifications.emptyTitle")}</p>
          <p className="mt-0.5 text-label font-normal text-ink-2">{t("notifications.emptyText")}</p>
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {data.results.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => open(n)}
                className="flex w-full items-start gap-3 px-4 py-3 text-start hover:bg-canvas"
              >
                <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-primary"}`} />
                <span className="min-w-0 flex-1">
                  <span className={`block text-body ${n.read ? "font-normal text-ink-2" : "text-ink"}`}>{n.title}</span>
                  {n.body ? <span className="block truncate text-label font-normal text-ink-2">{n.body}</span> : null}
                  <span className="mt-0.5 block text-caption text-ink-2">{relativeTime(n.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The bell in the top bar. The unread count comes from the shared My Work request, so it needs no polling of its own. */
export function NotificationBell() {
  const { t, formatNumber } = useI18n();
  const { unread } = useMyWork();
  const label = unread > 0 ? t("notifications.unreadLabel", { count: formatNumber(unread) }) : t("notifications.title");
  return (
    <Popover
      label={t("notifications.title")}
      width={360}
      trigger={({ open, ...props }) => (
        <span className="relative">
          <IconButton label={label} tipClassName={open ? "opacity-0!" : ""} {...props}>
            <Bell size={22} weight={open ? "fill" : "regular"} aria-hidden />
          </IconButton>
          {unread > 0 ? (
            <span
              aria-hidden
              dir="ltr"
              className="pointer-events-none absolute -end-0.5 -top-0.5 flex min-w-4.5 items-center justify-center rounded-full bg-primary px-1 text-caption font-semibold leading-[18px] text-white ring-2 ring-canvas"
            >
              {unread > 99 ? "99+" : unread}
            </span>
          ) : null}
        </span>
      )}
    >
      {(close) => <List close={close} />}
    </Popover>
  );
}
