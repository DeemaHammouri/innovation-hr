"use client";

import { useAuth } from "./auth";

/** Add a key here, then its icon in navIcons.tsx and its label (nav.<key>) in both locale files. */
export type NavKey = "home" | "users" | "clients" | "leads" | "pipeline" | "quotations" | "contracts" | "approvals" | "operation" | "payments" | "attendance" | "leave" | "payroll" | "settings";
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
  if (role === "ceo" || role === "commercial_head" || role === "commercial_member" || role === "hr_head" || role === "hr_member") items.push({ key: "quotations", href: "/quotations" });
  if (role && role !== "marketing") items.push({ key: "contracts", href: "/contracts" });
  if (role === "ceo" || role === "commercial_head" || role === "commercial_member" || role === "operation_head" || role === "operation_member") items.push({ key: "operation", href: "/operation" });
  if (role === "ceo" || role === "commercial_head") items.push({ key: "payments", href: "/payments" });
  if (role) items.push({ key: "attendance", href: "/attendance" });
  if (role) items.push({ key: "leave", href: "/leave" });
  if (role) items.push({ key: "payroll", href: "/payroll" });
  if (role === "ceo") items.push({ key: "approvals", href: "/approvals" });
  if (user?.role_key === "ceo") items.push({ key: "settings", href: "/admin/lookups" });
  return items;
}

export const isActive = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
