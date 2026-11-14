"use client";

import { useAuth } from "./auth";

/** Add a key here, then its icon in navIcons.tsx and its label (nav.<key>) in both locale files. */
export type NavKey = "home" | "users" | "clients" | "leads" | "pipeline" | "settings";
export type NavItem = { key: NavKey; href: string };

/**
 * What the sidebar and the tab bar show depends on the role. Home (My Work) is for everyone.
 * The server enforces every one of these again; hiding a link is only a courtesy.
 * Later phases add their modules here, by role.
 */
export function useNavItems(): NavItem[] {
  const { user } = useAuth();
  const items: NavItem[] = [{ key: "home", href: "/" }];
  if (user?.permissions.manage_users) items.push({ key: "users", href: "/users" });
  if (user?.permissions.manage_clients) items.push({ key: "clients", href: "/clients" });
  const role = user?.role_key;
  if (role === "ceo" || role === "marketing") items.push({ key: "leads", href: "/leads" });
  if (role === "commercial_head" || role === "commercial_member") items.push({ key: "pipeline", href: "/pipeline" });
  if (user?.role_key === "ceo") items.push({ key: "settings", href: "/admin/lookups" });
  return items;
}

export const isActive = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
