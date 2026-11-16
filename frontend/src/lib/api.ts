// Same-origin: Next.js forwards /api/* to Django (app/api/[...path]/route.ts). The sign-in cookies are HttpOnly, so no script holds a token.
const API_URL = "/api/v1";

export type RoleKey =
  | "ceo"
  | "marketing"
  | "commercial_head"
  | "commercial_member"
  | "hr_head"
  | "hr_member"
  | "operation_head"
  | "operation_member"
  | "super_admin";

export type Permissions = { manage_users: boolean; manage_clients: boolean };

export type User = {
  id: number;
  full_name: string;
  email: string;
  username: string | null;
  capabilities: string[];
  department: number | null;
  department_name: string | null;
  role: "head" | "member";
  role_key: RoleKey | null;
  is_active: boolean;
  must_change_password: boolean;
  preferred_language: "en" | "ar";
  permissions: Permissions;
};

export type SummaryClient = { id: number; company_name: string; contact_person: string; created_at: string };
export type DashboardSummary = {
  my_sign_ins: { timestamp: string }[];
  ceo?: {
    total_users: number;
    active_users: number;
    pending_password_users: number;
    users_by_department: { department: string; count: number }[];
    total_clients: number;
    recent_clients: SummaryClient[];
    recent_sign_ins: { user_id: number; full_name: string; timestamp: string }[];
  };
  operation?: { total_clients: number; clients_this_month: number; recent_clients: SummaryClient[] };
};

export type Department = { id: number; name: string };

export type Client = {
  id: number;
  company_name: string;
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
};

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  code: string;
  constructor(status: number, raw: Record<string, unknown>) {
    // Every server error is {"error": {"code", "message", "fields"?}}. It is flattened here to the shape the screens already read:
    // `detail` is the message, and each field name maps to its messages.
    const env = raw?.error as { code?: string; message?: string; fields?: Record<string, unknown> } | undefined;
    const data: Record<string, unknown> = env ? { ...(env.fields ?? {}), detail: env.message ?? "err.generic" } : (raw ?? {});
    // `message` is a backend message or a dictionary key. The screen turns it into the active language.
    super(typeof data?.detail === "string" ? data.detail : "err.generic");
    this.status = status;
    this.code = env?.code ?? "";
    this.data = data;
  }
  /** First message for each field, e.g. { email: "Someone already uses this email." } */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(this.data ?? {})) {
      const text = Array.isArray(value) ? String(value[0]) : typeof value === "string" ? value : "";
      if (text) out[key] = text;
    }
    return out;
  }
}

const CSRF_COOKIE = "csrf_token";

/** The readable half of the double-submit CSRF pair. Empty when nobody is signed in. */
function csrfToken() {
  const m = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : "";
}

async function send(path: string, method: string, body?: unknown) {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD") headers["X-CSRF-Token"] = csrfToken();
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, { detail: "err.network" });
  }
}

let refreshing: Promise<boolean> | null = null;

/** Asks for a new cookie pair. Nobody signed in means no CSRF cookie, so there is nothing to refresh. */
async function refreshAccess(): Promise<boolean> {
  if (!csrfToken()) return false;
  refreshing ??= (async () => {
    const res = await send("/auth/refresh/", "POST").catch(() => null);
    return !!res?.ok;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/**
 * `auth: false` is for the sign-in and sign-out calls. `quiet401` is for "who am I?" at page load, where a 401 just means
 * nobody is signed in (it must not announce an expired session).
 */
export async function api<T = unknown>(path: string, options: { method?: string; body?: unknown; auth?: boolean; quiet401?: boolean } = {}) {
  const { method = "GET", body, auth = true, quiet401 = false } = options;
  let res = await send(path, method, body);
  if (res.status === 401 && auth && (await refreshAccess())) {
    res = await send(path, method, body);
  }
  if (res.status === 401 && auth && !quiet401) {
    window.dispatchEvent(new Event("innovation:signed-out"));
  }
  const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

/** Returns a backend message or a dictionary key (never shown raw: pass it through msg() from useI18n). */
export function errorMessage(err: unknown, fallback = "err.generic") {
  return err instanceof ApiError && err.message ? err.message : fallback;
}

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type WorkItem = {
  kind: string;
  section: string;
  ref: string;
  title: string;
  link: string;
  due: string | null;
  overdue: boolean;
};
export type MyWork = { role: RoleKey | null; items: WorkItem[]; total: number; badges: Record<string, number>; unread_notifications: number };

export type AppNotification = { id: number; kind: string; title: string; body: string; link: string; created_at: string; read: boolean };
export type ActivityEntry = {
  id: number;
  actor: number | null;
  actor_name: string | null;
  action: string;
  from_value: string;
  to_value: string;
  comment: string;
  created_at: string;
};
export type RecordComment = { id: number; author: number; author_name: string; body: string; mentions: number[]; created_at: string };
export type RecordFile = {
  id: number;
  original_name: string;
  size: number;
  category: string;
  uploaded_by: number;
  uploaded_by_name: string;
  created_at: string;
  archived_at: string | null;
};

export type Lookup = { id: number; name_en: string; name_ar: string; is_active: boolean; sort_order: number };
export type ServiceLookup = Lookup & { default_unit_price: string | null; currency: string };
export type ChecklistLookup = Lookup & { required: boolean };
export type WorkHours = { work_start: string; work_end: string; grace_minutes: number };
export type SlaSettings = { first_contact_hours: number; follow_up_days: number };

/** "client:5" style reference used by the activity, comments and files endpoints. */
export type Target = string;

async function authedFetch(path: string, init: RequestInit) {
  const run = () => {
    const headers: Record<string, string> = { ...((init.headers as Record<string, string>) ?? {}) };
    if (init.method && init.method !== "GET") headers["X-CSRF-Token"] = csrfToken();
    return fetch(`${API_URL}${path}`, { ...init, headers, credentials: "same-origin" });
  };
  let res: Response;
  try {
    res = await run();
    if (res.status === 401 && (await refreshAccess())) res = await run();
  } catch {
    throw new ApiError(0, { detail: "err.network" });
  }
  return res;
}

/** Multipart upload (files). The browser sets the multipart boundary itself. */
export async function upload<T = unknown>(path: string, form: FormData) {
  const res = await authedFetch(path, { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

/** Files are never public URLs: fetch with the session cookie, then hand the browser a temporary blob to save. */
export async function downloadFile(path: string, fileName: string) {
  const res = await authedFetch(path, { method: "GET" });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({})));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export type LeadStatus = "new" | "contacted" | "waiting" | "qualified" | "rejected";
export type LeadPermissions = {
  can_edit: boolean;
  can_assign: boolean;
  can_log: boolean;
  can_reopen: boolean;
  can_archive: boolean;
  can_restore: boolean;
  can_request_quotation: boolean;
  can_skip_quotation: boolean;
  can_request_contract: boolean;
};
export type Lead = {
  id: number;
  ref: string;
  company_name: string;
  contact_name: string;
  phone: string;
  email: string;
  source: string;
  notes: string;
  status: LeadStatus;
  assigned_to: number | null;
  assigned_to_name: string | null;
  assigned_at: string | null;
  batch: number | null;
  batch_ref: string | null;
  created_by: number;
  created_by_name: string;
  created_at: string;
  next_follow_up: string | null;
  rejection_reason: number | null;
  rejection_reason_en: string | null;
  rejection_reason_ar: string | null;
  rejection_note: string;
  first_contacted_at: string | null;
  last_contacted_at: string | null;
  qualified_at: string | null;
  rejected_at: string | null;
  archived_at: string | null;
  archive_reason: string;
  follow_up_overdue: boolean;
  first_contact_overdue: boolean;
  permissions: LeadPermissions;
  quotation: { id: number; ref: string; status: QuotationStatus } | null;
  contract: { id: number; ref: string; status: ContractStatus } | null;
  skipped_quotation_at: string | null;
  updated_at: string;
};
export type Interaction = {
  id: number;
  type: "call" | "whatsapp" | "email" | "meeting" | "other";
  occurred_at: string;
  notes: string;
  outcome: "" | "waiting" | "rejected" | "accepted";
  created_by: number;
  created_by_name: string;
  created_at: string;
};
export type ImportBatch = {
  id: number;
  ref: string;
  filename: string;
  status: "active" | "undone";
  total_rows: number;
  imported_count: number;
  skipped_errors: number;
  skipped_duplicates: number;
  created_by: number;
  created_by_name: string;
  created_at: string;
  undone_at: string | null;
  contacted_count: number;
  can_undo: boolean;
};
export type PreviewRow = {
  row: number;
  company_name: string;
  contact_name: string;
  phone: string;
  email: string;
  source: string;
  notes: string;
  errors: { field: string; message: string }[];
  duplicate_of: string | null;
  duplicate_in_file: number | null;
  state: "ok" | "error" | "duplicate";
};
export type PreviewResult = { file_name: string; rows: PreviewRow[]; summary: { total: number; ok: number; errors: number; duplicates: number } };
export type BoardColumn = { status: LeadStatus; count: number; results: Lead[] };
export type Assignee = { id: number; full_name: string; role: string; open_leads: number };

export type QuotationStatus = "requested" | "in_preparation" | "in_review" | "changes_requested" | "signed" | "sent" | "waiting" | "confirmed" | "rejected" | "cancelled";
export type QuotationPermissions = {
  can_start: boolean;
  can_edit: boolean;
  can_review: boolean;
  can_send: boolean;
  can_outcome: boolean;
  can_cancel: boolean;
  can_print: boolean;
};
export type QuotationLine = {
  id?: number;
  position?: number;
  service: number | null;
  description: string;
  quantity: string;
  unit_price: string;
  discount_percent: string;
  tax_percent: string;
  line_total?: string;
};
export type QuotationVersion = {
  id: number;
  number: number;
  currency: string;
  valid_until: string | null;
  notes: string;
  created_by_name: string;
  created_at: string;
  submitted_at: string | null;
  is_draft: boolean;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  lines: QuotationLine[];
};
export type Quotation = {
  id: number;
  ref: string;
  lead: number;
  lead_ref: string;
  lead_company: string;
  lead_contact: string;
  assigned_to_name: string | null;
  status: QuotationStatus;
  requested_by: number;
  requested_by_name: string;
  request_note: string;
  prepared_by_name: string | null;
  review_comment: string;
  signed_by_name: string | null;
  signed_at: string | null;
  signed_version: number | null;
  sent_at: string | null;
  next_follow_up: string | null;
  rejection_reason: number | null;
  rejection_reason_en: string | null;
  rejection_reason_ar: string | null;
  rejection_note: string;
  outcome_at: string | null;
  cancel_reason: string;
  created_at: string;
  latest: { number: number; is_draft: boolean; currency: string; total: string; valid_until: string | null; count: number } | null;
  follow_up_overdue: boolean;
  permissions: QuotationPermissions;
  versions?: QuotationVersion[];
};
export type ServiceItem = { id: number; name_en: string; name_ar: string; default_unit_price: string | null; currency: string; is_active: boolean };

export type ContractStatus = "requested" | "drafting" | "with_commercial" | "meeting_logged" | "ceo_review" | "returned" | "signed" | "handed_over" | "cancelled";
export type ContractPermissions = {
  can_start: boolean;
  can_send: boolean;
  can_log_meeting: boolean;
  can_submit: boolean;
  can_review: boolean;
  can_handover: boolean;
  can_cancel: boolean;
};
export type Contract = {
  id: number;
  ref: string;
  lead: number;
  lead_ref: string;
  lead_company: string;
  lead_contact: string;
  assigned_to_name: string | null;
  quotation: number | null;
  quotation_ref: string | null;
  client: number | null;
  status: ContractStatus;
  requested_by_name: string;
  request_note: string;
  drafted_by_name: string | null;
  meeting_date: string | null;
  meeting_notes: string;
  meeting_by_name: string | null;
  submitted_to_ceo_at: string | null;
  ceo_comment: string;
  signed_by_name: string | null;
  signed_at: string | null;
  handed_over_by_name: string | null;
  handed_over_at: string | null;
  cancel_reason: string;
  created_at: string;
  permissions: ContractPermissions;
  attachable: string[];
  versions?: { id: number; number: number; note: string; created_by_name: string; created_at: string }[];
};

export type OpClientStatus = "onboarding" | "active" | "inactive";
export type ChecklistStatus = "pending" | "uploaded" | "verified" | "not_applicable";
export type ChecklistItem = {
  id: number;
  client: number;
  name_en: string;
  name_ar: string;
  required: boolean;
  status: ChecklistStatus;
  na_reason: string;
  verified_by_name: string | null;
  verified_at: string | null;
  position: number;
};
export type Frequency = "daily" | "weekly" | "biweekly" | "monthly" | "yearly" | "custom";
export type RecurringTask = {
  id: number;
  client: number;
  client_name: string;
  title: string;
  description: string;
  frequency: Frequency;
  interval_days: number | null;
  start_date: string;
  next_due: string;
  assignee: number | null;
  assignee_name: string | null;
  active: boolean;
};
export type TaskInstance = {
  id: number;
  client: number;
  client_name: string;
  recurring: number;
  title: string;
  due_date: string;
  assignee: number | null;
  assignee_name: string | null;
  status: "open" | "done" | "skipped";
  completion_note: string;
  skip_reason: string;
  closed_by_name: string | null;
  closed_at: string | null;
  overdue: boolean;
  can_work: boolean;
};
export type QAMeeting = { id: number; client: number; held_on: string; notes: string; next_date: string | null; logged_by_name: string; created_at: string };
export type OpClient = {
  id: number;
  company_name: string;
  contact_person: string;
  phone: string;
  email: string;
  status: OpClientStatus;
  activated_at: string | null;
  qa_cadence_days: number;
  open_tasks: number;
  overdue_tasks: number;
  required_total: number;
  required_done: number;
  next_qa_due: string | null;
  qa_overdue: boolean;
  permissions: { can_work: boolean; can_manage: boolean };
  address?: string;
  checklist?: ChecklistItem[];
  recurring_tasks?: RecurringTask[];
  contracts?: { id: number; ref: string }[];
};
export type OpAssignee = { id: number; full_name: string; is_head: boolean };

export type InstalmentStatus = "expected" | "partially_paid" | "paid" | "overdue" | "cancelled";
export type Instalment = {
  id: number;
  client: number;
  contract: number | null;
  contract_ref: string | null;
  number: number;
  due_date: string;
  amount: string;
  currency: string;
  note: string;
  status: InstalmentStatus;
  paid: string;
  balance: string;
  cancelled_at: string | null;
  cancel_reason: string;
  can_edit: boolean;
};
export type PaymentRow = {
  id: number;
  instalment: number;
  instalment_number: number;
  kind: "payment" | "reversal";
  amount: string;
  currency: string;
  received_on: string;
  method: "cash" | "bank_transfer" | "cheque" | "card" | "other";
  reference: string;
  note: string;
  reverses: number | null;
  reason: string;
  recorded_by_name: string;
  created_at: string;
  reversed: boolean;
  has_receipt: boolean;
  can_reverse: boolean;
};
export type PayTotals = { total: string; paid: string; balance: string; overdue_amount: string; overdue_count: number; next_due: string | null };
export type Statement = {
  client: { id: number; company_name: string };
  currency: string;
  totals: PayTotals;
  instalments: Instalment[];
  payments: PaymentRow[];
  permissions: { can_write: boolean };
  recorded?: number | null;
};
export type PayOverviewRow = PayTotals & { client: number; company_name: string; currency: string; instalments: number };

export type AttendanceRow = {
  user: number;
  user_name: string;
  department: string;
  date: string;
  first_in: string;
  last_out: string | null;
  hours: number | null;
  late: boolean;
  minutes_late: number;
  open: boolean;
};
export type AttendanceSummary = { days: number; late_days: number; hours: number; open_days: number };
export type AttendanceMine = { month: string; rows: AttendanceRow[]; summary: AttendanceSummary; work_hours: WorkHours };

export type LeaveType = { id: number; name_en: string; name_ar: string; paid: boolean; annual_days: number | null; is_active: boolean; sort_order: number };
export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";
export type LeaveRequest = {
  id: number;
  user: number;
  user_name: string;
  department: string;
  leave_type: number;
  type_en: string;
  type_ar: string;
  paid: boolean;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: LeaveStatus;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_note: string;
  created_at: string;
  can_decide: boolean;
  can_cancel: boolean;
};
export type LeaveBalance = { leave_type: number; name_en: string; name_ar: string; paid: boolean; allowance: number | null; used: number; pending: number; remaining: number | null };

export type PayrollStatus = "draft" | "ceo_approved" | "paid";
export type PayrollEntry = { id: number; user: number; user_name: string; department: string; base_salary: string; allowances: string; deductions: string; net: string; note: string };
export type PayrollRun = {
  id: number;
  month: string;
  currency: string;
  status: PayrollStatus;
  approved_by_name: string | null;
  approved_at: string | null;
  paid_by_name: string | null;
  paid_at: string | null;
  people: number;
  total_net: string;
  permissions: { can_edit: boolean; can_approve: boolean; can_reopen: boolean; can_pay: boolean };
  created_at: string;
  entries?: PayrollEntry[];
};
export type SalaryRow = { user: number; user_name: string; department: string; base_salary: string | null; currency: string | null };
export type Payslip = { id: number; month: string; currency: string; paid_at: string | null; user_name: string; department: string; base_salary: string; allowances: string; deductions: string; net: string; note: string };

export type ReportPoint = { key: string; value: number | null; n: number | null; label_en?: string; label_ar?: string };
export type ReportSeries = { key: string; unit: "count" | "hours" | "percent" | "money"; kind: "bar" | "line" | "funnel"; currency?: string; points: ReportPoint[] };
export type Report = {
  section: string;
  records: number;
  period: { from: string; to: string };
  series: ReportSeries[];
  kpis?: Record<string, { overdue_total: number; overdue_instalments: number }>;
  refused?: boolean;
  unpaid_records?: number;
  method?: { window_from: string; window_to: string; decided: number; left_early: number; min_sample: number; p_sent?: number; p_confirmed?: number; open_quotations?: number };
};
export type SearchHit = { kind: "lead" | "quotation" | "contract" | "client"; id: number; title: string; subtitle: string; href: string };
