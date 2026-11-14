/** The last few things a person opened, kept in this browser only and per account. */
export type RecentItem = { kind: "user" | "client"; id: number; title: string; subtitle: string; href: string };

const key = (userId: number) => `innovation.recent.${userId}`;

export function getRecents(userId: number): RecentItem[] {
  try {
    const raw = localStorage.getItem(key(userId));
    return raw ? (JSON.parse(raw) as RecentItem[]).slice(0, 5) : [];
  } catch {
    return [];
  }
}

export function pushRecent(userId: number, item: RecentItem) {
  try {
    const rest = getRecents(userId).filter((r) => r.href !== item.href);
    localStorage.setItem(key(userId), JSON.stringify([item, ...rest].slice(0, 5)));
  } catch {
    // Private windows can refuse storage. Recents are a convenience, so skip quietly.
  }
}
