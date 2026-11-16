"use client";

import { useAuth } from "./auth";
import { can, canAny } from "@/lib/can";

/** Add a key here, then its icon in navIcons.tsx and its label (nav.<key>) in both locale files. */
export type NavKey = "home" | "users" | "clients" | "portal" | "leads" | "dashboard" | "appointments" | "pipeline" | "quotations" | "contracts" | "approvals" | "operation" | "payments" | "attendance" | "leave" | "payroll" | "reports" | "settings" | "company" | "meetings" | "tracking" | "templates";
export type NavItem = { key: NavKey; href: string };

/**
 * What the sidebar and the tab bar show depends on the role. Home (My Work) is for everyone.
 * The server enforces every one of these again; hiding a link is only a courtesy.
 * Later phases add their modules here, by role.
 */
export function useNavItems(): NavItem[] {
  const { user } = useAuth();
  if (user?.role_key === "client") return [{ key: "portal", href: "/portal" }];  // a client has one page, and it is not the staff home
  const items: NavItem[] = [{ key: "home", href: "/" }];
  if (can(user, "user.manage")) items.push({ key: "users", href: "/users" });
  if (can(user, "client.manage")) items.push({ key: "clients", href: "/clients" });
  if (can(user, "lead.access") && !canAny(user, "lead.manage", "lead.work_assigned")) items.push({ key: "leads", href: "/leads" });
  if (canAny(user, "lead.manage", "lead.work_assigned")) items.push({ key: "pipeline", href: "/pipeline" });
  if (can(user, "lead.dashboard")) items.push({ key: "dashboard", href: "/dashboard" });
  if (can(user, "appointment.access")) items.push({ key: "appointments", href: "/appointments" });
  if (can(user, "quotation.access")) items.push({ key: "quotations", href: "/quotations" });
  if (can(user, "contract.access")) items.push({ key: "contracts", href: "/contracts" });
  if (can(user, "operation.access")) items.push({ key: "operation", href: "/operation" });
  if (can(user, "payment.view")) items.push({ key: "payments", href: "/payments" });
  if (user?.role_key) items.push({ key: "attendance", href: "/attendance" });
  if (user?.role_key) items.push({ key: "leave", href: "/leave" });
  if (user?.role_key) items.push({ key: "payroll", href: "/payroll" });
  if (canAny(user, "report.funnel", "report.revenue", "report.forecast", "report.operations", "report.hr")) items.push({ key: "reports", href: "/reports" });
  if (canAny(user, "meeting_report.write", "meeting_report.view_all")) items.push({ key: "meetings", href: "/meetings" });
  if (can(user, "contract.sign")) items.push({ key: "approvals", href: "/approvals" });
  if (can(user, "tracking.view")) items.push({ key: "tracking", href: "/admin/tracking" });
  if (can(user, "contract.template")) items.push({ key: "templates", href: "/admin/templates" });
  if (can(user, "company.manage")) items.push({ key: "company", href: "/admin/company" });
  if (can(user, "settings.manage")) items.push({ key: "settings", href: "/admin/lookups" });
  return items;
}

export const isActive = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
