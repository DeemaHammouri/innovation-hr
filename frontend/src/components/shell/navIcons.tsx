import { CalendarCheck, ChartLineUp, Buildings, GearSix, House, Kanban, Megaphone, CalendarBlank, Clock, CurrencyCircleDollar, ListChecks, Receipt, SealCheck, Signature, Users, Wallet, ChartBar } from "@phosphor-icons/react";
import type { NavItem } from "@/lib/nav";

const ICONS = { home: House, users: Users, clients: Buildings, settings: GearSix, portal: Buildings, leads: Megaphone, dashboard: ChartLineUp, appointments: CalendarCheck, pipeline: Kanban, quotations: Receipt, contracts: Signature, approvals: SealCheck, operation: ListChecks, payments: CurrencyCircleDollar, attendance: Clock, leave: CalendarBlank, payroll: Wallet, reports: ChartBar };

/** Regular when idle, fill when active (the SF Symbols behaviour). */
export function NavIcon({ item, active, size = 20 }: { item: NavItem["key"]; active: boolean; size?: number }) {
  const Icon = ICONS[item];
  return <Icon size={size} weight={active ? "fill" : "regular"} aria-hidden />;
}

/** Small count on a nav item. Hidden at zero, capped at 99+. */
export function Badge({ count, className = "" }: { count: number; className?: string }) {
  if (count <= 0) return null;
  return (
    <span
      dir="ltr"
      className={`inline-flex min-w-5 items-center justify-center rounded-full bg-primary-strong px-1.5 text-caption font-semibold leading-5 text-white ${className}`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
