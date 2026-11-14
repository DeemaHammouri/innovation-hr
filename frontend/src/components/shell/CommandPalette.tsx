"use client";

import {
  Buildings,
  ClockCounterClockwise,
  GearSix,
  House,
  MagnifyingGlass,
  Plus,
  SignOut,
  Translate,
  User as UserIcon,
  UserCircle,
  Users,
} from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useDialog } from "@/components/ui/useDialog";
import { usePresence } from "@/components/ui/usePresence";
import { Ltr } from "@/components/ui/Ltr";
import { Skeleton, useDelayed } from "@/components/ui/States";
import { api, type Client, type User } from "@/lib/api";
import { useAuth, useChangeLanguage, useSignOut } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { getRecents, pushRecent } from "@/lib/recent";
import { useShell } from "@/lib/shell";

type Entry = {
  id: string;
  group: string;
  title: string;
  subtitle?: string;
  ltrSubtitle?: boolean;
  icon: React.ReactNode;
  run: () => void;
};

/** Wraps the part of `text` that matches the query so the eye finds it. */
function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  const at = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark className="bg-transparent font-bold text-primary-strong">{text.slice(at, at + q.length)}</mark>
      {text.slice(at + q.length)}
    </>
  );
}

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen } = useShell();
  const { mounted, closing } = usePresence(paletteOpen);
  if (!mounted || typeof document === "undefined") return null;
  return <PaletteDialog closing={closing} onClose={() => setPaletteOpen(false)} />;
}

function PaletteDialog({ closing, onClose }: { closing: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const { t, lang, dept, role } = useI18n();
  const router = useRouter();
  const signOut = useSignOut();
  const changeLanguage = useChangeLanguage();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [found, setFound] = useState<{ q: string; users: User[]; clients: Client[] } | null>(null);
  const [active, setActive] = useState(0);
  const panel = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const listId = useId();
  const canUsers = !!user?.permissions.manage_users;
  const canClients = !!user?.permissions.manage_clients;

  useDialog(!closing, onClose, panel);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), 200);
    return () => clearTimeout(id);
  }, [query]);

  useEffect(() => {
    if (!debounced) return;
    let cancelled = false;
    const enc = encodeURIComponent(debounced);
    Promise.all([
      canUsers ? api<User[]>(`/users/?search=${enc}`).catch(() => []) : Promise.resolve([] as User[]),
      canClients ? api<Client[]>(`/clients/?search=${enc}`).catch(() => []) : Promise.resolve([] as Client[]),
    ]).then(([users, clients]) => {
      if (!cancelled) setFound({ q: debounced, users: users.slice(0, 5), clients: clients.slice(0, 5) });
    });
    return () => {
      cancelled = true;
    };
  }, [debounced, canUsers, canClients]);

  const waiting = query.trim() !== "" && found?.q !== query.trim();
  const showSkeleton = useDelayed(waiting, 100);

  const go = (href: string) => () => router.push(href);

  const entries = useMemo<Entry[]>(() => {
    if (!user) return [];
    const q = query.trim().toLowerCase();
    const match = (s: string) => !q || s.toLowerCase().includes(q);
    const out: Entry[] = [];
    const icon = (n: React.ReactNode) => n;

    const pages: Entry[] = [
      { id: "p-home", group: "search.pages", title: t("nav.home"), icon: icon(<House size={20} aria-hidden />), run: go("/") },
      ...(canUsers ? [{ id: "p-users", group: "search.pages", title: t("nav.users"), icon: <Users size={20} aria-hidden />, run: go("/users") }] : []),
      ...(canClients ? [{ id: "p-clients", group: "search.pages", title: t("nav.clients"), icon: <Buildings size={20} aria-hidden />, run: go("/clients") }] : []),
      { id: "p-profile", group: "search.pages", title: t("common.profile"), icon: <UserCircle size={20} aria-hidden />, run: go("/profile") },
      { id: "p-settings", group: "search.pages", title: t("common.settings"), icon: <GearSix size={20} aria-hidden />, run: go("/profile?tab=settings") },
    ];
    const actions: Entry[] = [
      ...(canUsers ? [{ id: "a-user", group: "search.actions", title: t("users.add"), icon: <Plus size={20} aria-hidden />, run: go("/users/new") }] : []),
      ...(canClients ? [{ id: "a-client", group: "search.actions", title: t("clients.add"), icon: <Plus size={20} aria-hidden />, run: go("/clients/new") }] : []),
      {
        id: "a-lang",
        group: "search.actions",
        title: t("search.switchLanguage"),
        icon: <Translate size={20} aria-hidden />,
        run: () => changeLanguage(lang === "en" ? "ar" : "en"),
      },
      { id: "a-out", group: "search.actions", title: t("common.signOut"), icon: <SignOut size={20} className="rtl:-scale-x-100" aria-hidden />, run: () => void signOut() },
    ];

    if (!q) {
      const recents = getRecents(user.id).map<Entry>((r) => ({
        id: `r-${r.href}`,
        group: "search.recent",
        title: r.title,
        subtitle: r.subtitle,
        icon: <ClockCounterClockwise size={20} aria-hidden />,
        run: go(r.href),
      }));
      return [...recents, ...actions.map((a) => ({ ...a, group: "search.suggested" }))];
    }

    out.push(...pages.filter((p) => match(p.title)));
    if (found && found.q === query.trim()) {
      out.push(
        ...found.users.map<Entry>((u) => ({
          id: `u-${u.id}`,
          group: "search.people",
          title: u.full_name,
          subtitle: u.email,
          ltrSubtitle: true,
          icon: <UserIcon size={20} aria-hidden />,
          run: () => {
            pushRecent(user.id, { kind: "user", id: u.id, title: u.full_name, subtitle: `${dept(u.department_name)} · ${role(u.role)}`, href: `/users/${u.id}` });
            router.push(`/users/${u.id}`);
          },
        })),
        ...found.clients.map<Entry>((c) => ({
          id: `c-${c.id}`,
          group: "search.clients",
          title: c.company_name,
          subtitle: c.contact_person || c.email || c.phone,
          icon: <Buildings size={20} aria-hidden />,
          run: () => {
            pushRecent(user.id, { kind: "client", id: c.id, title: c.company_name, subtitle: c.contact_person || c.email || c.phone, href: `/clients/${c.id}` });
            router.push(`/clients/${c.id}`);
          },
        })),
      );
    }
    out.push(...actions.filter((a) => match(a.title)));
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, query, found, lang, canUsers, canClients, t]);

  const current = Math.min(active, Math.max(0, entries.length - 1));

  useEffect(() => {
    list.current?.querySelector(`[data-index="${current}"]`)?.scrollIntoView({ block: "nearest" });
  }, [current, entries]);

  function choose(i: number) {
    const entry = entries[i];
    if (!entry) return;
    onClose();
    entry.run();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive(entries.length ? (current + 1) % entries.length : 0);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(entries.length ? (current - 1 + entries.length) % entries.length : 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(current);
    }
  }

  const grouped: { group: string; items: { entry: Entry; index: number }[] }[] = [];
  entries.forEach((entry, index) => {
    const last = grouped[grouped.length - 1];
    if (last && last.group === entry.group) last.items.push({ entry, index });
    else grouped.push({ group: entry.group, items: [{ entry, index }] });
  });

  const noResults = query.trim() !== "" && !waiting && entries.length === 0;

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-end justify-center md:items-start md:px-6 md:pt-[12vh]">
      <div data-closing={closing || undefined} className="sheet-backdrop absolute inset-0 bg-navy/45" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={t("search.title")}
        data-closing={closing || undefined}
        className="sheet-panel relative flex h-[85dvh] w-full flex-col overflow-hidden rounded-t-sheet bg-surface shadow-float md:h-auto md:max-h-[70dvh] md:max-w-xl md:rounded-sheet"
      >
        <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-line md:hidden" aria-hidden />
        <div className="flex items-center gap-3 border-b border-line px-4 focus-within:border-primary">
          <MagnifyingGlass size={20} aria-hidden className="shrink-0 text-ink-2" />
          <input
            data-autofocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={entries[current] ? `${listId}-${current}` : undefined}
            aria-label={t("search.title")}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder={t("search.placeholder")}
            autoComplete="off"
            className="h-14 min-w-0 flex-1 bg-transparent text-body text-ink placeholder:text-ink-2/70 focus-visible:outline-none"
          />
          <kbd dir="ltr" className="hidden shrink-0 rounded-md border border-line bg-canvas px-1.5 py-0.5 font-sans text-caption text-ink-2 md:block">
            Esc
          </kbd>
        </div>

        <div ref={list} id={listId} role="listbox" aria-label={t("search.title")} className="min-h-0 flex-1 overflow-y-auto p-2">
          {showSkeleton && entries.length === 0 ? (
            <div className="space-y-1 p-1" aria-busy="true" aria-label={t("common.loading")}>
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center gap-3 px-2 py-2.5">
                  <Skeleton className="size-9 rounded-control" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3.5 w-1/3" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {noResults ? (
            <div className="px-6 py-10 text-center">
              <p className="text-section text-ink">{t("search.noResults", { q: query.trim() })}</p>
              <p className="mt-1 text-body text-ink-2">{t("search.tryHint")}</p>
            </div>
          ) : null}

          {grouped.map((g) => (
            <div key={g.group} role="group" aria-label={t(g.group)} className="pb-1">
              <p className="px-3 pt-2 pb-1 text-caption text-ink-2">{t(g.group)}</p>
              {g.items.map(({ entry, index }) => {
                const on = index === current;
                return (
                  <div
                    key={entry.id}
                    id={`${listId}-${index}`}
                    role="option"
                    aria-selected={on}
                    data-index={index}
                    onMouseMove={() => setActive(index)}
                    onClick={() => choose(index)}
                    className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-control px-3 py-2 ${on ? "bg-primary-tint" : ""}`}
                  >
                    <span className={`flex size-9 shrink-0 items-center justify-center rounded-control ${on ? "bg-surface text-primary-strong" : "bg-canvas text-ink-2"}`}>
                      {entry.icon}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body text-ink">
                        <Highlight text={entry.title} query={query} />
                      </span>
                      {entry.subtitle ? (
                        <span className="block truncate text-label font-normal text-ink-2">
                          {entry.ltrSubtitle ? (
                            <Ltr>
                              <Highlight text={entry.subtitle} query={query} />
                            </Ltr>
                          ) : (
                            <Highlight text={entry.subtitle} query={query} />
                          )}
                        </span>
                      ) : null}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <div dir="ltr" className="hidden items-center gap-4 border-t border-line px-4 py-2.5 text-caption text-ink-2 md:flex">
          <span>↑ ↓ {t("search.hintMove")}</span>
          <span>↵ {t("search.hintOpen")}</span>
          <span>Esc {t("search.hintClose")}</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
