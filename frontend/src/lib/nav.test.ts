import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeUser } from "@/test/utils";
import type { RoleKey, User } from "./api";
import { can, canAny } from "./can";
import { isActive, useNavItems } from "./nav";

let current: User | null = null;
vi.mock("./auth", () => ({ useAuth: () => ({ user: current }) }));

// The seed grants from backend/accounts/catalog.py, per role (only the capabilities the navigation reads).
const OPS = ["operation.access", "operation.work", "operation.view_all_clients", "handover.view", "project.view", "gtask.access"];
const ROLE_CAPS: Record<RoleKey, string[]> = {
  ceo: [
    "lead.access", "lead.view_all", "lead.dashboard", "appointment.access", "quotation.access", "contract.access", "contract.sign", "contract.template",
    "operation.access", "gtask.access", "handover.view", "project.view", "payment.view", "client.manage", "user.manage", "company.manage", "settings.manage",
    "tracking.view", "meeting_report.view_all", "report.funnel", "report.revenue", "report.hr",
  ],
  marketing: ["lead.access", "lead.dashboard", "appointment.access", "gtask.access", "report.funnel"],
  commercial_head: [
    "lead.access", "lead.manage", "lead.dashboard", "appointment.access", "quotation.access", "contract.access", "operation.access", "gtask.access",
    "handover.view", "project.view", "payment.view", "meeting_report.write", "meeting_report.view_all", "report.funnel", "report.revenue", "report.forecast",
  ],
  commercial_member: ["lead.access", "lead.work_assigned", "appointment.access", "quotation.access", "contract.access", "operation.access", "gtask.access", "handover.view", "meeting_report.write"],
  hr_head: ["quotation.access", "contract.access", "contract.template", "gtask.access", "report.hr", "hr.staff", "hr.payroll_view"],
  hr_member: ["quotation.access", "contract.access", "gtask.access", "hr.staff"],
  operation_head: [...OPS, "client.manage", "report.operations"],
  operation_member: OPS,
  super_admin: [],
  client: ["portal.access"],
};

const keysFor = (role: RoleKey, caps = ROLE_CAPS[role]) => {
  current = makeUser({ role_key: role, capabilities: caps });
  return renderHook(() => useNavItems()).result.current.map((i) => i.key);
};

beforeEach(() => {
  current = null;
});

describe("can / canAny", () => {
  it("is false for a missing user or missing capabilities", () => {
    expect(can(null, "x")).toBe(false);
    expect(can(undefined, "x")).toBe(false);
    expect(canAny(null, "x")).toBe(false);
  });
  it("can requires every code, canAny requires one", () => {
    const u = { capabilities: ["a", "b"] };
    expect(can(u, "a", "b")).toBe(true);
    expect(can(u, "a", "c")).toBe(false);
    expect(canAny(u, "c", "b")).toBe(true);
    expect(canAny(u, "c", "d")).toBe(false);
  });
});

describe("useNavItems per role", () => {
  it("shows a signed-out visitor only Home", () => {
    current = null;
    expect(renderHook(() => useNavItems()).result.current.map((i) => i.key)).toEqual(["home"]);
  });

  it("gives a client the portal and nothing else, even if given staff capabilities", () => {
    expect(keysFor("client")).toEqual(["portal"]);
    expect(keysFor("client", ["user.manage", "payment.view"])).toEqual(["portal"]);
  });

  it("gives the CEO the administration entries", () => {
    const k = keysFor("ceo");
    expect(k).toEqual(expect.arrayContaining(["users", "clients", "company", "settings", "tracking", "templates", "approvals", "payments", "reports"]));
    expect(k).toContain("leads");
    expect(k).not.toContain("pipeline");
  });

  it("gives Marketing leads and dashboard but no pipeline, money or contracts", () => {
    const k = keysFor("marketing");
    expect(k).toEqual(expect.arrayContaining(["leads", "dashboard", "appointments"]));
    expect(k).not.toEqual(expect.arrayContaining(["pipeline"]));
    for (const banned of ["payments", "contracts", "quotations", "users", "settings", "operation"]) expect(k).not.toContain(banned);
  });

  it("gives the Commercial head the pipeline instead of the plain leads list", () => {
    const k = keysFor("commercial_head");
    expect(k).toContain("pipeline");
    expect(k).not.toContain("leads");
    expect(k).toEqual(expect.arrayContaining(["quotations", "contracts", "payments", "meetings"]));
  });

  it("gives a Commercial member the pipeline but no payments or user management", () => {
    const k = keysFor("commercial_member");
    expect(k).toContain("pipeline");
    expect(k).not.toContain("payments");
    expect(k).not.toContain("users");
  });

  it("gives HR quotations and contracts but not leads or payments", () => {
    const head = keysFor("hr_head");
    expect(head).toEqual(expect.arrayContaining(["quotations", "contracts", "templates", "reports"]));
    for (const banned of ["leads", "pipeline", "payments", "users", "operation"]) expect(head).not.toContain(banned);
    expect(keysFor("hr_member")).not.toContain("templates");
  });

  it.each(["operation_head", "operation_member"] as const)("never gives %s any money or contract entry", (role) => {
    const k = keysFor(role);
    for (const banned of ["payments", "contracts", "quotations", "approvals", "templates", "dashboard", "leads", "pipeline", "users", "company", "settings", "tracking"]) {
      expect(k).not.toContain(banned);
    }
    expect(k).toEqual(expect.arrayContaining(["operation", "handovers", "projects", "tasks"]));
  });

  it("lets only the Operation head see clients and the operations report", () => {
    expect(keysFor("operation_head")).toEqual(expect.arrayContaining(["clients", "reports"]));
    const member = keysFor("operation_member");
    expect(member).not.toContain("clients");
    expect(member).not.toContain("reports");
  });

  it("always starts with Home and has no duplicate entries for any staff role", () => {
    for (const role of Object.keys(ROLE_CAPS) as RoleKey[]) {
      if (role === "client") continue;
      const k = keysFor(role);
      expect(k[0]).toBe("home");
      expect(new Set(k).size).toBe(k.length);
    }
  });

  it("keeps attendance, leave and payroll as self-service entries for every signed-in staff role", () => {
    for (const role of ["marketing", "operation_member", "hr_member"] as const) {
      expect(keysFor(role)).toEqual(expect.arrayContaining(["attendance", "leave", "payroll"]));
    }
  });

  it("hides everything gated by a capability when the capability list is empty", () => {
    expect(keysFor("super_admin")).toEqual(["home", "attendance", "leave", "payroll"]);
  });
});

describe("isActive", () => {
  it("matches Home only exactly", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/", "/users")).toBe(false);
  });
  it("matches other entries by prefix", () => {
    expect(isActive("/users", "/users/12")).toBe(true);
    expect(isActive("/users", "/clients")).toBe(false);
  });
});
