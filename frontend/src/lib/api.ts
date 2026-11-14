const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export type RoleKey =
  | "ceo"
  | "marketing"
  | "commercial_head"
  | "commercial_member"
  | "hr_head"
  | "hr_member"
  | "operation_head"
  | "operation_member";

export type Permissions = { manage_users: boolean; manage_clients: boolean };

export type User = {
  id: number;
  full_name: string;
  email: string;
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
};

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  constructor(status: number, data: Record<string, unknown>) {
    // `message` is a backend message or a dictionary key. The screen turns it into the active language.
    super(typeof data?.detail === "string" ? data.detail : "err.generic");
    this.status = status;
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

const ACCESS = "innovation.access";
const REFRESH = "innovation.refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

async function send(path: string, method: string, body?: unknown, auth = true) {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, { detail: "err.network" });
  }
}

let refreshing: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  if (!tokens.refresh) return false;
  refreshing ??= (async () => {
    const res = await send("/auth/refresh/", "POST", { refresh: tokens.refresh }, false).catch(() => null);
    if (res?.ok) {
      tokens.set((await res.json()).access);
      return true;
    }
    return false;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function api<T = unknown>(path: string, options: { method?: string; body?: unknown; auth?: boolean } = {}) {
  const { method = "GET", body, auth = true } = options;
  let res = await send(path, method, body, auth);
  if (res.status === 401 && auth && (await refreshAccess())) {
    res = await send(path, method, body, auth);
  }
  if (res.status === 401 && auth) {
    tokens.clear();
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
  const run = () =>
    fetch(`${API_URL}${path}`, { ...init, headers: { ...(init.headers ?? {}), ...(tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}) } });
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

/** Files are never public URLs: fetch with the token, then hand the browser a temporary blob to save. */
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
  skipped_quotation_at: string | null;
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
